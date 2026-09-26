# How to read Italy's public accounts

A practical guide to the documents, definitions and data needed to analyse the Italian State budget, the general government accounts and the public debt. Notebook [`02_state_budget_analysis.ipynb`](../notebooks/public_accounts/02_state_budget_analysis.ipynb) applies it to the data.

## 1. Two perimeters, two accounting bases

| | State budget (*bilancio dello Stato*) | General government account (*conto consolidato delle Amministrazioni pubbliche*) |
| --- | --- | --- |
| Producer | Ministry of Economy and Finance, State General Accounting Department (MEF-RGS) | ISTAT, under the European System of Accounts (ESA 2010) |
| Coverage | Central State only | General government, sector S13: central government (S1311), local government (S1313), social security funds (S1314) |
| Basis | Financial: legal commitments (*competenza*) and cash (*cassa*) | Economic accrual: transactions recorded when economic value is created or rights and obligations arise |
| Approval and control | Parliament, with the budget law (*legge di bilancio*); final accounts (*Rendiconto generale dello Stato*) examined by the Court of Auditors (*giudizio di parificazione*) | Transmitted to Eurostat in the excessive deficit procedure notifications (April and October) |
| Classification | Missions and programmes (*missioni e programmi*), economic categories | ESA 2010 transactions (D1, P2, D62, D41, P51G, D2, D5, D61...) and functions (COFOG) |
| Used for | Authorising spending, managing the Treasury | EU fiscal rules, international comparisons, sustainability analysis |

The **Maastricht debt** (gross, consolidated within general government, at nominal value) is compiled by the **Bank of Italy**, which publishes it monthly together with the borrowing requirement (*fabbisogno*) in the supplement *Finanza pubblica: fabbisogno e debito*.

## 2. Balances and why they differ

- **Net lending/borrowing (B9)**: revenue minus expenditure on an accrual basis; the "deficit" of the EU rules (3% of GDP reference value).
- **Primary balance**: net lending/borrowing excluding interest payable (D41). It measures what current policies cost, independently of the inherited debt.
- **Cyclically adjusted balance**: removes the effect of the business cycle (output gap times the semi-elasticity of the budget, about 0.5-0.55 for Italy).
- **Structural balance**: cyclically adjusted balance net of one-off and temporary measures (tax amnesties, asset sales, emergency transfers).
- **Borrowing requirement (*fabbisogno*)**: cash needs of the public sector; it differs from the deficit because of cash-accrual timing, financial transactions (loans, equity injections, privatisation receipts) and other items.
- **Stock-flow adjustment**: the part of the change in debt not explained by the deficit (financial asset accumulation, valuation effects, cash-accrual differences, reclassifications). Large or persistent stock-flow adjustments deserve scrutiny.

## 3. The debt identity

With debt ratio $d$, effective interest rate $i$, nominal growth $\gamma$, primary balance $pb$ and stock-flow adjustment $sfa$:

$$d_t - d_{t-1} = -pb_t + d_{t-1}\frac{i_t - \gamma_t}{1+\gamma_t} + sfa_t, \qquad pb^* = d\,\frac{i-\gamma}{1+\gamma}$$

$pb^*$ is the primary balance that stabilises the ratio. When interest rates exceed nominal growth, a primary surplus is needed just to keep the ratio constant; the higher the debt, the larger it is.

## 4. The budget cycle

- **EU framework (from 2024)**: each Member State agrees a **medium-term fiscal-structural plan** (Italy's first plan covers 2025-2029) with a **net expenditure path** (primary expenditure net of discretionary revenue measures and cyclical unemployment spending) consistent with a declining debt ratio; annual progress reports; the draft budgetary plan by 15 October; the Commission's assessment in the European Semester. Safeguards require an average debt reduction for high-debt countries and a structural deficit margin below 3% of GDP.
- **National process**: the budget law is presented by 20 October and approved by 31 December; the national planning documents (formerly the *Documento di economia e finanza* and its update) were adapted to the new EU framework in 2024-2025.
- **Rules and institutions**: balanced-budget principle in Article 81 of the Constitution (as amended in 2012) and Law 243/2012; the **Ufficio parlamentare di bilancio** (parliamentary budget office, operational since 2014) endorses the macroeconomic forecasts and assesses compliance; the **Corte dei conti** audits the accounts.

## 5. Where the data are

| Source | What | Access |
| --- | --- | --- |
| ISTAT | General government quarterly and annual accounts, EDP notifications | istat.it, esploradati.istat.it (SDMX) |
| Bank of Italy | Debt, borrowing requirement, holders of the debt, average cost and maturity | Base Dati Statistica (BDS), statistical supplements |
| MEF-RGS | State budget, *Rendiconto*, Treasury cash account, OpenBDAP open data; Public Debt Department (issuance, average life of bonds) | mef.gov.it, rgs.mef.gov.it, dt.mef.gov.it |
| UPB, Corte dei conti | Independent assessments, audits | upbilancio.it, corteconti.it |
| Eurostat | Harmonised EU data used in this repository (`gov_10dd_edpt1`, `gov_10a_main`, `gov_10a_exp`, `nama_10_gdp`...) | ec.europa.eu/eurostat |
| European Commission | AMECO database, Debt Sustainability Monitor, fiscal plan assessments | economy-finance.ec.europa.eu |
| IMF, OECD | World Economic Outlook, Fiscal Monitor, historical public finance data; Economic Surveys | imf.org, oecd.org |

## 6. An analysis workflow

1. **Fix the perimeter and the basis** (State or general government; cash or accrual) and use the same ones throughout.
2. **Express everything in % of GDP and in real terms** as well as in euro; check revisions between vintages.
3. **Separate interest, cycle and one-offs**: headline, primary, cyclically adjusted and structural balances.
4. **Decompose changes** by revenue and expenditure item (economic and functional classifications) and by subsector (State, regions, municipalities, social security).
5. **Benchmark** against peers (Germany, France, Spain, EU average) and over time.
6. **Look at tax expenditures and tax credits**: they are spending carried out on the revenue side; transferable tax credits (such as the building bonuses) affect deficit and debt at different times depending on how they are recorded (Eurostat clarified the treatment in 2024).
7. **Assess sustainability**: interest-growth differential, stabilising primary balance, maturity and refinancing needs, sensitivity to rates and growth, contingent liabilities (State guarantees, ageing costs).
8. **Assess quality**: growth-friendliness (investment, education, R&D and their execution rates), equity, efficiency of the tax system (tax wedge, evasion).

## 7. Common pitfalls

- Comparing State-budget figures with general-government figures, or cash with accrual data.
- Reading a falling debt ratio as fiscal effort when it is driven by inflation (nominal GDP) or by one-off operations.
- Ignoring that EU recovery-fund grants are neutral for the deficit (recorded as revenue when the related expenditure occurs), while loans add to debt.
- Treating temporary measures as permanent savings, or permanent tax cuts financed by temporary revenues.
- Forgetting the lag between market rates and the average cost of the debt.

## 8. Glossary

| Italian | English |
| --- | --- |
| Indebitamento netto | Net borrowing (deficit, B9) |
| Avanzo/disavanzo primario | Primary surplus/deficit |
| Saldo strutturale | Structural balance |
| Fabbisogno | Borrowing requirement (cash) |
| Debito pubblico (definizione di Maastricht) | General government gross consolidated debt |
| Spesa per interessi | Interest expenditure |
| Legge di bilancio | Budget law |
| Rendiconto generale dello Stato | Final accounts of the State |
| Competenza / cassa | Commitment basis / cash basis |
| Spesa primaria corrente / in conto capitale | Current / capital primary expenditure |
| Pressione fiscale | Tax-to-GDP ratio (taxes and social contributions) |
| Cuneo fiscale | Tax wedge on labour |
| Spending review | Spending review |
| Aggiustamento stock-flussi | Stock-flow adjustment |
