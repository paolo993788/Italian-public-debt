"""Debt accounting: decomposition of debt dynamics and counterfactual paths.

Identity for the debt ratio d (debt / nominal GDP), with the effective interest
rate i, real growth g, inflation pi (GDP deflator), nominal growth
gamma = (1 + g)(1 + pi) - 1, primary balance pb and stock-flow adjustment sfa:

    d_t - d_{t-1} = -pb_t + d_{t-1} (i_t - gamma_t) / (1 + gamma_t) + sfa_t.

The "snowball" term d (i - gamma) / (1 + gamma) is split, following the European
Commission's convention, into

    interest effect      d_{t-1} i_t / (1 + gamma_t)
    real-growth effect  -d_{t-1} g_t / (1 + gamma_t)
    inflation effect    -d_{t-1} pi_t (1 + g_t) / (1 + gamma_t)

and the stock-flow adjustment is the residual that closes the identity
(privatisation receipts, accumulation of financial assets, exchange-rate and
valuation effects, differences between cash and accrual accounting, statistical
reclassifications). All inputs are fractions/decimals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def debt_decomposition(fiscal: pd.DataFrame) -> pd.DataFrame:
    """Year-by-year contributions to the change in the debt ratio (fractions of GDP)."""
    f = fiscal.sort_index()
    d_prev = f["debt"].shift(1)
    gamma = (1 + f["real_growth"]) * (1 + f["inflation"]) - 1
    out = pd.DataFrame(index=f.index)
    out["change in debt"] = f["debt"] - d_prev
    out["primary deficit"] = -f["primary_balance"]
    out["interest"] = f["interest"]          # equals d_{t-1} i_t / (1 + gamma_t) by construction
    out["real growth"] = -d_prev * f["real_growth"] / (1 + gamma)
    out["inflation"] = -d_prev * f["inflation"] * (1 + f["real_growth"]) / (1 + gamma)
    out["snowball"] = out["interest"] + out["real growth"] + out["inflation"]
    out["stock-flow adjustment"] = out["change in debt"] - out["primary deficit"] - out["snowball"]
    return out.dropna()


def by_period(decomposition: pd.DataFrame, periods: dict) -> pd.DataFrame:
    """Cumulative contributions over named periods, e.g. {"1995-1999": (1995, 1999)}."""
    rows = {name: decomposition.loc[start:end].sum() for name, (start, end) in periods.items()}
    return pd.DataFrame(rows).T


def stabilising_primary_balance(debt, effective_rate, real_growth, inflation):
    """Primary balance that keeps the debt ratio constant: d (i - gamma) / (1 + gamma)."""
    gamma = (1 + np.asarray(real_growth)) * (1 + np.asarray(inflation)) - 1
    return np.asarray(debt) * (np.asarray(effective_rate) - gamma) / (1 + gamma)


def replay(d0, effective_rate, real_growth, inflation, primary_balance, sfa):
    """Debt ratio path implied by the identity for given component paths (counterfactuals)."""
    d = [float(d0)]
    for i, g, pi, pb, s in zip(effective_rate, real_growth, inflation, primary_balance, sfa):
        d.append(d[-1] * (1 + i) / ((1 + g) * (1 + pi)) - pb + s)
    return np.array(d[1:])


def counterfactual(fiscal: pd.DataFrame, start: int, **overrides) -> pd.Series:
    """Replay the observed debt path from `start` changing some components.

    `overrides` maps column names (effective_rate, real_growth, inflation, primary_balance)
    to scalars or Series; the observed stock-flow adjustments are kept. With no override
    the observed path is reproduced exactly.
    """
    f = fiscal.sort_index()
    dec = debt_decomposition(f)
    window = f.loc[start + 1:]
    comps = {k: window[k].copy() for k in ("effective_rate", "real_growth", "inflation", "primary_balance")}
    for name, value in overrides.items():
        if name not in comps:
            raise KeyError(f"unknown component {name}")
        comps[name] = value.reindex(window.index) if isinstance(value, pd.Series) else pd.Series(float(value), index=window.index)
    path = replay(f.loc[start, "debt"], comps["effective_rate"], comps["real_growth"], comps["inflation"],
                  comps["primary_balance"], dec.loc[window.index, "stock-flow adjustment"])
    return pd.Series(path, index=window.index, name="counterfactual debt")
