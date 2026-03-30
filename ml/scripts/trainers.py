
from typing import Any

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
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=weight_decay)
        self.loss_fn = torch.nn.MSELoss()

    def train(self, train_x, train_y, *, epochs: int = 100, batch_size: int = None) -> dict[str, Any]:
        self.model.to(self.device)
        self.model.train()

        x = torch.as_tensor(train_x, dtype=torch.float32, device=self.device)
        y = torch.as_tensor(train_y, dtype=torch.float32, device=self.device)

        losses: list[float] = []
        if batch_size is None:
            batch_size = x.shape[0]

        epoch_bar = tqdm(range(epochs), desc="MLP training", leave=False)
        for epoch in epoch_bar:
            perm = torch.randperm(x.shape[0], device=self.device)
            epoch_losses: list[float] = []
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
                losses.append(loss_value)
                epoch_losses.append(loss_value)
            if epoch_losses:
                avg_loss = sum(epoch_losses) / len(epoch_losses)
                epoch_bar.set_postfix(loss=f"{avg_loss:.4f}")

        return {"losses": losses}


@register_trainer("multitask_gp")
class MultiTaskGPTrainer(BaseTrainer):
    def __init__(
        self,
        model,
        *,
        device: str | torch.device = "cpu",
        lr: float = 0.05,
        weight_decay: float = 0.0,
        lr_min: float | None = None,
        lr_iter: int = 1000,
    ) -> None:
        super().__init__(model, device=device)
        self.lr = lr
        self.weight_decay = weight_decay
        self.lr_min = lr_min
        self.lr_iter = lr_iter

    def train(self, train_x, train_y, *, epochs: int = 100) -> dict[str, Any]:
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

        return {"losses": losses}
