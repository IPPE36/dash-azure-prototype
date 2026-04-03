# standard imports
import random

# third party imports
from platypus.operators import PCX, SBX, PMX
from platypus import NSGAII, Problem, Real, nondominated
from scipy.spatial.distance import pdist

# local imports
from recipe_trainer.source.load_models import *
from recipe_trainer.source.data import *


class BatchProblem(Problem):
    def __init__(self, nvars, nobjs, batch_function, **kwargs):
        super().__init__(nvars, nobjs, **kwargs)
        self.batch_function = batch_function
        self.pending = []

    def evaluate(self, solution):
        self.pending.append(solution)

    def evaluate_all(self, solutions):
        self.pending.extend(s for s in solutions if not s.evaluated)
        losses, constraints = self.batch_function(self.pending)
        for sol, loss, constr in zip(self.pending, losses, constraints):
            sol.objectives[:] = loss
            sol.constraints[:] = constr
            sol.evaluated = True
        self.pending.clear()


class BatchNSGAII(NSGAII):
    def evaluate_all(self, solutions):
        """bypasses the evaluator"""
        self.problem.evaluate_all(solutions)
        self.nfe += len(solutions)


class Algorithm():
    def __init__(self, objectives: dict, objectives_strategies: dict, boundaries: dict, runs: int, population: int,
                 seed: int = 1, crossover: str = "SBX", n_materials: int = None, process: list = None,
                 new_crystex: dict = None, costs: dict = None, **kwargs):

        random.seed = seed
        self.costs = costs
        self.objectives = objectives
        self.objectives_strategies = objectives_strategies
        self.constraints = {}
        self.runs = runs
        self.process = pd.Series({key: val for key, val in zip(FEATURES_COMPOUNDING_IN, process)})
        self.new_crystex = new_crystex
        self.boundaries = boundaries
        self.population = population
        self.generations = runs // population
        self.keys = FEATURES_MATERIALS
        self.variator = {"SBX": SBX(distribution_index=20), "PCX": PCX(), "PMX": PMX()}.get(crossover)
        self.n_materials = n_materials
        self.mat_types = MAT_TYPES.copy()
        self.mat_types = {key: [v for v in val if v in self.keys] for key, val in self.mat_types.items()}
        self.mat_types_indices = {key: [list(self.keys).index(v) for v in val] for key, val in self.mat_types.items()}
        self.mat_types_n = {key: 1 if key in ["rtpo", "elastomer"] else 1 for key in MAT_TYPES.keys()}
        self.step = 0
        self.objective_keys = list(self.objectives.keys())
        self.objective_vals = list(self.objectives.values())

        # optimization attributes
        self.df_results = pd.DataFrame()
        self.result_options = None

        # get the boundaries of the parameters
        self.min_ = np.array([self.boundaries[key]["min"] if self.boundaries[key]["fit"] else 0 for key in self.keys])
        self.max_ = np.array([self.boundaries[key]["max"] if self.boundaries[key]["fit"] else 0 for key in self.keys])

        self.default_vals = np.array([self.boundaries[key]["val"] for key in self.keys if not self.boundaries[key]["fit"]])
        self.default_idcs = np.array([idx for idx, key in enumerate(self.keys) if not self.boundaries[key]["fit"]])
        self.fit_params = [key for key in self.keys if self.boundaries[key]["fit"]]

        # normalize between 0 and 1 if weight percentages in %
        self.min_ = self.min_ / 100 if np.max(self.min_) > 1 else self.min_
        self.max_ = self.max_ / 100 if np.max(self.max_) > 1 else self.max_
        try:
            self.default_vals = self.default_vals / 100 if np.max(self.default_vals) > 1 else self.default_vals
            for idx, val in zip(self.default_idcs, self.default_vals):
                self.max_[idx] = val
                self.min_[idx] = val
        except ValueError:
            pass

        # transform target weight fractions
        for key, val in self.objectives.items():
            if key.startswith("wt_") and val > 1:
                self.objectives[key] /= 100

        # for distance optimizations calcualte maximum distance of observations in the database
        self.max_distances = {}
        self.distance_df = {}
        for key in self.objective_keys:
            if self.objectives_strategies[key] == "maximize distance":
                df_ = DF.copy()
                df_ = df_.dropna(subset=FEATURES_WT + FEATURES_CRYSTEX + FEATURES_WEIGHTED + [key], how="any")
                self.distance_df[key] = df_
                self.max_distances[key] = pdist(df_[FEATURES_WT + FEATURES_CRYSTEX].values, metric='euclidean').max()

    def initialize(self) -> None:
        # number of constraints, see self.optimize_func()
        self.n_constraints = 2 + len(FEATURES_ALL) * 2 + len(list(self.constraints.keys()))
        self.n_losses = len(self.objective_keys)
        problem = BatchProblem(nvars=len(self.fit_params), nobjs=self.n_losses, nconstrs=self.n_constraints,
                               batch_function=self._optimize_fun)
        problem.directions[:] = Problem.MINIMIZE
        problem.constraints[:] = "<0"

        for i in range(len(self.fit_params)):
            problem.types[i] = Real(0, 1)

        self.optimization = BatchNSGAII(problem, population_size=self.population, variator=self.variator)

    def stepping(self) -> None:
        self.step += 1
        self.optimization.run(self.population)

        # do calculation not every generation
        if self.step == 1 or not self.step % 5 or self.step >= self.generations:
            self._update_solution(gen=self.step)

        # decrease randomness along optimization for stronger definition of pareto front
        if self.step >= int(self.generations / 2):
            self.variator.distribution_index = 15
        if self.step >= 3 * int(self.generations / 4):
            self.variator.distribution_index = 10

    def _update_solution(self, gen: int = 0):
        results = nondominated(self.optimization.result)
        losses, outputs = self._optimize_fun(results, optimization=False)
        df_results = pd.DataFrame()
        for i, l in enumerate(losses):
            o = outputs.iloc[i]
            row = {"idx": i, "gen": int(gen)}
            row.update({f"obj_{key}": val for key, val in zip(self.objective_keys, l)})
            row.update({"loss": (sum([row[f"obj_{key}"] ** 2 for key in self.objective_keys])) ** (1/2)})
            row.update({key: val for key, val in o.items()})
            row_series = pd.DataFrame.from_dict(row, orient='index').T
            df_results = pd.concat((df_results, row_series), axis=0)
        df_results.drop_duplicates(subset=FEATURES_MATERIALS, inplace=True, ignore_index=True)
        df_results = df_results.sort_values(by='loss', ascending=True, ignore_index=True)
        self.df_results = df_results

    def _constant_values(self, x):
        """if constant values are present that are not optimized in x at specific indices"""
        x = np.array(x)
        for i, v in zip(self.default_idcs, self.default_vals):
            x = np.insert(x, i, v)
        return x

    def _predict(self, x, return_bounds: bool = False):

        # relative quadratic difference
        losses = []
        for i, _ in outputs.iterrows():
            loss_ = self.loss_fun(
                outputs=outputs.iloc[i][self.objective_keys],
                uncertainties=outputs_std.iloc[i][self.objective_keys],
                distances=outputs_dist.iloc[i][self.objective_keys]
            )
            losses.append(loss_)

        return losses, outputs

    def _calculate_cost(self, x) -> float:
        return calculate_costs(x, keys=list(self.keys), costs_dic=self.costs)

    def _optimize_fun(self, x, optimization: bool = True):
        x = [x_.variables for x_ in x]
        x = [self._constant_values(x_) for x_ in x]
        x = [self._material_mix(x_) for x_ in x]
        x = np.vstack(x)
        losses, outputs = self._predict(x)
        if optimization:
            constraints = []
            for i, o in outputs.iterrows():
                constraint_ = []
                constraints.append(constraint_)
            return losses, constraints
        else:
            return losses, outputs

    def loss_fun(self, outputs: pd.Series, uncertainties: pd.Series = None, distances: pd.Series = None) -> list:
        loss_strategy = [0] * len(self.objective_keys)
        loss_targets = [
            ((t - o) / (BOUNDS_MAX[key] - BOUNDS_MIN[key])) ** 2
            for key, t, o in zip(self.objective_keys, self.objective_vals, outputs)
        ]
        for i, key in enumerate(self.objective_keys):
            if "greater than" in self.objectives_strategies[key]:
                loss_strategy[i] = abs(BOUNDS_MAX[key] - outputs[key]) / (BOUNDS_MAX[key] - BOUNDS_MIN[key])
                if outputs[key] >= self.objective_vals[i]:
                    loss_targets[i] = 0
            elif "smaller than" in self.objectives_strategies[key]:
                loss_strategy[i] = abs(outputs[key] - BOUNDS_MIN[key]) / (BOUNDS_MAX[key] - BOUNDS_MIN[key])
                if outputs[key] <= self.objective_vals[i]:
                    loss_targets[i] = 0
            elif "maximize uncertainty" in self.objectives_strategies[key]:
                loss_strategy[i] = abs(BOUNDS_MAX[key] - uncertainties[key]) / (BOUNDS_MAX[key] - BOUNDS_MIN[key])
                loss_targets[i] = 0
            elif "minimize uncertainty" in self.objectives_strategies[key]:
                loss_strategy[i] = abs(uncertainties[key] - BOUNDS_MIN[key]) / (BOUNDS_MAX[key] - BOUNDS_MIN[key])
                loss_targets[i] = 0
            elif "maximize distance" in self.objectives_strategies[key]:
                loss_strategy[i] = ((self.max_distances[key] - distances[key]) / self.max_distances[key]) ** 2
                loss_targets[i] = 0
            elif "minimize distance" in self.objectives_strategies[key]:
                loss_strategy[i] = (distances[key] / self.max_distances[key]) ** 2
                loss_targets[i] = 0
        return [t + s for t, s in zip(loss_targets, loss_strategy)]


if __name__ == '__main__':
    exit()
