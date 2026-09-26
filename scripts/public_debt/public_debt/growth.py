"""Growth accounting: where does (or does not) GDP per capita growth come from?

With Y real GDP, P population, W working-age population (15-64), E employment and H
hours worked, log growth of GDP per capita decomposes exactly as

    dln(Y/P) = dln(Y/H) + dln(H/E) + dln(E/W) + dln(W/P)
               productivity   hours per   employment   demographic
               per hour       worker      rate         structure

so weak productivity can be separated from labour-market and demographic effects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def decompose(lp: pd.DataFrame) -> pd.DataFrame:
    wap = lp["working_age_share"] * lp["population"]
    logs = pd.DataFrame({
        "GDP per capita": np.log(lp["real_gdp_index"] / lp["population"]),
        "productivity per hour": np.log(lp["real_gdp_index"] / lp["hours"]),
        "hours per worker": np.log(lp["hours"] / lp["employment"]),
        "employment rate (15-64)": np.log(lp["employment"] / wap),
        "working-age share": np.log(lp["working_age_share"]),
    })
    return logs.diff().dropna()


def average_by_period(dec: pd.DataFrame, periods: dict) -> pd.DataFrame:
    """Average annual contributions (percentage points) over named periods."""
    return pd.DataFrame({name: 100 * dec.loc[a:b].mean() for name, (a, b) in periods.items()}).T
