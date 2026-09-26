"""Debt sustainability analysis: scenarios, projections, fan charts and fiscal rules.

Scenario paths are annual and expressed in decimals (growth, inflation, market rate)
or fractions of GDP (primary balance, stock-flow adjustment). The heavy lifting
(Monte Carlo fan charts and adjustment grids) is done by the C++ engine.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from . import require_cpp
from .var import VAR1


@dataclass(frozen=True)
class Scenario:
    years: tuple
    growth: tuple
    inflation: tuple
    market_rate: tuple
    primary_balance: tuple
    sfa: tuple

    @classmethod
    def constant(cls, first_year, horizon, growth, inflation, market_rate, primary_balance, sfa=0.0):
        n = horizon
        return cls(tuple(range(first_year, first_year + n)), (growth,) * n, (inflation,) * n, (market_rate,) * n,
                   (primary_balance,) * n, (sfa,) * n)

    def shifted(self, **deltas) -> "Scenario":
        """Add constant (or per-year) changes to some paths."""
        changes = {}
        for name, delta in deltas.items():
            base = np.asarray(getattr(self, name), dtype=float)
            changes[name] = tuple(base + np.broadcast_to(np.asarray(delta, dtype=float), base.shape))
        return replace(self, **changes)

    def with_adjustment(self, annual_step, years_of_adjustment) -> "Scenario":
        """Primary balance improved by `annual_step` each year for `years_of_adjustment` years, then kept."""
        steps = annual_step * np.minimum(np.arange(1, len(self.years) + 1), years_of_adjustment)
        return self.shifted(primary_balance=steps)

    def arrays(self):
        return [np.asarray(getattr(self, k), dtype=float) for k in ("growth", "inflation", "market_rate", "primary_balance", "sfa")]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({k: getattr(self, k) for k in ("growth", "inflation", "market_rate", "primary_balance", "sfa")},
                            index=pd.Index(self.years, name="year"))


def project(d0, i0, refinancing_share, scenario: Scenario) -> pd.DataFrame:
    core = require_cpp()
    out = core.project(d0, i0, refinancing_share, *scenario.arrays())
    frame = scenario.to_frame()
    for key in ("debt", "effective_rate", "interest", "snowball"):
        frame[key] = out[key]
    frame["overall balance"] = frame["primary_balance"] - frame["interest"]
    return frame


def stochastic(d0, i0, refinancing_share, scenario: Scenario, var: VAR1, u0=None, epsilon=0.5, rho=0.0, sigma_pb=0.0,
               n_paths=100_000, seed=12345, n_threads=0) -> dict:
    """Fan chart of the debt ratio: percentiles by year and probability of a higher debt ratio."""
    core = require_cpp()
    u0 = np.zeros(3) if u0 is None else np.asarray(u0, dtype=float)
    out = core.stochastic_dsa(d0, i0, refinancing_share, *scenario.arrays(), var.A, var.residuals, u0, epsilon, rho,
                              sigma_pb, n_paths, seed, n_threads)
    debt = out["debt"]
    pct = pd.DataFrame(np.percentile(debt, [5, 10, 25, 50, 75, 90, 95], axis=0).T, index=pd.Index(scenario.years, name="year"),
                       columns=["p5", "p10", "p25", "p50", "p75", "p90", "p95"])
    return {"paths": debt, "interest": out["interest"], "percentiles": pct,
            "prob_higher_than_start": pd.Series((debt > d0).mean(axis=0), index=pct.index)}


def adjustment_grid(d0, i0, refinancing_share, scenario: Scenario, var: VAR1, annual_steps, adjustment_years,
                    reference_year, target_year, u0=None, epsilon=0.5, rho=0.0, sigma_pb=0.0, n_paths=20_000, seed=12345):
    """Probability that debt in `target_year` exceeds debt in `reference_year` for each adjustment plan."""
    core = require_cpp()
    years = list(scenario.years)
    ref = -1 if reference_year is None else years.index(reference_year)
    u0 = np.zeros(3) if u0 is None else np.asarray(u0, dtype=float)
    grid = core.adjustment_grid(d0, i0, refinancing_share, *scenario.arrays(), var.A, var.residuals, u0, epsilon, rho,
                                sigma_pb, np.asarray(annual_steps, dtype=float), [int(y) for y in adjustment_years], ref,
                                years.index(target_year), n_paths, seed, 0)
    return pd.DataFrame(grid, index=pd.Index(annual_steps, name="annual improvement of the primary balance"),
                        columns=pd.Index(adjustment_years, name="years of adjustment"))


def with_fiscal_multiplier(scenario: Scenario, annual_step, years_of_adjustment, multiplier=0.8, gap_persistence=0.5,
                           epsilon=0.5) -> Scenario:
    """Consolidation that lowers output in the short run.

    Each year's tightening d_pb reduces the output gap by `multiplier * d_pb`; the gap
    closes at rate (1 - gap_persistence). Growth falls by the change in the gap and
    automatic stabilisers give back epsilon * gap of the primary balance.
    """
    n = len(scenario.years)
    tightening = annual_step * (np.arange(1, n + 1) <= years_of_adjustment)
    gap = np.zeros(n)
    prev = 0.0
    for t in range(n):
        gap[t] = gap_persistence * prev - multiplier * tightening[t]
        prev = gap[t]
    growth_change = np.diff(np.r_[0.0, gap])
    adjusted = scenario.with_adjustment(annual_step, years_of_adjustment)
    return adjusted.shifted(growth=growth_change, primary_balance=epsilon * gap)


def eu_rules_check(projection: pd.DataFrame, start_debt, adjustment_end_year) -> pd.Series:
    """Headline checks inspired by the 2024 EU economic governance framework.

    - deficit below the 3% of GDP reference value by the end of the adjustment period;
    - debt sustainability safeguard: for debt above 90% of GDP, an average decline of at
      least 1 percentage point per year over the adjustment period;
    - deficit resilience safeguard: deficit at or below 1.5% of GDP (the framework refers to
      the structural balance; with a closed output gap the two coincide);
    - debt on a declining path over the ten years after the adjustment.
    Illustrative only: the official assessment uses the Commission's full methodology.
    """
    p = projection
    horizon_years = p.loc[:adjustment_end_year].index
    avg_decline = (start_debt - p.loc[adjustment_end_year, "debt"]) / len(horizon_years)
    after = p.loc[adjustment_end_year:, "debt"]
    return pd.Series({
        "deficit <= 3% at end of adjustment": -p.loc[adjustment_end_year, "overall balance"] <= 0.03,
        "average debt decline >= 1 pp per year": avg_decline >= 0.01 if start_debt > 0.9 else True,
        "deficit <= 1.5% (resilience)": -p.loc[adjustment_end_year, "overall balance"] <= 0.015,
        "debt declining after adjustment": bool(after.iloc[-1] < after.iloc[0]),
        "average annual debt change during adjustment (pp)": -100 * avg_decline,
    })
