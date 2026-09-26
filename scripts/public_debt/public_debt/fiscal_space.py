"""Panel fiscal reaction functions, fiscal fatigue, debt limits and sovereign spreads.

* **Fiscal reaction with fatigue** (Ghosh, Kim, Mendoza, Ostry and Qureshi, 2013): in a panel of advanced
  EU economies the primary balance responds to lagged debt through a cubic,
  pb_it = mu_i + b1 d_{i,t-1} + b2 d^2 + b3 d^3 + c gap_it + e_it,
  so the response can weaken ("fatigue") at high debt. Estimated by the within (fixed-effects) estimator,
  optionally with year effects, with Driscoll-Kraay standard errors (robust to heteroskedasticity, serial
  correlation and cross-country correlation) or standard errors clustered by country.
* **Debt limit**: with an effective interest-growth differential, debt is stable where the primary balance
  equals ((r - g) / (1 + g)) d. The debt limit is the largest debt ratio at which the country's reaction
  function still reaches that line: above it, debt keeps rising. Fiscal space is the limit minus current debt.
  The interest rate can depend on debt through a spread elasticity, r(d) = r0 + kappa (d - d0).
* **Sovereign spreads**: 10-year yield spreads against Germany in the euro area regressed on lagged debt,
  the lagged primary balance and growth, with the debt effect allowed to change after 2008 (markets priced
  fiscal fundamentals much more after the global financial crisis; Bernoth, von Hagen and Schuknecht, 2012;
  De Grauwe and Ji, 2013). The fitted value is the "fundamental" spread, the residual the part not explained
  by fundamentals (redenomination and contagion risk, market sentiment).

Units: ratios as fractions of GDP (0.05 = 5%), rates as decimals, spreads in percentage points.
Data: Eurostat gov_10dd_edpt1 (debt, net lending, interest), nama_10_gdp (real growth, nominal GDP),
irt_lt_mcby_a (10-year yields, Maastricht criterion).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import data
from .fiscal import hp_filter

ADVANCED_EU = ("AT", "BE", "DE", "DK", "EL", "ES", "FI", "FR", "IE", "IT", "NL", "PT", "SE")
EURO_AREA_SPREAD = ("AT", "BE", "ES", "FI", "FR", "IE", "IT", "NL", "PT")   # Greece in a robustness check


# --------------------------------------------------------------------------- data


def panel_dataset(geos=ADVANCED_EU, official=True, refresh=False, seed=5) -> pd.DataFrame:
    """Long panel (geo, year) with debt, primary balance, balance, interest, real and nominal growth,
    HP output gap (lambda 100 on log real GDP, country by country), 10-year yield and spread over Germany."""
    geos = list(geos)
    if not official:
        return synthetic_panel(geos, seed=seed)
    edp = data.eurostat("gov_10dd_edpt1", refresh, geo=geos, unit="PC_GDP", sector="S13", na_item=["GD", "B9", "D41PAY"])
    gdp = data.eurostat("nama_10_gdp", refresh, geo=geos, na_item="B1GQ", unit=["CLV_PCH_PRE", "CP_MEUR"])
    yld = data.eurostat("irt_lt_mcby_a", refresh, geo=geos)
    fiscal = edp.pivot_table(index=["geo", "year"], columns="na_item", values="value") / 100
    macro = gdp.pivot_table(index=["geo", "year"], columns="unit", values="value")
    yields = yld.set_index(["geo", "year"])["value"].groupby(level=[0, 1]).last()
    panel = pd.DataFrame({"debt": fiscal["GD"], "balance": fiscal["B9"], "interest": fiscal["D41PAY"]})
    panel["primary_balance"] = panel["balance"] + panel["interest"]
    panel = panel.join(pd.DataFrame({"real_growth": macro["CLV_PCH_PRE"] / 100, "nominal_gdp": macro["CP_MEUR"]}), how="left")
    panel["yield"] = yields.reindex(panel.index)
    panel = panel.reset_index()
    panel["year"] = panel["year"].astype(int)
    panel = panel.sort_values(["geo", "year"]).reset_index(drop=True)
    panel = _derived(panel)
    panel.attrs["source"] = "Eurostat gov_10dd_edpt1, nama_10_gdp, irt_lt_mcby_a"
    return panel


def _derived(panel: pd.DataFrame) -> pd.DataFrame:
    out = []
    for geo, g in panel.groupby("geo", sort=False):
        g = g.sort_values("year").copy()
        g["nominal_growth"] = g["nominal_gdp"].pct_change()
        level = np.log((1 + g["real_growth"].fillna(0.0)).cumprod())
        ok = g["real_growth"].notna().to_numpy()
        gap = np.full(len(g), np.nan)
        if ok.sum() > 5:
            gap[ok] = level.to_numpy()[ok] - hp_filter(level.to_numpy()[ok], 100.0)
        g["gap"] = gap
        g["debt_lag"] = g["debt"].shift(1)
        g["pb_lag"] = g["primary_balance"].shift(1)
        out.append(g)
    panel = pd.concat(out, ignore_index=True)
    bund = panel.loc[panel["geo"] == "DE", ["year", "yield"]].set_index("year")["yield"]
    panel["spread"] = panel["yield"] - panel["year"].map(bund)
    return panel


def synthetic_panel(geos, years=range(1995, 2026), seed=5) -> pd.DataFrame:
    """Simulated panel with a known cubic reaction function and a debt-dependent spread (offline mode)."""
    rng = np.random.default_rng(seed)
    rows = []
    b = (0.12, -0.10, 0.02)                      # response to debt: rising, then fatigue above about 100% of GDP
    for geo in geos:
        mu = rng.normal(-0.02, 0.01)
        d = rng.uniform(0.3, 1.2)
        gap_prev = 0.0
        for year in years:
            gap = 0.6 * gap_prev + rng.normal(0, 0.015)
            growth = 0.012 + (gap - gap_prev) + rng.normal(0, 0.005)
            pb = mu + b[0] * d + b[1] * d ** 2 + b[2] * d ** 3 + 0.4 * gap + rng.normal(0, 0.008)
            post = year >= 2009
            spread = (0.2 + (0.5 + 2.5 * post) * d - 10 * pb + rng.normal(0, 0.3)) if geo != "DE" else 0.0
            rows.append({"geo": geo, "year": year, "debt": d, "primary_balance": pb, "interest": 0.03 * d,
                         "real_growth": growth, "nominal_gdp": 1e5, "gap": gap, "yield": 3.0 + spread})
            d = max(d * (1 + 0.035 - growth - 0.02) / (1 + growth) - pb, 0.05)
            gap_prev = gap
    panel = pd.DataFrame(rows)
    panel["balance"] = panel["primary_balance"] - panel["interest"]
    panel = panel.sort_values(["geo", "year"]).reset_index(drop=True)
    gaps = panel["gap"].copy()
    panel = _derived(panel)
    panel["gap"] = gaps                            # keep the true gap of the simulation
    panel.attrs["source"] = f"simulated panel (seed {seed}), not official data"
    return panel


# --------------------------------------------------------------------------- estimation


def within_regression(frame: pd.DataFrame, y: str, X: list[str], entity="geo", time="year", time_effects=False,
                      se="driscoll_kraay", lags=2) -> dict:
    """Fixed-effects (within) OLS of y on X, optionally with time effects (two-way demeaning is done by
    adding year dummies to the within regression, which is exact in unbalanced panels).

    Standard errors: "driscoll_kraay" (Newey-West over time of the cross-sectional sums of scores, `lags`
    lags), "cluster" (by entity, with the small-sample correction G/(G-1) (N-1)/(N-K)) or "classical".
    """
    cols = [y] + list(X) + [entity, time]
    df = frame[cols].dropna().copy()
    regressors = list(X)
    if time_effects:
        dummies = pd.get_dummies(df[time], prefix="year", drop_first=True, dtype=float)
        df = pd.concat([df, dummies], axis=1)
        regressors = regressors + list(dummies.columns)
    demeaned = df[[y] + regressors] - df.groupby(entity)[[y] + regressors].transform("mean")
    Y = demeaned[y].to_numpy()
    Z = demeaned[regressors].to_numpy()
    beta = np.linalg.lstsq(Z, Y, rcond=None)[0]
    u = Y - Z @ beta
    n, k = Z.shape
    groups = df[entity].to_numpy()
    n_groups = len(np.unique(groups))
    ZZi = np.linalg.pinv(Z.T @ Z)
    scores = Z * u[:, None]
    if se == "classical":
        cov = ZZi * (u @ u) / (n - k - n_groups)
    elif se == "cluster":
        g_sums = pd.DataFrame(scores).groupby(groups).sum().to_numpy()
        adj = n_groups / (n_groups - 1) * (n - 1) / (n - k)
        cov = adj * ZZi @ (g_sums.T @ g_sums) @ ZZi
    elif se == "driscoll_kraay":
        times = df[time].to_numpy()
        h = pd.DataFrame(scores, index=times).groupby(level=0).sum().sort_index()
        h = h.reindex(range(int(h.index.min()), int(h.index.max()) + 1), fill_value=0.0).to_numpy()
        S = h.T @ h
        for lag in range(1, lags + 1):
            w = 1 - lag / (lags + 1)
            G = h[lag:].T @ h[:-lag]
            S += w * (G + G.T)
        cov = ZZi @ S @ ZZi
    else:
        raise ValueError("se must be 'driscoll_kraay', 'cluster' or 'classical'")
    se_ = np.sqrt(np.diag(cov))
    fe = (df[y] - df[regressors].to_numpy() @ beta).groupby(df[entity]).mean()
    names = list(X)
    k_x = len(names)
    # average year effect (the omitted first year counts as zero), so that entity effect + average year
    # effect is the intercept of an average year
    n_years = df[time].nunique()
    mean_time_effect = float(beta[k_x:].sum() / n_years) if time_effects else 0.0
    return {"coef": pd.Series(beta[:k_x], index=names), "se": pd.Series(se_[:k_x], index=names),
            "t": pd.Series(beta[:k_x] / se_[:k_x], index=names), "cov": pd.DataFrame(cov[:k_x, :k_x], index=names, columns=names),
            "fixed_effects": fe, "time_coef": pd.Series(beta[k_x:], index=regressors[k_x:]),
            "mean_time_effect": mean_time_effect, "time_effects": time_effects,
            "r2_within": float(1 - u @ u / (Y @ Y)), "n": n, "groups": n_groups,
            "years": (int(df[time].min()), int(df[time].max())), "resid": pd.Series(u, index=df.index), "data": df}


def fiscal_reaction_panel(panel: pd.DataFrame, degree=3, time_effects=False, exclude_years=(), geos=None,
                          se="driscoll_kraay", lags=2) -> dict:
    """Fixed-effects fiscal reaction function with a polynomial in lagged debt (degree 1 or 3) and the gap."""
    df = panel if geos is None else panel[panel["geo"].isin(geos)]
    df = df[~df["year"].isin(list(exclude_years))].copy()
    names = []
    for p in range(1, degree + 1):
        name = "debt_lag" if p == 1 else f"debt_lag^{p}"
        df[name] = df["debt_lag"] ** p
        names.append(name)
    res = within_regression(df, "primary_balance", names + ["gap"], time_effects=time_effects, se=se, lags=lags)
    res["degree"] = degree
    return res


def reaction(res: dict, geo: str, debt, gap=0.0) -> np.ndarray:
    """Primary balance implied by a fitted reaction function for a country (its fixed effect) at given debt."""
    d = np.asarray(debt, dtype=float)
    pb = res["fixed_effects"][geo] + res["mean_time_effect"] + res["coef"]["gap"] * gap
    for p in range(1, res["degree"] + 1):
        pb = pb + res["coef"]["debt_lag" if p == 1 else f"debt_lag^{p}"] * d ** p
    return pb


def required_balance(debt, r, g, kappa=0.0, d0=0.0):
    """Primary balance that keeps the debt ratio constant: ((r(d) - g) / (1 + g)) d, r(d) = r + kappa (d - d0)."""
    d = np.asarray(debt, dtype=float)
    rate = r + kappa * (d - d0)
    return (rate - g) / (1 + g) * d


def debt_limit(pb_function, r, g, kappa=0.0, d0=0.0, grid=None) -> float:
    """Largest debt ratio at which the reaction function still reaches the debt-stabilising balance.

    Returns the upper crossing of pb(d) - required(d) from above to below on the grid (linear interpolation),
    +inf if the reaction stays above the line on the whole grid and NaN if it is below everywhere (no debt
    level is sustainable).
    """
    grid = np.linspace(0.0, 3.0, 3001) if grid is None else np.asarray(grid, dtype=float)
    gap = np.asarray(pb_function(grid)) - required_balance(grid, r, g, kappa, d0)
    above = gap >= 0
    if not above.any():
        return float("nan")
    last = np.flatnonzero(above)[-1]
    if last == grid.size - 1:
        return float("inf")
    x0, x1, y0, y1 = grid[last], grid[last + 1], gap[last], gap[last + 1]
    return float(x0 - y0 * (x1 - x0) / (y1 - y0))


def debt_limit_draws(res: dict, geo: str, r, g, kappa=0.0, d0=0.0, n_draws=5000, seed=1, grid=None,
                     kappa_se=0.0) -> np.ndarray:
    """Debt limits under parameter uncertainty: slope coefficients drawn from their asymptotic normal
    distribution, with the country effect recomputed from the within-estimator identity
    mu_i = mean_i(pb) - mean_i(X) b - mean_i(year effects) (year effects held at their estimates);
    `kappa_se` adds uncertainty on the spread elasticity."""
    rng = np.random.default_rng(seed)
    names = [c for c in res["coef"].index]
    draws = rng.multivariate_normal(res["coef"][names].to_numpy(), res["cov"].loc[names, names].to_numpy(), n_draws)
    df = res["data"]
    sub = df[df["geo"] == geo]
    means = sub[names].mean().to_numpy()
    mean_pb = sub["primary_balance"].mean()
    if res["time_effects"]:
        mean_pb = mean_pb - float((sub[list(res["time_coef"].index)].to_numpy() @ res["time_coef"].to_numpy()).mean())
        mean_pb = mean_pb + res["mean_time_effect"]
    kappas = kappa + kappa_se * rng.standard_normal(n_draws)
    out = np.empty(n_draws)
    grid = np.linspace(0.0, 3.0, 1501) if grid is None else grid
    idx_gap = names.index("gap")
    for j in range(n_draws):
        b = draws[j]
        fe = mean_pb - means @ b      # fixed effect consistent with the drawn slopes (within estimator)

        def f(d, b=b, fe=fe):
            pb = fe + 0.0 * b[idx_gap]
            for p in range(1, res["degree"] + 1):
                pb = pb + b[p - 1] * np.asarray(d) ** p
            return pb
        out[j] = debt_limit(f, r, g, kappas[j], d0, grid)
    return out


def spread_regression(panel: pd.DataFrame, geos=EURO_AREA_SPREAD, first_year=1999, break_year=2009, time_effects=True,
                      se="driscoll_kraay", lags=2) -> dict:
    """Euro-area spreads over the Bund (percentage points) on lagged debt, lagged primary balance and growth,
    with the debt slope allowed to change from `break_year` (country and optionally year effects)."""
    df = panel[panel["geo"].isin(geos) & (panel["year"] >= first_year)].copy()
    df["post"] = (df["year"] >= break_year).astype(float)
    df["debt_lag x post"] = df["debt_lag"] * df["post"]
    X = ["debt_lag", "debt_lag x post", "pb_lag", "real_growth"]
    if not time_effects:
        X = X + ["post"]
    res = within_regression(df, "spread", X, time_effects=time_effects, se=se, lags=lags)
    res["panel"] = df
    res["break_year"] = break_year
    return res


def fundamental_spread(res: dict, geo: str) -> pd.DataFrame:
    """Actual spread, the part explained by the regressors (with the country and year effects) and the residual."""
    df = res["data"]
    sub = df[df["geo"] == geo]
    resid = res["resid"].reindex(sub.index)
    out = pd.DataFrame({"actual": sub["spread"].to_numpy(), "fundamental": (sub["spread"] - resid).to_numpy(),
                        "residual": resid.to_numpy()}, index=sub["year"].to_numpy())
    out.index.name = "year"
    return out


def wald_test(res: dict, names, weights=None, value=0.0) -> dict:
    """Wald test of a linear combination w'b = value of the named coefficients."""
    names = list(names)
    w = np.ones(len(names)) if weights is None else np.asarray(weights, dtype=float)
    est = float(w @ res["coef"][names].to_numpy())
    var = float(w @ res["cov"].loc[names, names].to_numpy() @ w)
    z = (est - value) / np.sqrt(var)
    return {"estimate": est, "se": float(np.sqrt(var)), "z": float(z), "p_value": float(2 * stats.norm.sf(abs(z)))}
