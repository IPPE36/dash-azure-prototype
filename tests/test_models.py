import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
torch = pytest.importorskip("torch")
StandardScaler = pytest.importorskip("sklearn.preprocessing").StandardScaler

from worker.models.base import BaseTorchModel, _inverse_transform_gaussian_stats
from worker.models.io_utils import ArtifactIO
from worker.models.registry import MODEL_REGISTRY, create_model, get_model_class, register_model
from worker.models.repo import ModelRepository
from worker.models.specs import AuxilaryData, ModelConfig, PreprocessConfig


def _ensure_registered(name: str, cls):
    if name not in MODEL_REGISTRY:
        register_model(name)(cls)


class DummyRegModel(BaseTorchModel):
    task_type = "regression"

    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux=aux)
        self.linear = torch.nn.Linear(spec.input_dim, spec.output_dim, bias=False)

    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        mean = self.linear(x)
        if return_std:
            std = torch.ones_like(mean) * 0.5
            return {"mean": mean, "std": std}
        return mean

    def _format_prediction(
        self,
        raw,
        *,
        input_kind: str,
        return_std: bool = False,
        return_bounds: bool = False,
        ordinal: bool = False,
    ):
        if isinstance(raw, dict):
            mean = raw.get("mean")
            std = raw.get("std")
        else:
            mean = raw
            std = None

        mean_np = mean.detach().cpu().numpy()
        std_np = std.detach().cpu().numpy() if std is not None else None

        if return_bounds or return_std:
            if std_np is None:
                std_np = np.zeros_like(mean_np)
            mean_u, std_u, lower, upper = self._inv_transform_y_stats(mean_np, std_np)
            payload = {
                "mean": self._to_pandas(mean_u, columns=self.spec.targets, input_kind=input_kind),
                "lower": self._to_pandas(lower, columns=self.spec.targets, input_kind=input_kind),
                "upper": self._to_pandas(upper, columns=self.spec.targets, input_kind=input_kind),
            }
            if return_std:
                payload["std"] = self._to_pandas(std_u, columns=self.spec.targets, input_kind=input_kind)
            return payload

        mean_u = self._inv_transform_y(mean_np)
        return self._to_pandas(mean_u, columns=self.spec.targets, input_kind=input_kind)


class DummyClsModel(BaseTorchModel):
    task_type = "classification"

    def __init__(self, spec: ModelConfig, prep: PreprocessConfig = None, aux: AuxilaryData = None) -> None:
        super().__init__(spec=spec, prep=prep, aux=aux)
        self.linear = torch.nn.Linear(spec.input_dim, spec.output_dim, bias=False)

    def _predict_tensor(self, x: torch.Tensor, *, return_std: bool = False):
        return self.linear(x)

    def _format_prediction(
        self,
        raw,
        *,
        input_kind: str,
        return_std: bool = False,
        return_bounds: bool = False,
        ordinal: bool = False,
    ):
        out = raw.detach().cpu().numpy()
        return self._to_pandas(out, columns=self.spec.targets, input_kind=input_kind)


_ensure_registered("dummy_reg", DummyRegModel)
_ensure_registered("dummy_cls", DummyClsModel)


def _make_spec(model_type: str, n_features: int = 3, n_targets: int = 2, *, requires_aux: bool = False):
    features = [f"x{i}" for i in range(n_features)]
    targets = [f"y{i}" for i in range(n_targets)]
    return ModelConfig(
        model_type=model_type,
        features=features,
        targets=targets,
        requires_aux=requires_aux,
    )


def test_registry_create_model_and_lookup_errors():
    spec = _make_spec("dummy_reg")
    model = create_model(spec=spec, prep=PreprocessConfig(), aux=AuxilaryData())
    assert isinstance(model, DummyRegModel)
    assert get_model_class("dummy_reg") is DummyRegModel

    try:
        get_model_class("nope")
    except KeyError as exc:
        assert "Unknown model type" in str(exc)
    else:
        raise AssertionError("Expected get_model_class to raise for unknown type.")


def test_predict_mixin_dataframe_series_and_clip_bounds():
    spec = _make_spec("dummy_reg", n_features=2, n_targets=2)
    model = DummyRegModel(spec)

    df = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=spec.features)
    pred = model.predict(df)
    assert isinstance(pred, pd.DataFrame)
    assert list(pred.columns) == spec.targets

    series = pd.Series({"x0": 1.0, "x1": 2.0})
    pred_series = model.predict(series)
    assert isinstance(pred_series, pd.Series)
    assert list(pred_series.index) == spec.targets

    clip = {spec.targets[0]: (-0.1, 0.1), spec.targets[1]: (-0.1, 0.1)}
    pred_clip = model.predict(df, return_bounds=True, clip_bounds=clip)
    assert isinstance(pred_clip, dict)
    assert pred_clip["mean"].max().max() <= 0.1
    assert pred_clip["mean"].min().min() >= -0.1


def test_classification_rejects_regression_only_options():
    spec = _make_spec("dummy_cls", n_features=2, n_targets=1)
    model = DummyClsModel(spec)
    x = np.array([[0.0, 1.0]])

    try:
        model.predict(x, clip_bounds={"y0": (0.0, 1.0)})
    except ValueError as exc:
        assert "clip_bounds" in str(exc)
    else:
        raise AssertionError("Expected clip_bounds to raise for classification.")

    try:
        model.predict(x, return_bounds=True)
    except ValueError as exc:
        assert "return_bounds" in str(exc)
    else:
        raise AssertionError("Expected return_bounds to raise for classification.")

    model.predict(x, ordinal=True)


def test_inverse_transform_gaussian_stats_matches_scaler():
    rng = np.random.default_rng(1)
    raw = rng.normal(10.0, 2.0, size=(4, 2))
    scaler = StandardScaler().fit(raw)
    mean_scaled = scaler.transform(raw)
    std_scaled = np.full_like(mean_scaled, 0.5)

    mean_u, std_u, lower_u, upper_u = _inverse_transform_gaussian_stats(mean_scaled, std_scaled, scaler)
    assert np.allclose(mean_u, raw)
    assert np.all(std_u >= 0.0)
    assert lower_u.shape == upper_u.shape == mean_u.shape


def test_artifact_io_roundtrip(tmp_path):
    spec = _make_spec("dummy_reg", n_features=2, n_targets=1)
    model = DummyRegModel(spec)
    with torch.no_grad():
        model.linear.weight[:] = torch.tensor([[1.0, 2.0]])

    prep = PreprocessConfig()
    artifact_dir = tmp_path / "artifact"
    ArtifactIO.save(artifact_dir, model=model, spec=spec, prep=prep, aux=AuxilaryData())
    loaded = ArtifactIO.load(artifact_dir)

    assert isinstance(loaded, DummyRegModel)
    assert loaded.spec.model_type == "dummy_reg"

    x = np.array([[1.0, 1.0]], dtype=float)
    pred = loaded.predict(x)
    assert np.allclose(pred, np.array([[3.0]]))


def test_model_repository_load_and_bounds(tmp_path):
    spec = _make_spec("dummy_reg", n_features=2, n_targets=1, requires_aux=True)
    model = DummyRegModel(spec)
    with torch.no_grad():
        model.linear.weight[:] = torch.tensor([[1.0, 1.0]])

    train_x = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=float)
    train_y = np.array([[1.0], [5.0]], dtype=float)

    scaler_x = StandardScaler().fit(train_x)
    scaler_y = StandardScaler().fit(train_y)
    prep = PreprocessConfig(scaler_x=scaler_x, scaler_y=scaler_y)

    aux = AuxilaryData(
        train_x=torch.tensor(scaler_x.transform(train_x), dtype=torch.float32),
        train_y=torch.tensor(scaler_y.transform(train_y), dtype=torch.float32),
    )

    artifact_dir = tmp_path / "demo_a"
    ArtifactIO.save(artifact_dir, model=model, spec=spec, prep=prep, aux=aux)

    repo = ModelRepository(root=tmp_path, served_artifacts={"demo_a"})
    loaded = repo.get("demo_a")
    assert loaded is not None
    assert repo.is_active("demo_a")

    bounds = repo.bounds
    assert np.isclose(bounds["x0"][0], 0.0)
    assert np.isclose(bounds["x0"][1], 2.0)
    assert np.isclose(bounds["x1"][0], 1.0)
    assert np.isclose(bounds["x1"][1], 3.0)
    assert np.isclose(bounds["y0"][0], 1.0)
    assert np.isclose(bounds["y0"][1], 5.0)

    assert repo.find_by_targets({"y0"}) == ["demo_a"]

    repo.unload("demo_a")
    assert not repo.is_active("demo_a")


def test_model_repository_errors(tmp_path):
    try:
        ModelRepository(root=tmp_path, served_artifacts=set())
    except ValueError as exc:
        assert "served_artifacts" in str(exc)
    else:
        raise AssertionError("Expected served_artifacts empty to raise.")

    (tmp_path / "demo_a").mkdir()
    repo = ModelRepository(root=tmp_path, served_artifacts={"demo_a"})
    assert repo.list_available() == []

    try:
        repo.get("other")
    except KeyError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("Expected unserved artifact access to raise.")

    try:
        repo.get("demo_a")
    except KeyError as exc:
        assert "Unknown or unloadable" in str(exc)
    else:
        raise AssertionError("Expected missing config to raise.")
