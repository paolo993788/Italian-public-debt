"""VAR(1) for the macroeconomic drivers of debt (real growth, inflation, long-term rate).

The model is estimated by OLS on deviations from the sample means,
u_t = A u_{t-1} + e_t; the residuals e_t are resampled in the stochastic debt
sustainability analysis so that their joint distribution (including fat tails
and correlations such as falling growth with rising spreads) is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class VAR1:
    names: list
    mean: np.ndarray
    A: np.ndarray
    residuals: np.ndarray
    sample: str

    @property
    def stable(self) -> bool:
        return bool(np.max(np.abs(np.linalg.eigvals(self.A))) < 1.0)

    @property
    def residual_cov(self) -> np.ndarray:
        return np.cov(self.residuals, rowvar=False, ddof=self.A.shape[0])

    def last_deviation(self, frame: pd.DataFrame) -> np.ndarray:
        return frame[self.names].dropna().iloc[-1].to_numpy() - self.mean


def fit_var1(frame: pd.DataFrame, columns=("real_growth", "inflation", "long_rate")) -> VAR1:
    data = frame[list(columns)].dropna()
    mean = data.mean().to_numpy()
    u = data.to_numpy() - mean
    Y, X = u[1:], u[:-1]
    A = np.linalg.lstsq(X, Y, rcond=None)[0].T
    residuals = Y - X @ A.T
    return VAR1(list(columns), mean, A, residuals, f"{data.index.min()}-{data.index.max()}")
