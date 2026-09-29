# Banking conditions

The Funding & credit desk uses the FDIC Quarterly Banking Profile (QBP) time-series workbook's published **All Insured Institutions** aggregates. This is a depository-institution population, not SEC-reporting bank holding companies. FDIC can include consolidated parent and separate subsidiary reports without adjusting for potential double counting; amounts are labelled FDIC-reported aggregates, not uniquely consolidated financial-system totals.

## Reading the measures

Noncurrent loans include loans 90 or more days past due plus loans on nonaccrual. The noncurrent-loan ratio, allowance coverage and bank-equity/assets ratio describe quarter-end stocks. Quarterly net charge-off rate and return on assets are published annualized performance ratios, not quarter-only percentage losses or returns. Deposits and assets are quarter-end stocks; bank-attributable net income is a quarterly flow from the Quarterly Income sheet. Income and equity including noncontrolling interests must not replace bank-attributable amounts.

The primary table compares a quarter with the immediately preceding quarter and the same quarter one year earlier. Ratios are retained as published rather than averaged across institutions. Changes in percentage-valued ratios are expressed as percentage points or basis points, not percent growth. Monetary source values are USD millions; display scaling to USD billions does not alter retained source values. Regulatory-capital ratios with different CBLR populations are excluded.

Historical values belong to the retrieved workbook edition. A revision to an old observation is not a reconstructed original-release vintage. Changes in accounting, reporting definitions and the institution population limit long-horizon comparisons. Refer to the edition's FDIC notes before drawing structural or causal conclusions. In the Q2 2026 workbook, 1984–1989 noncurrent and coverage ratios do not reconstruct from the displayed balance-sheet components. Another 23 historical balance-sheet identities differ beyond displayed rounding. Their cause is not established here. Published values remain unchanged; the corresponding histories expose period-specific diagnostics. Do not describe the entire history as component-reconciled.

## Evidence and refresh

The collector discovers the latest workbook through FDIC's official publication pages and retains the raw response with a content hash. Extracted values carry sheet/cell references, metric labels, population and quarter. Successful retrieval time is distinct from the observation quarter and the latest attempt. A daily check does not imply a new quarterly observation. Failed collection retains the last successful values with a stale warning; missing source values are not zero.

Build-time validation binds the normalized bundle to retained raw evidence. Current, prior-quarter and year-ago ratio reconciliations use matching published numerators and denominators with an allowance for source rounding. Historical checks are diagnostic and disclose exceptions rather than establishing uniform historical comparability. Change records compare each metric/quarter against the prior successful banking capture, not the unrelated macro capture clock. Definition changes must not masquerade as ordinary numerical revisions.

## Source data and reuse

Source: FDIC Quarterly Banking Profile. The [FDIC public data catalog](https://www.fdic.gov/data.json) identifies related QBP Graph Book distributions and the underlying Research Information System data as public domain with unrestricted reuse. The catalog does not enumerate a bespoke license for the time-series workbook. Public Record's original-work licenses do not restrict those FDIC source data; no FDIC endorsement is implied. Retained catalog records document the scope of this evidence.

The [QBP publication page](https://www.fdic.gov/quarterly-banking-profile) provides the original workbook and edition-specific notes. All source links remain available alongside the on-page comparisons. This panel does not estimate defaults, rank banks or claim to be a complete bank valuation or credit model.
