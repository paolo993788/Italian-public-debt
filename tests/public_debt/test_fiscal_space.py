"""Panel fiscal reaction functions, debt limits and spread regressions: estimator identities, standard
errors against direct formulas, limiting cases of the debt limit."""

import numpy as np
import pandas as pd
import pytest
from scipy import optimize

from public_debt import fiscal_space as fs


def simulated(n_geo=8, years=range(2000, 2030), seed=3, noise=0.01):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_geo):
        mu = rng.normal(0, 0.02)
        for t in years:
            x1, x2 = rng.normal(1, 0.3), rng.normal(0, 0.02)
            rows.append({"geo": f"G{i}", "year": t, "x1": x1, "x2": x2,
                         "y": mu + 0.05 * x1 + 0.4 * x2 + 0.01 * np.sin(t) + noise * rng.standard_normal()})
    return pd.DataFrame(rows)


def test_within_estimator_equals_dummy_variable_regression():
    df = simulated()
    for time_effects in (False, True):
        res = fs.within_regression(df, "y", ["x1", "x2"], time_effects=time_effects, se="classical")
        D = pd.get_dummies(df["geo"], dtype=float)
        parts = [df[["x1", "x2"]], D]
        if time_effects:
            parts.append(pd.get_dummies(df["year"], dtype=float).iloc[:, 1:])
        Z = pd.concat(parts, axis=1).to_numpy()
        beta = np.linalg.lstsq(Z, df["y"].to_numpy(), rcond=None)[0]
        np.testing.assert_allclose(res["coef"].to_numpy(), beta[:2], rtol=1e-9)
        # entity effect + average year effect reproduces the mean fitted intercept
        fitted = Z @ beta
        implied = res["fixed_effects"].reindex(df["geo"]).to_numpy() + df[["x1", "x2"]].to_numpy() @ res["coef"].to_numpy()
        if time_effects:
            implied = implied + df["year"].map({**{y: 0.0 for y in df["year"].unique()},
                                                **{int(k.split("_")[1]): v for k, v in res["time_coef"].items()}}).to_numpy()
        np.testing.assert_allclose(implied, fitted, atol=1e-10)
    assert abs(res["coef"]["x1"] - 0.05) < 0.01 and abs(res["coef"]["x2"] - 0.4) < 0.1


def test_standard_errors_match_direct_formulas():
    df = simulated(seed=4)
    dk = fs.within_regression(df, "y", ["x1", "x2"], se="driscoll_kraay", lags=0)
    cl = fs.within_regression(df, "y", ["x1", "x2"], se="cluster")
    dm = df[["y", "x1", "x2"]] - df.groupby("geo")[["y", "x1", "x2"]].transform("mean")
    Z, Y = dm[["x1", "x2"]].to_numpy(), dm["y"].to_numpy()
    b = np.linalg.solve(Z.T @ Z, Z.T @ Y)
    u = Y - Z @ b
    ZZi = np.linalg.inv(Z.T @ Z)
    h_t = pd.DataFrame(Z * u[:, None]).groupby(df["year"].to_numpy()).sum().to_numpy()
    np.testing.assert_allclose(dk["se"].to_numpy(), np.sqrt(np.diag(ZZi @ h_t.T @ h_t @ ZZi)), rtol=1e-10)
    h_g = pd.DataFrame(Z * u[:, None]).groupby(df["geo"].to_numpy()).sum().to_numpy()
    G, n, k = 8, len(Y), 2
    adj = G / (G - 1) * (n - 1) / (n - k)
    np.testing.assert_allclose(cl["se"].to_numpy(), np.sqrt(np.diag(adj * ZZi @ h_g.T @ h_g @ ZZi)), rtol=1e-10)
    lagged = fs.within_regression(df, "y", ["x1", "x2"], se="driscoll_kraay", lags=3)
    assert np.all(lagged["se"] > 0)


def test_required_balance_and_debt_limit_limiting_cases():
    r, g = 0.04, 0.02
    assert fs.required_balance(1.0, r, g) == pytest.approx(0.02 / 1.02)
    # a reaction steeper than (r - g)/(1 + g) everywhere: no upper limit
    assert np.isinf(fs.debt_limit(lambda d: 0.01 + 0.05 * np.asarray(d), r, g))
    # a reaction below the line everywhere: no sustainable debt level
    assert np.isnan(fs.debt_limit(lambda d: -0.05 + 0.0 * np.asarray(d), r, g))
    # cubic with fatigue: the limit is the upper root of pb(d) = required(d)
    pb = lambda d: -0.02 + 0.12 * np.asarray(d) - 0.04 * np.asarray(d) ** 3   # noqa: E731
    root = optimize.brentq(lambda d: pb(d) - fs.required_balance(d, r, g), 1.0, 3.0)
    assert fs.debt_limit(pb, r, g, grid=np.linspace(0, 3, 30001)) == pytest.approx(root, abs=1e-6)
    # a debt-dependent interest rate lowers the limit
    assert fs.debt_limit(pb, r, g, kappa=0.02, d0=1.0) < fs.debt_limit(pb, r, g)


def test_reaction_function_and_draws_on_the_simulated_panel():
    panel = fs.panel_dataset(official=False)
    res = fs.fiscal_reaction_panel(panel, degree=3)
    assert res["coef"]["gap"] == pytest.approx(0.4, abs=0.1)
    d = np.array([0.5, 1.0])
    pb = fs.reaction(res, panel["geo"].iloc[0], d)
    assert pb.shape == (2,)
    frozen = dict(res)
    frozen["cov"] = res["cov"] * 0.0
    geo = panel["geo"].iloc[0]
    draws = fs.debt_limit_draws(frozen, geo, 0.03, 0.02, n_draws=5, grid=np.linspace(0, 3, 1501))
    expected = fs.debt_limit(lambda x: fs.reaction(res, geo, x), 0.03, 0.02, grid=np.linspace(0, 3, 1501))
    np.testing.assert_allclose(draws, expected, atol=1e-9)


def test_spread_regression_detects_the_post_2008_change():
    panel = fs.panel_dataset(official=False)
    res = fs.spread_regression(panel, geos=[g for g in fs.ADVANCED_EU if g != "DE"], first_year=1996)
    assert res["coef"]["debt_lag x post"] > 0 and res["t"]["debt_lag x post"] > 2
    w = fs.wald_test(res, ["debt_lag", "debt_lag x post"])
    assert w["estimate"] == pytest.approx(res["coef"]["debt_lag"] + res["coef"]["debt_lag x post"])
    fund = fs.fundamental_spread(res, "IT")
    np.testing.assert_allclose(fund["actual"], fund["fundamental"] + fund["residual"], atol=1e-12)
