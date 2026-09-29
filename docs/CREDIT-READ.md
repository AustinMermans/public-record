# Dated credit-conditions read

The Funding desk's first screen juxtaposes five observations from three already-collected official publisher families. Its reader question is narrow: are the latest observed overnight funding, global market stress and FDIC-insured bank loan-quality measures moving in the same direction, and **when** was each measured? It is not a composite score, a US corporate-credit spread, a causal explanation, or a forecast.

## Evidence and comparisons

| Measure | Basis | Comparison and source |
| --- | --- | --- |
| SOFR − EFFR | Basis points, `(SOFR − EFFR) × 100`; both New York Fed rates must share an effective date. | Latest versus previous common effective date; both exact rate sources linked. A newer standalone rate never fills the missing counterpart. |
| OFR Financial Stress Index | Global signed index points relative to historical-average zero; normally published with a two-business-day lag. | Latest versus previous observation within the current OFR edition; official index URL linked. Negative is not zero risk. |
| OFR credit contribution | Signed market-category contribution to the same global index, not a standalone index, corporate bond spread, or default rate. | Displayed only when latest and prior component dates exactly match the corresponding total-index dates. Its direction can differ from total stress. |
| FDIC noncurrent loans / loans | Quarter-end share of loans at FDIC-insured institutions, including 90+ days past due and nonaccrual. | Latest quarter versus immediately prior quarter from the **same** reconciled current QBP workbook edition; official source-cell workbook linked. |
| FDIC net charge-off rate | Published annualized ratio for quarterly bank performance, not a quarter-end stock or annual income amount. | Same adjacent-quarter and current-edition rule; official source-cell workbook linked. |

Every row shows its observation/effective period, prior period, retrieval clock, unit, definition and original source. The displayed values link to the on-site history or detailed banking panel. The short synthesis is withheld unless all five comparisons have validated periods, exact expected source/units/frequency definitions and source links, and their individual source receipts are successful and no older than 36 hours. The daily New York Fed common observation and OFR total must also be no more than seven calendar days old; this allows ordinary weekends and holidays without treating an old but successfully polled daily series as current. FDIC remains quarterly and does not inherit a daily observation-age rule. Individual rows can remain visible with explicit missing or stale labels. A new capture alone is not a new observation.

The prose states directional movements *within* each series and notes the OFR credit component as counterevidence where appropriate. It never labels the cross-source configuration as broadly improving/worsening, infers a shared cause, or splices daily September data into quarterly June bank outcomes. FDIC historical values are from the latest workbook edition; original-release vintages have not been reconstructed. The existing [Funding methodology](FUNDING.md) and [FDIC banking documentation](BANKING.md) control detailed source definitions and reuse terms.

## Gate

Tests reject a missing common rate date, stale or unavailable source receipts, old daily observations despite fresh retrieval, wrong daily source/unit/frequency, wrong FDIC quarter/unit/annualization, invalid QBP reconciliation, mismatched OFR component dates, missing source URLs, and nonfinite observations. Responsive browser checks confirmed that five evidence rows are readable without page-level horizontal overflow, internal drill-down values and external publisher links are distinct, and all three publisher clocks remain explicit. Independent PM, temporal-method and UI reviewers approved this bounded synthesis increment at P0=P1=P2=0. This is not final product approval.
