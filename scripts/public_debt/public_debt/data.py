"""Official data on public finances and the macroeconomy.

Sources (free reuse with acknowledgement of the source):

* **Eurostat** dissemination API, JSON-stat format
  (https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>):
  - ``gov_10dd_edpt1``  government deficit and debt notified under the excessive
    deficit procedure (EDP): gross debt (GD), net lending/borrowing (B9),
    interest (D41PAY), % of GDP, general government (S13), from 1995;
  - ``nama_10_gdp``     GDP at current prices and real growth;
  - ``gov_10a_main``    revenue and expenditure of general government by ESA 2010 item;
  - ``gov_10a_exp``     expenditure by function (COFOG);
  - ``irt_lt_mcby_a``   10-year government bond yields (Maastricht criterion);
  - ``nama_10_pe``      population and employment (national accounts);
  - ``nama_10_a10_e``   hours worked by employed persons (all industries);
  - ``demo_pjanind``    population structure indicators (old-age dependency, share aged 15-64);
  - ``lfsi_emp_a``      employment rates;  ``rd_e_gerdtot`` R&D expenditure.
* **IMF DataMapper** API (https://www.imf.org/external/datamapper/api/v1/<indicator>/<country>),
  World Economic Outlook series such as GGXWDG_NGDP (gross debt, % of GDP; for Italy from 1988).
* **Optional long-run series**: a CSV placed in ``data/external/`` with the historical
  debt ratio since 1861 published by the Bank of Italy (Francese and Pace, 2008), columns
  ``year,debt_pct``. It is read if present and never downloaded automatically.

Downloads are cached in ``data/raw/`` (ignored by Git); ``PUBLIC_DEBT_DATA_DIR`` changes
the base folder. Dataset and item codes are selected after download, and a missing code
raises an error that lists the available ones, so that changes in the source are easy to fix.

Units: fiscal ratios are returned as fractions of GDP (0.05 = 5%) and rates as decimals.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?{query}"
IMF_URL = "https://www.imf.org/external/datamapper/api/v1/{indicator}/{countries}"
USER_AGENT = "public-debt/0.1 (research scripts; https://github.com/paolo993788/Italian-public-debt)"
PEERS = ("IT", "DE", "FR", "ES", "EU27_2020")


def repository_root() -> Path:
    for base in (Path.cwd(), *Path.cwd().parents):
        if (base / "scripts" / "public_debt").is_dir():
            return base
    return Path(__file__).resolve().parents[3]


def cache_dir(source: str) -> Path:
    env = os.environ.get("PUBLIC_DEBT_DATA_DIR")
    path = (Path(env) if env else repository_root() / "data" / "raw") / source
    path.mkdir(parents=True, exist_ok=True)
    return path


def download(url: str, destination: Path, timeout: float = 120.0) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.write_bytes(payload)
    tmp.replace(destination)
    return destination


# --------------------------------------------------------------------------- Eurostat


def parse_jsonstat(obj: dict) -> pd.DataFrame:
    """Convert a JSON-stat 2.0 dataset into a long table (one column per dimension + value)."""
    dims, sizes = obj["id"], obj["size"]
    codes = []
    for dim in dims:
        index = obj["dimension"][dim]["category"]["index"]
        if isinstance(index, list):
            codes.append(index)
        else:
            ordered = [None] * len(index)
            for code, pos in index.items():
                ordered[pos] = code
            codes.append(ordered)
    values = obj["value"]
    pairs = ([(int(k), v) for k, v in values.items() if v is not None] if isinstance(values, dict)
             else [(i, v) for i, v in enumerate(values) if v is not None])
    flat = np.array([i for i, _ in pairs], dtype=np.int64)
    strides = np.cumprod([1] + sizes[::-1])[:-1][::-1]
    table = {dim: np.asarray(labels, dtype=object)[(flat // stride) % size]
             for dim, stride, size, labels in zip(dims, strides, sizes, codes)}
    table["value"] = np.array([v for _, v in pairs], dtype=float)
    return pd.DataFrame(table)


def eurostat_cache_path(dataset: str, **filters) -> Path:
    tag = "_".join(f"{k}-{'+'.join(v) if isinstance(v, (list, tuple)) else v}" for k, v in sorted(filters.items()))
    return cache_dir("eurostat") / f"{dataset}_{tag}.json"


def eurostat(dataset: str, refresh=False, **filters) -> pd.DataFrame:
    """Download (or read from cache) a Eurostat dataset; list-valued filters select several codes."""
    params = [("format", "JSON"), ("lang", "EN")]
    for key, value in sorted(filters.items()):
        for v in (value if isinstance(value, (list, tuple)) else [value]):
            params.append((key, v))
    path = eurostat_cache_path(dataset, **filters)
    if refresh or not path.exists():
        download(EUROSTAT_URL.format(dataset=dataset, query=urllib.parse.urlencode(params)), path)
    frame = parse_jsonstat(json.loads(path.read_text(encoding="utf-8")))
    frame["year"] = pd.to_numeric(frame["time"].str[:4], errors="coerce").astype("Int64")
    frame.attrs["source"] = f"Eurostat, {dataset}"
    return frame


def select(frame: pd.DataFrame, **codes) -> pd.DataFrame:
    """Rows matching dimension codes; a missing code raises an error listing the available ones."""
    out = frame
    for dim, code in codes.items():
        wanted = code if isinstance(code, (list, tuple)) else [code]
        available = sorted(out[dim].dropna().unique())
        missing = [c for c in wanted if c not in available]
        if missing:
            raise KeyError(f"{dim}={missing} not found in {frame.attrs.get('source', 'dataset')}; "
                           f"available: {available[:60]}")
        out = out[out[dim].isin(wanted)]
    return out


def _series(frame, **codes) -> pd.Series:
    return select(frame, **codes).set_index("year")["value"].sort_index().astype(float)


def fiscal_dataset(geo="IT", refresh=False) -> pd.DataFrame:
    """Annual debt, balance, interest, growth and inflation for one country (fractions and decimals).

    Columns: debt, balance, interest, primary_balance (= balance + interest), real_growth,
    nominal_growth, inflation (GDP deflator), nominal_gdp (EUR million), effective_rate
    (interest paid over the previous year's debt).
    """
    edp = eurostat("gov_10dd_edpt1", refresh, geo=geo, unit="PC_GDP", sector="S13")
    gdp = eurostat("nama_10_gdp", refresh, geo=geo, na_item="B1GQ")
    out = pd.DataFrame({
        "debt": _series(edp, na_item="GD") / 100,
        "balance": _series(edp, na_item="B9") / 100,
        "interest": _series(edp, na_item="D41PAY") / 100,
    })
    nominal = _series(gdp, unit="CP_MEUR")
    real_growth = _series(gdp, unit="CLV_PCH_PRE") / 100
    out["nominal_gdp"] = nominal
    out["nominal_growth"] = nominal.pct_change()
    out["real_growth"] = real_growth
    out["inflation"] = (1 + out["nominal_growth"]) / (1 + out["real_growth"]) - 1
    out["primary_balance"] = out["balance"] + out["interest"]
    out["effective_rate"] = out["interest"] * (1 + out["nominal_growth"]) / out["debt"].shift(1)
    out = out.dropna(subset=["debt"]).sort_index()
    out.index = out.index.astype(int)
    out.index.name = "year"
    out.attrs["source"] = f"Eurostat gov_10dd_edpt1 and nama_10_gdp, geo={geo}"
    return out


def government_accounts(geos=PEERS, refresh=False) -> pd.DataFrame:
    """Revenue and expenditure items of general government, % of GDP (long format: geo, item, year, value)."""
    frame = eurostat("gov_10a_main", refresh, geo=list(geos), unit="PC_GDP", sector="S13")
    out = frame.rename(columns={"na_item": "item"})[["geo", "item", "year", "value"]].dropna()
    out.attrs["source"] = "Eurostat gov_10a_main"
    return out


def cofog_expenditure(geos=PEERS, refresh=False) -> pd.DataFrame:
    """Total expenditure by COFOG function, % of GDP (long format: geo, cofog, year, value)."""
    frame = eurostat("gov_10a_exp", refresh, geo=list(geos), unit="PC_GDP", sector="S13", na_item="TE")
    out = frame.rename(columns={"cofog99": "cofog"})[["geo", "cofog", "year", "value"]].dropna()
    out.attrs["source"] = "Eurostat gov_10a_exp"
    return out


def bond_yields(geos=PEERS, refresh=False) -> pd.DataFrame:
    """Annual 10-year government bond yields (Maastricht criterion), percent, years x countries."""
    frame = eurostat("irt_lt_mcby_a", refresh, geo=[g for g in geos if not g.startswith("EU")])
    out = frame.pivot_table(index="year", columns="geo", values="value", aggfunc="last")
    out.index = out.index.astype(int)
    out.attrs["source"] = "Eurostat irt_lt_mcby_a"
    return out


def labour_and_population(geo="IT", refresh=False) -> pd.DataFrame:
    """Population, employment, hours worked, working-age share and real GDP index for growth accounting."""
    pe = eurostat("nama_10_pe", refresh, geo=geo)
    hw = eurostat("nama_10_a10_e", refresh, geo=geo, nace_r2="TOTAL", na_item="EMP_DC", unit="THS_HW")
    ind = eurostat("demo_pjanind", refresh, geo=geo)
    gdp = eurostat("nama_10_gdp", refresh, geo=geo, na_item="B1GQ")
    out = pd.DataFrame({
        "population": _series(pe, na_item="POP_NC", unit="THS_PER"),
        "employment": _series(pe, na_item="EMP_DC", unit="THS_PER"),
        "hours": _series(hw, na_item="EMP_DC", unit="THS_HW"),
        # share of the population aged 15-64 (the dataset publishes the 0-14 and 65+ shares)
        "working_age_share": 1 - (_series(ind, indic_de="PC_Y0_14") + _series(ind, indic_de="PC_Y65_MAX")) / 100,
    })
    growth = _series(gdp, unit="CLV_PCH_PRE") / 100
    out["real_gdp_index"] = (1 + growth.reindex(out.index).fillna(0)).cumprod()
    out = out.dropna()
    out.index = out.index.astype(int)
    out.attrs["source"] = f"Eurostat nama_10_pe, nama_10_a10_e, demo_pjanind, nama_10_gdp, geo={geo}"
    return out


def structural_indicators(geos=PEERS, refresh=False) -> dict:
    """Employment rate 20-64 (total and women), old-age dependency ratio and R&D intensity (percent)."""
    emp = eurostat("lfsi_emp_a", refresh, geo=list(geos), indic_em="EMP_LFS", age="Y20-64", unit="PC_POP")
    dep = eurostat("demo_pjanind", refresh, geo=list(geos), indic_de="OLDDEP1")
    rd = eurostat("rd_e_gerdtot", refresh, geo=list(geos), sectperf="TOTAL", unit="PC_GDP")

    def wide(frame, **codes):
        f = select(frame, **codes) if codes else frame
        w = f.pivot_table(index="year", columns="geo", values="value", aggfunc="last")
        w.index = w.index.astype(int)
        return w

    return {"employment_rate": wide(emp, sex="T"), "female_employment_rate": wide(emp, sex="F"),
            "old_age_dependency": wide(dep), "rd_intensity": wide(rd)}


# --------------------------------------------------------------------------- IMF and historical series


def imf_series(indicator: str, country="ITA", refresh=False) -> pd.Series:
    """One IMF DataMapper series (World Economic Outlook and other datasets) by year."""
    path = cache_dir("imf") / f"{indicator}_{country}.json"
    if refresh or not path.exists():
        download(IMF_URL.format(indicator=indicator, countries=country), path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("values", {}).get(indicator, {}).get(country)
    if not values:
        raise KeyError(f"IMF DataMapper returned no data for {indicator}/{country}")
    s = pd.Series({int(k): float(v) for k, v in values.items() if v is not None}).sort_index()
    s.index.name = "year"
    s.attrs["source"] = f"IMF DataMapper, {indicator}"
    return s


def historical_debt(path=None) -> pd.Series | None:
    """Long-run debt ratio (percent of GDP) from a user-provided CSV with columns year, debt_pct."""
    path = Path(path) if path else repository_root() / "data" / "external" / "debt_1861.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    s = frame.set_index("year")["debt_pct"].astype(float).sort_index()
    s.attrs["source"] = f"user-provided file {path.name} (for example Bank of Italy, Francese and Pace, 2008)"
    return s


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download the official datasets used by the notebooks.")
    parser.add_argument("--geo", default="IT")
    args = parser.parse_args(argv)
    fiscal = fiscal_dataset(args.geo, refresh=True)
    print(f"Fiscal dataset {args.geo}: {fiscal.index.min()}-{fiscal.index.max()}")
    government_accounts(refresh=True)
    cofog_expenditure(refresh=True)
    bond_yields(refresh=True)
    labour_and_population(args.geo, refresh=True)
    structural_indicators(refresh=True)
    print(f"Eurostat datasets cached in {cache_dir('eurostat')}")


if __name__ == "__main__":
    main()
