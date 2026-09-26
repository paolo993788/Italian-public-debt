# Italian Public Debt

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![C++](https://img.shields.io/badge/C%2B%2B-17-00599C?logo=cplusplus&logoColor=white)
![pybind11](https://img.shields.io/badge/bindings-pybind11-5C6BC0)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![Data](https://img.shields.io/badge/data-Eurostat%20%7C%20IMF-2E7D32)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**Why Italy's public debt is so high, how to read the public accounts, and what it would take to reduce the debt: an evidence-based analysis with official Eurostat and IMF data, Python notebooks and a C++ engine for stochastic debt sustainability.**

Italy's general government debt is around 135% of GDP, the second highest in the euro area. This repository reconstructs how it was built, measures the role of primary deficits, interest rates, growth and inflation, compares the structure of spending and revenues with Germany, France, Spain and the EU, analyses the macroeconomic and microeconomic causes of weak growth, and quantifies the options to put the debt ratio on a durably declining path.

## What the analysis shows

- **The debt was built mainly in the 1970s and 1980s.** Spending commitments (pensions, public employment, health, regional governments) grew without matching revenues; after the 1981 end of monetary financing, real interest rates rose above growth while primary deficits persisted for a decade. The ratio rose from about 57% of GDP in 1980 to about 120% in 1994.
- **The 1990s show that consolidation can work**: emergency budgets after the 1992 crisis, pension reforms, privatisations and primary surpluses, together with falling rates on the way to the euro, reduced the ratio.
- **The euro dividend was only partly saved**: in the 2000s lower interest spending was accompanied by an eroding primary surplus and weak growth.
- **Since 2008 the snowball has dominated**: Italy has run primary surpluses in most years before 2020, but recessions, low nominal growth and spread episodes pushed the ratio up; the pandemic and large building tax credits added deficits in 2020-2023.
- **Growth is the missing ingredient**: low productivity, low employment of women and young people, small firms, slow justice and administration, low R&D and population ageing weaken the denominator and the tax base.
- **The way out combines** a gradual but sustained primary surplus above the debt-stabilising level, better spending composition, a broader tax base with a lower tax wedge, growth-enhancing reforms and prudent debt management. Notebook 4 quantifies each lever and the adjustment needed for the debt to decline with high probability.

The figures for the years since 1995 are computed in the notebooks from Eurostat data; earlier figures are approximate values from the Bank of Italy literature cited in the notebooks.

## Catalogue

| Item | Question | Data |
| --- | --- | --- |
| [`scripts/public_debt`](scripts/public_debt/README.md) (library) | Debt accounting, fiscal analysis, growth accounting and a C++ engine for projections, fan charts and adjustment grids | Eurostat, IMF loaders |
| [1. Debt history and decomposition](notebooks/debt_dynamics/01_debt_history_and_decomposition.ipynb) | How was the debt built, which factors drove it in each period, and what if different choices had been made? | Eurostat EDP and national accounts, IMF WEO, optional Bank of Italy series since 1861 |
| [2. Reading the public accounts](notebooks/public_accounts/02_state_budget_analysis.ipynb) | Where does the money go and come from, compared with peers? How much of the deficit is structural? Has policy reacted to debt? | Eurostat government finance statistics (ESA 2010, COFOG) |
| [3. Macro and micro drivers](notebooks/growth_drivers/03_macro_micro_drivers.ipynb) | Why has Italy grown less, and what would closing the employment and productivity gaps be worth for the debt? | Eurostat national accounts, labour market, demography, R&D, bond yields |
| [4. Sustainability and policy options](notebooks/sustainability/04_debt_sustainability_and_policy_options.ipynb) | Where is the debt heading, how large an adjustment is needed, and which policy mix works best? | Eurostat, model-based scenarios |
| [Guide: how to read Italy's public accounts](docs/reading_public_accounts.md) | State budget versus general government, balances, budget cycle, data sources, analysis workflow, glossary | |

## Architecture

```text
notebooks/  ──►  public_debt (Python)                    ──►  public_debt._core (C++17, pybind11)
                 Eurostat and IMF loaders                     debt projection with repricing of the effective rate
                 debt decomposition, counterfactuals          stochastic DSA: VAR(1) shocks with bootstrap, fiscal reaction
                 HP output gap, structural balance, Bohn      fiscal-adjustment grids (probability of rising debt)
                 growth accounting, VAR(1), EU rules checks
```

## Getting started

Requirements: Python 3.10 or later and a C++17 compiler. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r scripts/public_debt/requirements.txt
python -m pip install -e scripts/public_debt
python -m pytest tests/public_debt
```

Open the notebooks in Visual Studio Code (extensions *Python*, *Jupyter* and *C/C++*) in numerical order and select the `.venv` environment as kernel. Official data are downloaded and cached on first use; `PUBLIC_DEBT_DATA_MODE=synthetic` runs them offline on random placeholder data.

## Repository layout

```text
.
├── scripts/public_debt/   C++ engine (cpp/), Python package, build and dependency files
├── notebooks/             debt_dynamics/, public_accounts/, growth_drivers/, sustainability/
├── docs/                  guide to the public accounts, project template, publishing workflow
├── tests/public_debt/     validation suite (pytest)
├── data/                  download cache and optional external series (ignored by Git)
└── outputs/               generated figures and tables (ignored by Git)
```

## Principles

- **Official data first**: Eurostat, ISTAT, Bank of Italy, MEF, European Commission, IMF; every dataset, perimeter and vintage is stated.
- **Facts, estimates and judgements are kept apart**: numbers computed from data, estimates from the literature (with sources) and policy assessments are labelled as such. The analysis is non-partisan: it evaluates policies by their measurable effects.
- **Reproducible and tested**: accounting identities and limiting cases are tested; simulations use fixed seeds.

## Development workflow

Changes follow the [publishing workflow](docs/publishing.md). The [`CLAUDE.md`](CLAUDE.md) file provides project instructions for [Claude Code](https://claude.com/claude-code).

## Disclaimer

Research and educational material. Projections depend on stated assumptions and are not official forecasts.

## License

Released under the [MIT License](LICENSE).
