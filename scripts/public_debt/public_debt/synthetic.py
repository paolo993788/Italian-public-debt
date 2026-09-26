"""Synthetic stand-ins for the official data, used by the tests and by the notebooks'
offline mode (PUBLIC_DEBT_DATA_MODE=synthetic).

The series have plausible orders of magnitude but are randomly generated: they are
not statistics about Italy or any other country and must not be interpreted as such.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import PEERS

LABEL = "synthetic data (random, for offline testing only; not official statistics)"
MAIN_ITEMS = {  # item: typical level in % of GDP for the synthetic generator
    "TE": 50.0, "TR": 46.0, "D41PAY": 4.0, "P51G": 2.8, "D1PAY": 10.0, "P2": 5.5, "D62PAY": 20.0, "D632PAY": 2.5,
    "D3PAY": 1.5, "D2REC": 14.5, "D5REC": 14.0, "D61REC": 13.0, "D91REC": 0.2,
}
COFOG = {"GF01": 8.0, "GF02": 1.2, "GF03": 1.9, "GF04": 4.0, "GF05": 0.9, "GF06": 0.6, "GF07": 7.0, "GF08": 0.8,
         "GF09": 4.0, "GF10": 21.0, "GF1001": 1.8, "GF1002": 13.5, "GF1003": 2.5, "GF1004": 1.2, "GF1005": 1.0}


def fiscal_dataset(first=1995, last=2024, seed=5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    years = np.arange(first, last + 1)
    n = years.size
    g = 0.01 + 0.015 * rng.standard_normal(n)
    pi = 0.02 + 0.008 * rng.standard_normal(n)
    pb = 0.01 + 0.015 * rng.standard_normal(n)
    sfa = 0.003 * rng.standard_normal(n)
    rate = np.clip(0.06 - 0.0015 * np.arange(n) + 0.004 * rng.standard_normal(n), 0.015, None)
    d, i = [1.1], 0.08
    interest, eff = [], []
    for t in range(n):
        i = 0.85 * i + 0.15 * rate[t]
        gamma = (1 + g[t]) * (1 + pi[t]) - 1
        interest.append(d[-1] * i / (1 + gamma))
        eff.append(i)
        d.append(d[-1] * (1 + i) / (1 + gamma) - pb[t] + sfa[t])
    f = pd.DataFrame({"debt": d[1:], "interest": interest, "primary_balance": pb, "real_growth": g, "inflation": pi},
                     index=pd.Index(years, name="year"))
    f["balance"] = f["primary_balance"] - f["interest"]
    f["nominal_growth"] = (1 + g) * (1 + pi) - 1
    f["nominal_gdp"] = 1.0e6 * np.cumprod(1 + f["nominal_growth"])
    f["effective_rate"] = eff
    f.attrs["source"] = LABEL
    return f


def government_accounts(geos=PEERS, first=1995, last=2024, seed=6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for geo in geos:
        shift = rng.normal(0, 2.0)
        for item, level in MAIN_ITEMS.items():
            base = level * (1 + 0.08 * rng.standard_normal())
            for year in range(first, last + 1):
                rows.append((geo, item, year, max(base + 0.3 * rng.standard_normal() + (shift if item in ("TE", "TR") else 0), 0)))
        for year in range(first, last + 1):
            te = next(r[3] for r in rows if r[0] == geo and r[1] == "TE" and r[2] == year)
            tr = next(r[3] for r in rows if r[0] == geo and r[1] == "TR" and r[2] == year)
            rows.append((geo, "B9", year, tr - te))
    out = pd.DataFrame(rows, columns=["geo", "item", "year", "value"])
    out.attrs["source"] = LABEL
    return out


def cofog_expenditure(geos=PEERS, first=2001, last=2023, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = [(geo, code, year, max(level * (1 + 0.15 * rng.standard_normal()), 0.05))
            for geo in geos for code, level in COFOG.items() for year in range(first, last + 1)]
    out = pd.DataFrame(rows, columns=["geo", "cofog", "year", "value"])
    out.attrs["source"] = LABEL
    return out


def bond_yields(geos=("IT", "DE", "FR", "ES"), first=1995, last=2024, seed=8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    years = np.arange(first, last + 1)
    base = np.clip(7.0 - 0.25 * (years - first) + 0.5 * rng.standard_normal(years.size), 0.0, None)
    out = pd.DataFrame({g: base + (0.0 if g == "DE" else abs(rng.normal(1.0, 0.6))) + 0.2 * rng.standard_normal(years.size)
                        for g in geos}, index=pd.Index(years, name="year"))
    out.attrs["source"] = LABEL
    return out


def labour_and_population(first=1995, last=2024, seed=9) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    years = np.arange(first, last + 1)
    n = years.size
    pop = 57_000 * np.cumprod(1 + 0.002 + 0.001 * rng.standard_normal(n))
    emp = 22_000 * np.cumprod(1 + 0.004 + 0.01 * rng.standard_normal(n))
    hours = emp * 1.75 * np.cumprod(1 - 0.002 + 0.003 * rng.standard_normal(n))
    share = 0.67 - 0.002 * np.arange(n)
    gdp = np.cumprod(1 + 0.007 + 0.015 * rng.standard_normal(n))
    out = pd.DataFrame({"population": pop, "employment": emp, "hours": hours, "working_age_share": share,
                        "real_gdp_index": gdp}, index=pd.Index(years, name="year"))
    out.attrs["source"] = LABEL
    return out


def structural_indicators(geos=PEERS, first=2000, last=2024, seed=10) -> dict:
    rng = np.random.default_rng(seed)
    years = pd.Index(np.arange(first, last + 1), name="year")

    def panel(level, spread, trend):
        return pd.DataFrame({g: level + rng.normal(0, spread) + trend * np.arange(years.size) + rng.normal(0, 0.3, years.size)
                             for g in geos}, index=years)

    return {"employment_rate": panel(68, 4, 0.2), "female_employment_rate": panel(60, 6, 0.3),
            "old_age_dependency": panel(30, 3, 0.4), "rd_intensity": panel(1.8, 0.6, 0.01)}
