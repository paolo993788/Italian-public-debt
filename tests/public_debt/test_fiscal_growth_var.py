"""HP filter, OLS/Newey-West, fiscal reaction, VAR(1) and growth accounting."""

import numpy as np
import pandas as pd
import pytest

from public_debt import fiscal, growth, synthetic
from public_debt.var import fit_var1


def test_hp_filter_limits():
    line = 3.0 + 0.2 * np.arange(40)
    np.testing.assert_allclose(fiscal.hp_filter(line, 1600.0), line, atol=1e-9)   # a line is its own trend
    y = np.random.default_rng(0).standard_normal(30)
    np.testing.assert_allclose(fiscal.hp_filter(y, 1e-10), y, atol=1e-8)        # lambda -> 0: no smoothing


def test_ols_matches_lstsq_and_newey_west_zero_lag_is_white():
    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(200), rng.standard_normal(200)])
    y = X @ [1.0, 2.0] + rng.standard_normal(200)
    res = fiscal.ols(y, X)
    np.testing.assert_allclose(res["coef"], np.linalg.lstsq(X, y, rcond=None)[0], rtol=1e-12)
    white = fiscal.ols(y, X, newey_west_lags=0)
    e = res["resid"]
    meat = (X * e[:, None]).T @ (X * e[:, None])
    bread = np.linalg.inv(X.T @ X)
    np.testing.assert_allclose(white["se"], np.sqrt(np.diag(bread @ meat @ bread * 200 / 198)), rtol=1e-12)


def test_fiscal_reaction_recovers_the_response():
    rng = np.random.default_rng(2)
    years = np.arange(1960, 2025)
    debt = 0.6 + np.cumsum(0.01 * rng.standard_normal(years.size))
    gap = 0.01 * rng.standard_normal(years.size)
    pb = np.r_[np.nan, -0.02 + 0.06 * debt[:-1] + 0.5 * gap[1:] + 0.002 * rng.standard_normal(years.size - 1)]
    frame = pd.DataFrame({"debt": debt, "primary_balance": pb}, index=years)
    table = fiscal.fiscal_reaction(frame, pd.Series(gap, index=years))
    assert table.loc["lagged debt ratio (rho)", "coefficient"] == pytest.approx(0.06, abs=0.02)
    assert table.loc["output gap", "coefficient"] == pytest.approx(0.5, abs=0.1)


def test_var1_recovers_dynamics():
    rng = np.random.default_rng(3)
    A = np.array([[0.4, 0.0, -0.1], [0.1, 0.6, 0.0], [0.0, 0.2, 0.8]])
    u = np.zeros((20_000, 3))
    for t in range(1, u.shape[0]):
        u[t] = A @ u[t - 1] + rng.normal(0, [0.01, 0.005, 0.004])
    frame = pd.DataFrame(u + [0.01, 0.02, 0.03], columns=["real_growth", "inflation", "long_rate"])
    var = fit_var1(frame)
    np.testing.assert_allclose(var.A, A, atol=0.03)
    assert var.stable


def test_growth_decomposition_is_exact():
    lp = synthetic.labour_and_population()
    dec = growth.decompose(lp)
    parts = dec.drop(columns="GDP per capita").sum(axis=1)
    np.testing.assert_allclose(parts, dec["GDP per capita"], atol=1e-14)
