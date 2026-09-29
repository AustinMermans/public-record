# Next increment: banking conditions

Shipped in verified v1.8.0. Independent bounded review, real source capture, raw-bound validation, browser checks, hosted refresh and public-payload equality gates passed; receipts are in REVIEWS.md. The scope below is preserved as the acceptance record, not an assertion of full-product completion.

Reader job: Are problem loans and realized credit losses improving or worsening, and how do reserves, earnings, capital and deposits compare? Add a compact panel within Funding & credit, not an institution directory or bank ranking.

## Sources

- [FDIC QBP time-series workbook, Q2 2026](https://www.fdic.gov/quarterly-banking-profile/qbp-time-series-spreadsheets-second-quarter-2026.xlsx): keyless probe returned HTTP 200, seven sheets, 2,616,294 bytes. Use published All Insured Institutions aggregates, not a self-assembled sum of bank API records.
- [FDIC notes to users, Q2 2026](https://www.fdic.gov/quarterly-banking-profile/qbp-notes-users-second-quarter-2026.pdf): population, ratio construction, annualization and comparability.

Probe evidence is feasibility only; the production collector must repeat discovery, retain raw bytes/hash and bind every reported value to its sheet, heading, population and quarter. Establish a reliable latest-edition discovery mechanism instead of hardcoding Q2. Verify a modern applicable source-reuse policy before publication; an archive-only policy does not suffice.

## Minimal display

Current, prior-quarter and year-ago columns, plus a selectable history chart for noncurrent loans/loans; quarterly net charge-off rate; allowance/noncurrent loans; quarterly return on assets; bank equity/assets; and deposits. Context: reporting-institution count, assets and bank-attributable quarterly net income. Headline numbers must open the corresponding detailed measure. Link original sources separately.

No composite health score or causal interpretation. A mixed directional summary can explain observed movements without calling the system healthy or distressed.

## Measurement boundaries and acceptance

- Population is FDIC-insured commercial banks and savings institutions, not SEC bank holding companies. FDIC tables can include both parent and subsidiary institution reports without a double-counting adjustment; label these FDIC-reported aggregates.
- Published aggregate ratios are not unweighted averages of institution ratios. Performance ratios are annualized with appropriate average-period denominators; use published ratios rather than inventing denominator approximations.
- Quarterly Income and Annual Income are distinct. Bank-attributable income and equity differ from totals including noncontrolling interests. Do not treat an API NETINC field as a quarter flow without independent definition verification.
- Monetary amounts in the selected workbook tables are USD millions; selected ratio-sheet values are percentages directly. Other sheets can use different percentage conventions. Validate per field/sheet, never with a workbook-wide converter.
- Noncurrent means 90+ days past due plus nonaccrual. Do not conflate with differently defined nonperforming measures. Omit regulatory capital ratios initially because CBLR exclusions can change the population.
- Independently reconcile published Q2 2026 ratios: `(39811 + 89844) / 13936266 * 100` rounds to 0.93%; `223887 / 129655 * 100` to 172.68%; `2624826 / 26462210 * 100` to 9.92%. Inclusive equity gives a different result and must not be substituted.
- Reject missing or duplicate populations, unknown/moved headings, formula errors, absent quarters, zero denominators and annual-income substitution. Match semantic labels and periods, not fixed row positions alone.
- Keep successful retrieval, attempt and quarter clocks distinct. Preserve prior success on failure; a daily check does not mean new quarterly data. Compare replaced historical observations as revisions, not reconstructed original-release vintages.
- Require independent numerical/source audit, PM usefulness review, responsive/chart-interaction checks, build/test gates, hosted refresh and public-payload verification before release.
