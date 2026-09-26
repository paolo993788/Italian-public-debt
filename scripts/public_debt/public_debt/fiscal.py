"""Cyclical adjustment, fiscal stance and fiscal reaction functions.

* Output gap from the Hodrick-Prescott trend of log real GDP (lambda = 100 for annual
  data by default; the European Commission uses a production-function approach, so
  the gap here is an approximation).
* Cyclically adjusted balance CAB = b - epsilon * gap, with epsilon the semi-elasticity
  of the budget balance to the output gap (about 0.5-0.55 for Italy in the European
  Commission's estimates, Mourre, Poissonnier and Lausegger, 2019). The cyclically
  adjusted primary balance CAPB adds back interest; its annual change measures the
  discretionary fiscal stance.
* Fiscal reaction function (Bohn, 1998): pb_t = a + rho d_{t-1} + beta gap_t + e_t.
  rho > 0 means that the primary balance improves when debt rises, a sufficient
  condition for sustainability in Bohn's framework. Standard errors are Newey-West.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy import stats

SEMI_ELASTICITY_ITALY = 0.55


def hp_filter(y, lam=100.0):
    """Hodrick-Prescott trend: argmin sum (y - tau)^2 + lam sum (second difference of tau)^2."""
    y = np.asarray(y, dtype=float)
    n = y.size
    D = sparse.diags([np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)], [0, 1, 2], shape=(n - 2, n))
    trend = spsolve((sparse.eye(n) + lam * (D.T @ D)).tocsc(), y)
    return trend


def output_gap(real_gdp: pd.Series, lam=100.0) -> pd.Series:
    """Output gap as a fraction of potential output, from the HP trend of log GDP."""
    log_y = np.log(real_gdp.astype(float))
    return pd.Series(log_y.to_numpy() - hp_filter(log_y, lam), index=real_gdp.index, name="output gap")


def cyclically_adjusted(fiscal: pd.DataFrame, gap: pd.Series, epsilon=SEMI_ELASTICITY_ITALY) -> pd.DataFrame:
    out = pd.DataFrame(index=fiscal.index)
    out["output gap"] = gap.reindex(fiscal.index)
    out["cyclical component"] = epsilon * out["output gap"]
    out["cyclically adjusted balance"] = fiscal["balance"] - out["cyclical component"]
    out["cyclically adjusted primary balance"] = out["cyclically adjusted balance"] + fiscal["interest"]
    out["fiscal stance (change in CAPB)"] = out["cyclically adjusted primary balance"].diff()
    return out


def ols(y, X, newey_west_lags=None):
    """OLS with classical or Newey-West standard errors. Returns coefficients, s.e., t, p, R^2."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)
    if newey_west_lags is None:
        cov = XtX_inv * (e @ e) / (n - k)
    else:
        S = (X * e[:, None]).T @ (X * e[:, None])
        for lag in range(1, newey_west_lags + 1):
            w = 1 - lag / (newey_west_lags + 1)
            G = (X[lag:] * e[lag:, None]).T @ (X[:-lag] * e[:-lag, None])
            S += w * (G + G.T)
        cov = XtX_inv @ S @ XtX_inv * n / (n - k)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), n - k)
    r2 = 1 - (e @ e) / np.sum((y - y.mean()) ** 2)
    return {"coef": beta, "se": se, "t": t, "p": p, "r2": r2, "n": n, "resid": e}


def fiscal_reaction(fiscal: pd.DataFrame, gap: pd.Series, lags=2) -> pd.DataFrame:
    """Bohn (1998) regression of the primary balance on lagged debt and the output gap."""
    frame = pd.DataFrame({"pb": fiscal["primary_balance"], "debt_lag": fiscal["debt"].shift(1),
                          "gap": gap.reindex(fiscal.index)}).dropna()
    X = np.column_stack([np.ones(len(frame)), frame["debt_lag"], frame["gap"]])
    res = ols(frame["pb"], X, newey_west_lags=lags)
    table = pd.DataFrame({"coefficient": res["coef"], "std. error (Newey-West)": res["se"], "t": res["t"], "p-value": res["p"]},
                         index=["constant", "lagged debt ratio (rho)", "output gap"])
    table.attrs.update(r2=res["r2"], n=res["n"], years=f"{frame.index.min()}-{frame.index.max()}")
    return table
