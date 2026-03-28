
from typing import Any

import torch
import gpytorch

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

        for _ in range(epochs):
            perm = torch.randperm(x.shape[0], device=self.device)
            for i in range(0, x.shape[0], batch_size):
                idx = perm[i:i + batch_size]
                xb = x[idx]
                yb = y[idx]

                self.optimizer.zero_grad()
                preds = self.model(xb)
                loss = self.loss_fn(preds, yb)
                loss.backward()
                self.optimizer.step()
                losses.append(float(loss.detach().cpu().item()))

        return {"losses": losses}


@register_trainer("multitask_gp")
class MultiTaskGPTrainer(BaseTrainer):
    def __init__(
        self,
        model,
        *,
        device: str | torch.device = "cpu",
        lr: float = 0.05,
    ) -> None:
        super().__init__(model, device=device)
        self.lr = lr

    def train(self, train_x, train_y, *, epochs: int = 100) -> dict[str, Any]:
        self.model.gp_model.to(self.device)
        self.model.likelihood.to(self.device)
        self.model.gp_model.train()
        self.model.likelihood.train()

        x = torch.as_tensor(train_x, dtype=torch.float32, device=self.device)
        y = torch.as_tensor(train_y, dtype=torch.float32, device=self.device)

        self.model.gp_model.set_train_data(inputs=x, targets=y, strict=False)
        optimizer = torch.optim.Adam(self.model.gp_model.parameters(), lr=self.lr)
        mll = gpytorch.mlls.ExactMarginalLogLikelihood(self.model.likelihood, self.model.gp_model)

        losses: list[float] = []
        for _ in range(epochs):
            optimizer.zero_grad()
            output = self.model.gp_model(x)
            loss = -mll(output, y)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu().item()))

        return {"losses": losses}