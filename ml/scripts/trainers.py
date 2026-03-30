from typing import Any
import time
import numpy as np
import torch
import gpytorch
from tqdm.auto import tqdm

from .base import BaseTrainer
from .registry import register_trainer


@register_trainer("mlp_regressor")
class MLPTrainer(BaseTrainer):
    def __init__(
        self,
        model,
        *,
        device: str | torch.device = "cpu",
        lr: float = 1e-3,
        weight_decay: float = 0.0,
    ) -> None:
        super().__init__(model, device=device)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay,
        )
        self.loss_fn = torch.nn.MSELoss()

    def train(
        self,
        train_x,
        train_y,
        *,
        val_x=None,
        val_y=None,
        epochs: int = 100,
        batch_size: int | None = None,
        early_stopping_patience: int | None = 10,
        early_stopping_min_delta: float = 0.0,
        restore_best_weights: bool = True,
    ) -> dict[str, Any]:
        self.duration = None
        start_time = time.perf_counter()

        self.model.to(self.device)

        x = torch.as_tensor(train_x, dtype=torch.float32, device=self.device)
        y = torch.as_tensor(train_y, dtype=torch.float32, device=self.device)

        has_validation = val_x is not None and val_y is not None
        if (val_x is None) ^ (val_y is None):
            raise ValueError("val_x and val_y must either both be provided or both be None.")

        if has_validation:
            x_val = torch.as_tensor(val_x, dtype=torch.float32, device=self.device)
            y_val = torch.as_tensor(val_y, dtype=torch.float32, device=self.device)

        if batch_size is None:
            batch_size = x.shape[0]

        train_losses: list[float] = []
        val_losses: list[float] = []

        best_val_loss = float("inf")
        best_state_dict = None
        patience_counter = 0
        stopped_early = False
        best_epoch = -1

        epoch_bar = tqdm(range(epochs), desc="MLP training", leave=False)

        for epoch in epoch_bar:
            self.model.train()

            perm = torch.randperm(x.shape[0], device=self.device)
            epoch_train_losses: list[float] = []

            for i in range(0, x.shape[0], batch_size):
                idx = perm[i:i + batch_size]
                xb = x[idx]
                yb = y[idx]

                self.optimizer.zero_grad()
                preds = self.model(xb)
                loss = self.loss_fn(preds, yb)
                loss.backward()
                self.optimizer.step()

                loss_value = float(loss.detach().cpu().item())
                train_losses.append(loss_value)
                epoch_train_losses.append(loss_value)

            avg_train_loss = (
                sum(epoch_train_losses) / len(epoch_train_losses)
                if epoch_train_losses
                else float("nan")
            )

            postfix = {"train_loss": f"{avg_train_loss:.6f}"}

            if has_validation:
                self.model.eval()
                with torch.no_grad():
                    val_preds = self.model(x_val)
                    val_loss = self.loss_fn(val_preds, y_val)
                    avg_val_loss = float(val_loss.detach().cpu().item())

                val_losses.append(avg_val_loss)
                postfix["val_loss"] = f"{avg_val_loss:.4f}"

                improved = avg_val_loss < (best_val_loss - early_stopping_min_delta)
                if improved:
                    best_val_loss = avg_val_loss
                    best_epoch = epoch
                    patience_counter = 0
                    if restore_best_weights:
                        best_state_dict = {
                            k: v.detach().cpu().clone()
                            for k, v in self.model.state_dict().items()
                        }
                else:
                    patience_counter += 1

                if (
                    early_stopping_patience is not None
                    and patience_counter >= early_stopping_patience
                ):
                    stopped_early = True
                    epoch_bar.set_postfix(postfix)
                    break

            epoch_bar.set_postfix(postfix)

        if has_validation and restore_best_weights and best_state_dict is not None:
            self.model.load_state_dict(best_state_dict)
            self.model.to(self.device)

        self.duration = time.perf_counter() - start_time

        return {
            "losses": train_losses,
            "val_losses": val_losses,
            "duration": self.duration,
            "best_val_loss": None if not has_validation else best_val_loss,
            "best_epoch": None if not has_validation else best_epoch,
            "stopped_early": stopped_early,
        }


@register_trainer("multitask_gp")
class MultiTaskGPTrainer(BaseTrainer):
    def __init__(
        self,
        model,
        *,
        device: str | torch.device = "cpu",
        lr: float = 0.05,
        weight_decay: float = 0.0,
        lr_min: float = None,
        lr_iter: int = 1000,
    ) -> None:
        super().__init__(model, device=device)
        self.lr = lr
        self.weight_decay = weight_decay
        self.lr_min = lr_min
        self.lr_iter = lr_iter

    def train(
        self,
        train_x,
        train_y,
        *,
        epochs: int = 100,
    ) -> dict[str, Any]:
        self.duration = None
        start_time = time.perf_counter()
        self.model.gp_model.to(self.device)
        self.model.likelihood.to(self.device)
        self.model.gp_model.train()
        self.model.likelihood.train()

        x = torch.as_tensor(train_x, dtype=torch.float32, device=self.device)
        y = torch.as_tensor(train_y, dtype=torch.float32, device=self.device)

        self.model.gp_model.set_train_data(inputs=x, targets=y, strict=False)
        optimizer = torch.optim.Adam(
            self.model.gp_model.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )
        mll = gpytorch.mlls.ExactMarginalLogLikelihood(self.model.likelihood, self.model.gp_model)
        scheduler = None
        if self.lr_min is not None and self.lr_min > 0 and self.lr_min < self.lr:
            gamma = float(np.exp(np.log(self.lr_min / self.lr) / self.lr_iter))
            scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=gamma)

        losses: list[float] = []
        epoch_bar = tqdm(range(epochs), desc="GP training", leave=False)
        for epoch in epoch_bar:
            optimizer.zero_grad()
            with gpytorch.settings.cholesky_jitter(1e-5), gpytorch.settings.observation_nan_policy("mask"):
                output = self.model.gp_model(x)
                loss = -mll(output, y)
            loss.backward()
            optimizer.step()
            if scheduler is not None:
                scheduler.step()
            loss_value = float(loss.detach().cpu().item())
            losses.append(loss_value)
            epoch_bar.set_postfix(loss=f"{loss_value:.4f}")

        self.duration = time.perf_counter() - start_time
        return {"losses": losses, "duration": self.duration}
