# Public debt: accounting, fiscal analysis and C++ debt sustainability

Python package with a C++17 engine (pybind11) to analyse Italy's public debt: debt-dynamics decomposition and counterfactuals, cyclically adjusted balances and fiscal reaction functions, growth accounting, deterministic projections, a stochastic debt sustainability analysis (Monte Carlo fan charts and fiscal-adjustment grids), and panel estimates of fiscal fatigue, debt limits and sovereign spreads. It downloads official data from Eurostat and the IMF.

## Requirements

- Python 3.10 or later (developed and tested with Python 3.11).
- A C++17 compiler: Visual Studio Build Tools ("Desktop development with C++") on Windows, Xcode Command Line Tools on macOS, GCC 9+ or Clang 10+ on Linux.
- Python dependencies: [`requirements.txt`](requirements.txt).
- Development tools: [`requirements-dev.txt`](requirements-dev.txt) (ruff, nbconvert).
- Exact versions: [`requirements-lock.txt`](requirements-lock.txt) pins the two files above to versions that pass the test suite and execute every notebook (Python 3.11, Linux). CI installs it on Python 3.11 and the unpinned files on 3.10 and 3.12.
- For the standalone C++ tests: CMake 3.16 or later (Ninja optional).

## Usage

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r scripts/public_debt/requirements.txt
python -m pip install -e scripts/public_debt
python -m pytest tests/public_debt
python -m public_debt.data --geo IT   # optional: pre-download the Eurostat datasets
ruff check --select F scripts tests   # lint (pyflakes rules)

# Standalone C++ tests (strict warnings; add -DPD_SANITIZE=address,undefined or =thread)
cmake -S scripts/public_debt/cpp -B build/cpp -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build/cpp && ctest --test-dir build/cpp --output-on-failure
```

For the exact environment used by CI, install `requirements-lock.txt` instead of `requirements.txt`.

In Visual Studio Code, install the *Python*, *Jupyter* and *C/C++* extensions, select the `.venv` interpreter and use it as the notebook kernel. Set `PUBLIC_DEBT_DATA_MODE=synthetic` to run the notebooks offline on random placeholder data.

## Inputs

| Name | Source | Content |
| --- | --- | --- |
| `gov_10dd_edpt1` | Eurostat | EDP gross debt (GD), net lending/borrowing (B9), interest (D41PAY), % of GDP, general government, from 1995 |
| `nama_10_gdp` | Eurostat | GDP at current prices (CP_MEUR) and real growth (CLV_PCH_PRE) |
| `gov_10a_main`, `gov_10a_exp` | Eurostat | Revenue and expenditure by ESA 2010 item and by COFOG function, % of GDP |
| `irt_lt_mcby_a` | Eurostat | 10-year government bond yields (convergence criterion) |
| Panel of 13 countries | Eurostat `gov_10dd_edpt1`, `nama_10_gdp`, `irt_lt_mcby_a` | AT, BE, DE, DK, EL, ES, FI, FR, IE, IT, NL, PT, SE (Greece is `EL` in Eurostat codes), 1995-2025 |
| `nama_10_pe`, `nama_10_a10_e`, `demo_pjanind`, `lfsi_emp_a`, `rd_e_gerdtot` | Eurostat | Population, employment, hours worked, working-age share (100 minus the shares aged 0-14 and 65+), employment rates, old-age dependency, R&D |
| `GGXWDG_NGDP` | IMF DataMapper (World Economic Outlook) | Gross debt, % of GDP (for Italy from 1988, with projections) |
| `data/external/debt_1861.csv` (optional) | User-provided, for example the Bank of Italy series of Francese and Pace (2008) | Columns `year,debt_pct`; read if present, never downloaded or committed |

Downloads are cached in `data/raw/` (ignored by Git); `PUBLIC_DEBT_DATA_DIR` changes the base folder. Eurostat and IMF data may be reused with acknowledgement of the source. Codes are selected after download; if Eurostat renames a code, the error message lists the available ones.

## Outputs

Figures and tables in `outputs/debt_history/`, `outputs/public_accounts/`, `outputs/growth_drivers/`, `outputs/sustainability/` and `outputs/fiscal_space/`.

The README charts are drawn by `python -m public_debt.readme_figures` (official data; `--synthetic` for an offline check) and saved in a light and a dark variant in `docs/figures/`, the only generated files committed to the repository.

## Method

**Units.** Ratios are fractions of GDP and rates decimals in the code; charts and tables show percentages.

**Debt decomposition** (`public_debt/accounting.py`): $d_t - d_{t-1} = -pb_t + d_{t-1}(i_t-\gamma_t)/(1+\gamma_t) + sfa_t$, with the snowball split into interest $d_{t-1}i_t/(1+\gamma_t)$, real growth $-d_{t-1}g_t/(1+\gamma_t)$ and inflation $-d_{t-1}\pi_t(1+g_t)/(1+\gamma_t)$ effects (European Commission convention). The effective rate is interest paid over the previous year's debt, $i_t = \text{int}_t(1+\gamma_t)/d_{t-1}$; the stock-flow adjustment is the residual. Counterfactuals replay the identity with modified components and observed stock-flow adjustments.

**Fiscal analysis** (`public_debt/fiscal.py`): Hodrick-Prescott output gap ($\lambda = 100$), cyclically adjusted balance with semi-elasticity 0.55, fiscal stance as the change in the cyclically adjusted primary balance, Bohn (1998) fiscal reaction function with Newey-West standard errors, optional indicator variables for exceptional years and sample restrictions.

**Growth accounting** (`public_debt/growth.py`): exact log decomposition of GDP per capita growth into productivity per hour, hours per worker, employment rate and working-age share.

**Debt engine** (`cpp/debt_dynamics.hpp`, `public_debt/dsa.py`): the effective rate reprices gradually, $i_t = (1-s)\,i_{t-1} + s\,r_t$, with $s$ the share of debt refinanced each year. The stochastic analysis adds to the baseline deviations $u_t = A u_{t-1} + e_t$ of real growth, inflation and the 10-year rate, with $A$ estimated by a VAR(1) (`public_debt/var.py`) and $e_t$ resampled from the historical residual vectors; the primary balance responds to growth surprises ($\varepsilon$) and optionally to debt ($\rho$). Each path has its own random stream, so results do not depend on the number of threads. The adjustment grid computes, for plans of different size and length, the probability that the debt ratio is higher at a target year. Fiscal multipliers can be added to consolidation scenarios.

**Fiscal space and spreads** (`public_debt/fiscal_space.py`): within (fixed-effects) estimator, with year effects added as dummies (exact in unbalanced panels), and Driscoll-Kraay standard errors (Newey-West over time of the cross-sectional sums of scores) or errors clustered by country. The fiscal reaction function is cubic in lagged debt with the output gap (Ghosh, Kim, Mendoza, Ostry and Qureshi, 2013). A country's reaction is its fixed effect plus the average year effect plus the common polynomial. The debt limit is the largest debt ratio at which the reaction still reaches the debt-stabilising balance $((r(d) - g)/(1+g))\,d$, with $r(d) = r_0 + \kappa(d - d_0)$; it is found on a grid with linear interpolation. Parameter uncertainty comes from draws of the slope coefficients from their asymptotic normal distribution, with the country effect recomputed from the within-estimator identity. Spreads over the Bund are regressed on lagged debt (with a post-2008 interaction), the lagged primary balance and real growth; the residual is the part not explained by fundamentals and the common year effect.

**EU rules** (`dsa.eu_rules_check`): simplified checks inspired by the 2024 framework (3% deficit, average debt decline of 1 point a year above 90% of GDP, 1.5% resilience margin, declining debt after the adjustment).

## Verification

Run `python -m pytest tests/public_debt` (25 tests, about 10 seconds):

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
| Within estimator equals the dummy-variable regression, with and without year effects; entity and year effects reproduce the fitted values | relative $10^{-9}$, absolute $10^{-10}$ |
| Driscoll-Kraay (zero lags) and cluster-robust standard errors against direct formulas | relative $10^{-10}$ |
| Debt limit: infinite for a reaction steeper than the stabilising line, undefined below it, equal to the root of the cubic case (brentq), lower with a debt-dependent rate | $10^{-6}$; exact |
| Draws with zero covariance reproduce the point limit; synthetic panel recovers the gap response and the post-2008 spread slope | $10^{-9}$; 0.1 and $t > 2$ |

## C++ unit tests and sanitizers

**Tests.** The engine is header-only, so [`cpp/CMakeLists.txt`](cpp/CMakeLists.txt) also compiles it without Python. It uses `-Wall -Wextra -Wpedantic -Wshadow -Wold-style-cast -Wnull-dereference -Wdouble-promotion -Werror` (`/W4 /WX` with MSVC) and bounds-checked standard containers outside Release builds. [`cpp/tests/test_core.cpp`](cpp/tests/test_core.cpp) runs 213 checks without any test framework. The Python suite compares the engine with NumPy implementations; these tests add exact identities, reductions of the stochastic engine to deterministic projections, thread invariance and argument validation on the C++ code alone:

| Check | Tolerance |
| --- | --- |
| SplitMix64 and xoshiro256** against the published reference outputs; uniform and normal moments | exact; 4 standard errors |
| `parallel_for`: same result for 1, 3 and 8 threads; an exception in a task is rethrown | exact |
| Projection: change in the debt ratio = snowball - primary balance + stock-flow adjustment, interest = $d_{t-1} i_t / (1 + \gamma_t)$, effective-rate recursion; refinancing shares 0 and 1 | $10^{-14}$ to $10^{-15}$; exact |
| Closed forms: $i_t = r + (i_0 - r)(1 - s)^t$; $d_t = d_0 ((1 + i)/(1 + \gamma))^t$ without primary balance; the debt-stabilising primary balance keeps $d_t = d_0$ | $10^{-15}$ to $10^{-12}$ |
| Stochastic DSA with degenerate shocks equals the deterministic projection: no shocks, a constant shock (with the growth semi-elasticity), VAR decay with a diagonal and a non-symmetric matrix, the -2% floor on the market rate, the fiscal reaction to the debt ratio written out | $10^{-13}$ to $10^{-14}$ |
| Residual bootstrap: two residual vectors are drawn with frequency 1/2 each; 1 vs 6 threads with primary-balance noise; argument validation | 4 standard errors; bitwise; exact |
| Adjustment grid: probabilities in [0, 1], never higher for a larger or longer adjustment (the same shocks are reused), each cell equal to the share computed from the fan chart; argument validation | exact |

**Mutation check.** Eight deliberate bugs were injected into the engine, and each makes the suite fail:

- nominal growth added instead of compounded;
- the snowball effect not deflated by nominal growth;
- the market rate lagged one year;
- the VAR matrix transposed;
- the floor on the market rate removed;
- the fiscal reaction halved;
- the residual bootstrap drawing only half of the residuals;
- the fiscal adjustment starting one year late.

The transposed VAR matrix was missed until the non-symmetric VAR check was added: a diagonal matrix is its own transpose.

**Sanitizers.** The same tests pass under two sanitizer builds:

- AddressSanitizer with UndefinedBehaviorSanitizer (`-DPD_SANITIZE=address,undefined`): out-of-bounds access, use after free, signed overflow and similar;
- ThreadSanitizer (`-DPD_SANITIZE=thread`): data races in the parallel Monte Carlo loop.

CI runs both, plus GCC and Clang builds with warnings as errors.

## Continuous integration

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs on every pull request and on pushes to `main`. It needs no credentials and downloads no data. Its jobs:

1. **Python:** lint (ruff, pyflakes rules) and the test suite, on Python 3.11 with the locked versions and on 3.10 and 3.12 with the newest allowed versions.
2. **C++:** the standalone tests with GCC and Clang (warnings as errors), and with GCC under ASan/UBSan and under TSan.
3. **Notebooks:** every Python notebook executed offline on synthetic data. The job checks that the data cache stays empty, i.e. that synthetic mode does not touch the network.

## References

- Balassone, F., Francese, M. and Pace, A. (2013). Public debt and economic growth: Italy's first 150 years. *The Oxford Handbook of the Italian Economy since Unification*.
- Blanchard, O. (2019). Public debt and low interest rates. *American Economic Review*, 109(4), 1197-1229.
- Blanchard, O. and Leigh, D. (2013). Growth forecast errors and fiscal multipliers. *American Economic Review*, 103(3), 117-120.
- Bernoth, K., von Hagen, J. and Schuknecht, L. (2012). Sovereign risk premiums in the European government bond market. *Journal of International Money and Finance*, 31(5), 975-995.
- Bohn, H. (1998). The behavior of U.S. public debt and deficits. *Quarterly Journal of Economics*, 113(3), 949-963.
- De Grauwe, P. and Ji, Y. (2013). Self-fulfilling crises in the Eurozone: an empirical test. *Journal of International Money and Finance*, 34, 15-36.
- Driscoll, J. C. and Kraay, A. C. (1998). Consistent covariance matrix estimation with spatially dependent panel data. *Review of Economics and Statistics*, 80(4), 549-560.
- European Commission. *Debt Sustainability Monitor*; Regulation (EU) 2024/1263.
- Francese, M. and Pace, A. (2008). Il debito pubblico italiano dall'Unità a oggi. Banca d'Italia, Questioni di Economia e Finanza 31.
- Ghosh, A. R., Kim, J. I., Mendoza, E. G., Ostry, J. D. and Qureshi, M. S. (2013). Fiscal fatigue, fiscal space and debt sustainability in advanced economies. *Economic Journal*, 123(566), F4-F30.
- IMF (2021). Review of the Debt Sustainability Framework for Market Access Countries.
- Mourre, G., Poissonnier, A. and Lausegger, M. (2019). The semi-elasticities underlying the cyclically-adjusted budget balance. European Commission Discussion Paper 098.
- Blackman, D. and Vigna, S. (2021). Scrambled linear pseudorandom number generators. *ACM TOMS*, 47(4) (public-domain xoshiro256** reference code).
