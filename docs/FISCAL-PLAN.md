# Next increment: federal fiscal conditions

Released and verified as v1.7.0, including hosted refresh and public-payload equality; publication receipts are in REVIEWS.md. The original scope below is retained as the acceptance record. Source probes were repeated in the collector with content-addressed raw receipts and independently reconciled by the PM reviewer; the scout's findings are not substituted for production evidence.

Reader job: **What changed in the federal deficit, and how much came from receipts, non-interest spending or interest?**

## Bounded display and sources

- Comparable fiscal-year-to-date receipts, total outlays, net interest and deficit, with prior-FYTD and dollar changes. Label both complete fiscal spans explicitly.
- One accounting bridge: change in net interest + change in other outlays − change in receipts = change in the positive deficit/financing gap. This is an accounting contribution, not policy causality.
- Monthly history behind a toggle only after table-1 hierarchy, year and edition alignment are validated. No naive accumulation of differently revised monthly vintages.
- Source links, reporting periods, capture time, partial/stale states and a collapsed method note. Preserve existing clickable-number and accessible chart conventions.

Primary keyless endpoints:

- [MTS table 3](https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_3?filter=record_date:eq:2026-08-31&page%5Bsize%5D=1000): uniquely identify Total Receipts, Total Outlays and Surplus (+) or Deficit (-). Actual amount fields: `current_month_rcpt_outly_amt`, `current_fytd_rcpt_outly_amt`, `prior_fytd_rcpt_outly_amt`.
- [MTS table 9](https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9?filter=record_date:eq:2026-08-31&page%5Bsize%5D=1000): exact Net Interest function; not gross interest from table 3.
- Table 1 at the same API prefix supports monthly history after identifying each row's fiscal-year parent. Latest `record_date` is an edition, not the economic date of every row. Prior-year Year-to-Date can mean the full prior year rather than the matched cutoff.

## Acceptance and exclusion boundaries

API actual amounts are dollar-scale; PDF million-dollar display conventions must not be applied to them. The scout found a different scale in budget-estimate fields and a zero surplus estimate. Exclude estimates entirely until units and missing/placeholder semantics are separately verified. Preserve string `null` as missing and exclude section headers. July outlays differed between July and August editions, demonstrating why edition provenance matters.

Use decimal arithmetic: receipts − outlays must equal Treasury's signed surplus/deficit for current month, current FYTD and matched prior FYTD. The three-component bridge must reconcile to the direct deficit difference. Fail closed on duplicate/missing rows, mismatched editions or reconciliation failure. Retain signed balance in data even if the display uses a positive deficit convention; surpluses must not be labelled deficits.

Period-end, publication and capture clocks remain separate. [Treasury timing guidance](https://home.treasury.gov/policy-issues/financial-markets-financial-institutions-and-fiscal-service/cash-and-debt-forecasting) describes release normally on the eighth workday after month-end; do not invent a precise timestamp. Modified-cash reporting and payment shifts limit single-month inference.

Require independent PM and econometric/source reconciliation, responsive UI checks, source-rights assessment and hosted refresh/public-payload verification. No budget forecasts, policy attribution, bank aggregates or debt-stock/financing bridge in this increment. Those remain subsequent work; deficit is not debt growth. Full-product completion remains open.
