# Federal fiscal conditions

The Treasury section uses the Monthly Treasury Statement (MTS), published by the U.S. Department of the Treasury, Bureau of the Fiscal Service. It describes budget receipts, outlays and the signed surplus/deficit. It is not a debt-outstanding series, forecast, measure of fiscal impulse or policy-causality model.

## Definitions and comparable periods

Table 3 supplies Total Receipts, Total Outlays and Surplus (+) or Deficit (-), using current-month, current-fiscal-year-to-date and comparable-prior-fiscal-year-to-date fields. Table 9 supplies Net Interest. Gross interest from table 3 is not a substitute. Federal fiscal years begin October 1. Every FYTD comparison retains explicit start/end dates; September is the completed fiscal year, not a calendar-year observation.

Actual API amounts are dollar-scale. The published PDF expresses corresponding values in millions; original API dollar strings are retained and only presentation is scaled to billions. Budget estimates are excluded because their unit and placeholder conventions differ from the actual fields. Missing values are not zero.

MTS uses modified-cash reporting, including accrued interest on publicly held Treasury debt. Payment-date shifts can move spending between adjacent months. A monthly change is not automatically a structural trend. Reporting month-end, publication date and capture time are distinct; a precise publication timestamp is not supplied by this integration. A successful daily refresh can return unchanged monthly data.

## Reconciliation and synthesis

For each supported period, decimal arithmetic must satisfy receipts minus outlays equals the published signed balance. When the display presents a deficit as positive, it negates the signed balance; a positive balance is a surplus and must be labelled accordingly.

The deficit-change bridge is an accounting identity: change in net interest plus change in other outlays minus change in receipts. The component sum must equal the directly computed change in the financing gap. It describes contributions, not the effects of a policy or administration. Failed reconciliation, duplicate/missing rows or mismatched editions block new synthesis.

Table 1 monthly records require fiscal-year hierarchy within the same edition. Classification IDs can change between editions. A prior-year Year-to-Date row can represent the full prior year, so it is not used as a matched partial-year comparator. Monthly histories preserve their single publication edition and revisions; first-release monthly points from different editions are never silently summed into latest FYTD values.

## Evidence, updates and source rights

The collector retains exact requests, raw-body hashes, original values, table/row identities, edition and capture time. Failed updates retain the previous successful bundle with stale status. Capture comparisons distinguish same-period revisions from new-period boundaries. A first capture is only a baseline; changed definitions cannot be reported as numerical revisions.

[FiscalData licensing](https://fiscaldata.treasury.gov/about-us/) and its [API authorization terms](https://fiscaldata.treasury.gov/api-documentation/) permit copying, adaptation and redistribution for commercial and noncommercial purposes. Treasury source data do not inherit Public Record's noncommercial restriction. Source attribution is retained as a provenance practice; Public Record's licenses apply to its original software, writing and visualizations. This documents the published source policy, not legal-counsel certification.

Official references: [MTS dataset](https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/), [Treasury reporting/release guidance](https://home.treasury.gov/policy-issues/financial-markets-financial-institutions-and-fiscal-service/cash-and-debt-forecasting), and [August 2026 published statement](https://fiscaldata.treasury.gov/static-data/published-reports/mts/MonthlyTreasuryStatement_202608.pdf). The independent reviewer reconciled current API actuals to this statement's million-dollar display before implementation approval.
