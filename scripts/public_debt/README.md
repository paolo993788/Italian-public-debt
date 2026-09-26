# Public debt: accounting, fiscal analysis and C++ debt sustainability

Python package with a C++17 engine (pybind11) to analyse Italy's public debt: debt-dynamics decomposition and counterfactuals, cyclically adjusted balances and fiscal reaction functions, growth accounting, deterministic projections and a stochastic debt sustainability analysis (Monte Carlo fan charts and fiscal-adjustment grids). It downloads official data from Eurostat and the IMF.

## Requirements

- Python 3.10 or later (developed and tested with Python 3.11).
- A C++17 compiler: Visual Studio Build Tools ("Desktop development with C++") on Windows, Xcode Command Line Tools on macOS, GCC 9+ or Clang 10+ on Linux.
- Python dependencies: [`requirements.txt`](requirements.txt).

## Usage

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r scripts/public_debt/requirements.txt
python -m pip install -e scripts/public_debt
python -m pytest tests/public_debt
python -m public_debt.data --geo IT   # optional: pre-download the Eurostat datasets
```

In Visual Studio Code, install the *Python*, *Jupyter* and *C/C++* extensions, select the `.venv` interpreter and use it as the notebook kernel. Set `PUBLIC_DEBT_DATA_MODE=synthetic` to run the notebooks offline on random placeholder data.

## Inputs

| Name | Source | Content |
| --- | --- | --- |
| `gov_10dd_edpt1` | Eurostat | EDP gross debt (GD), net lending/borrowing (B9), interest (D41PAY), % of GDP, general government, from 1995 |
| `nama_10_gdp` | Eurostat | GDP at current prices (CP_MEUR) and real growth (CLV_PCH_PRE) |
| `gov_10a_main`, `gov_10a_exp` | Eurostat | Revenue and expenditure by ESA 2010 item and by COFOG function, % of GDP |
| `irt_lt_mcby_a` | Eurostat | 10-year government bond yields (convergence criterion) |
| `nama_10_pe`, `nama_10_a10_e`, `demo_pjanind`, `lfsi_emp_a`, `rd_e_gerdtot` | Eurostat | Population, employment, hours worked, working-age share (100 minus the shares aged 0-14 and 65+), employment rates, old-age dependency, R&D |
| `GGXWDG_NGDP` | IMF DataMapper (World Economic Outlook) | Gross debt, % of GDP (for Italy from 1988, with projections) |
| `data/external/debt_1861.csv` (optional) | User-provided, for example the Bank of Italy series of Francese and Pace (2008) | Columns `year,debt_pct`; read if present, never downloaded or committed |

Downloads are cached in `data/raw/` (ignored by Git); `PUBLIC_DEBT_DATA_DIR` changes the base folder. Eurostat and IMF data may be reused with acknowledgement of the source. Codes are selected after download; if Eurostat renames a code, the error message lists the available ones.

## Outputs

Figures and tables in `outputs/debt_history/`, `outputs/public_accounts/`, `outputs/growth_drivers/` and `outputs/sustainability/`.

The README charts are drawn by `python -m public_debt.readme_figures` (official data; `--synthetic` for an offline check) and saved in a light and a dark variant in `docs/figures/`, the only generated files committed to the repository.

## Method

**Units.** Ratios are fractions of GDP and rates decimals in the code; charts and tables show percentages.

**Debt decomposition** (`public_debt/accounting.py`): $d_t - d_{t-1} = -pb_t + d_{t-1}(i_t-\gamma_t)/(1+\gamma_t) + sfa_t$, with the snowball split into interest $d_{t-1}i_t/(1+\gamma_t)$, real growth $-d_{t-1}g_t/(1+\gamma_t)$ and inflation $-d_{t-1}\pi_t(1+g_t)/(1+\gamma_t)$ effects (European Commission convention). The effective rate is interest paid over the previous year's debt, $i_t = \text{int}_t(1+\gamma_t)/d_{t-1}$; the stock-flow adjustment is the residual. Counterfactuals replay the identity with modified components and observed stock-flow adjustments.

**Fiscal analysis** (`public_debt/fiscal.py`): Hodrick-Prescott output gap ($\lambda = 100$), cyclically adjusted balance with semi-elasticity 0.55, fiscal stance as the change in the cyclically adjusted primary balance, Bohn (1998) fiscal reaction function with Newey-West standard errors, optional indicator variables for exceptional years and sample restrictions.

**Growth accounting** (`public_debt/growth.py`): exact log decomposition of GDP per capita growth into productivity per hour, hours per worker, employment rate and working-age share.

**Debt engine** (`cpp/debt_dynamics.hpp`, `public_debt/dsa.py`): the effective rate reprices gradually, $i_t = (1-s)\,i_{t-1} + s\,r_t$, with $s$ the share of debt refinanced each year. The stochastic analysis adds to the baseline deviations $u_t = A u_{t-1} + e_t$ of real growth, inflation and the 10-year rate, with $A$ estimated by a VAR(1) (`public_debt/var.py`) and $e_t$ resampled from the historical residual vectors; the primary balance responds to growth surprises ($\varepsilon$) and optionally to debt ($\rho$). Each path has its own random stream, so results do not depend on the number of threads. The adjustment grid computes, for plans of different size and length, the probability that the debt ratio is higher at a target year. Fiscal multipliers can be added to consolidation scenarios.

**EU rules** (`dsa.eu_rules_check`): simplified checks inspired by the 2024 framework (3% deficit, average debt decline of 1 point a year above 90% of GDP, 1.5% resilience margin, declining debt after the adjustment).

## Verification

Run `python -m pytest tests/public_debt` (20 tests, about 10 seconds):

| Check | Tolerance |
| --- | --- |
| C++ projection vs the Python identity, including the repricing of the effective rate | relative $10^{-13}$ |
| The debt-stabilising primary balance keeps the ratio constant | relative $10^{-12}$ |
| Stochastic engine without shocks equals the deterministic projection on every path | relative $10^{-13}$ |
| Fiscal reaction reduces the dispersion; results independent of the number of threads; adjustment grid monotone | exact |
| Decomposition closes the identity; stock-flow adjustments of synthetic data recovered exactly | $10^{-12}$ to $10^{-15}$ |
| Counterfactual without changes reproduces history; one point more of primary balance lowers next year's debt by one point | $10^{-12}$ |
| HP filter limits (a line is its own trend; no smoothing as lambda goes to 0); OLS and White/Newey-West standard errors | $10^{-8}$ to $10^{-12}$ |
| Fiscal reaction and VAR(1) recover known parameters from simulated data; an indicator variable absorbs an exceptional shift without biasing the debt response | 0.005-0.1 (sampling error) |
| Growth decomposition is exact | $10^{-14}$ |
| Eurostat JSON-stat and IMF parsers; offline assembly of the fiscal dataset from cached files | exact |

## References

- Balassone, F., Francese, M. and Pace, A. (2013). Public debt and economic growth: Italy's first 150 years. *The Oxford Handbook of the Italian Economy since Unification*.
- Blanchard, O. (2019). Public debt and low interest rates. *American Economic Review*, 109(4), 1197-1229.
- Blanchard, O. and Leigh, D. (2013). Growth forecast errors and fiscal multipliers. *American Economic Review*, 103(3), 117-120.
- Bohn, H. (1998). The behavior of U.S. public debt and deficits. *Quarterly Journal of Economics*, 113(3), 949-963.
- European Commission. *Debt Sustainability Monitor*; Regulation (EU) 2024/1263.
- Francese, M. and Pace, A. (2008). Il debito pubblico italiano dall'Unità a oggi. Banca d'Italia, Questioni di Economia e Finanza 31.
- IMF (2021). Review of the Debt Sustainability Framework for Market Access Countries.
- Mourre, G., Poissonnier, A. and Lausegger, M. (2019). The semi-elasticities underlying the cyclically-adjusted budget balance. European Commission Discussion Paper 098.
- Blackman, D. and Vigna, S. (2021). Scrambled linear pseudorandom number generators. *ACM TOMS*, 47(4) (public-domain xoshiro256** reference code).
