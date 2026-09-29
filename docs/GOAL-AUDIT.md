# Investor-hub completion audit

Updated for the hosted v1.16.0 filed-quarter release, September 29, 2026 (Pacific). **Full goal: not approved.** A reviewed application increment is not proof that the entire product is complete. Publication receipts are recorded separately in REVIEWS.md.

## Acceptance requirements

| Requirement | Current evidence and remaining work |
| --- | --- |
| Data refresh at least daily | Seven-day twice-daily workflow is configured. Hosted refresh 36627804184 succeeded and its published payload matched the rebuilt capture, including an `ok` BEA release channel. The v1.15 and v1.16 code publications succeeded separately and did not refresh source data. Future scheduler execution is not guaranteed by configuration; the next expected run should be checked against Actions history. |
| At least ten high-value source sites, keyless first | Twelve provider families appear below, grouping Treasury services and repeated endpoints rather than inflating counts. This inventory is not an assertion that the best investor data needs are covered. Broader forecasts remain a material gap. |
| Useful without opening every source | Macro charts, calendar, extracted FOMC/GDPNow/SPF, plain-language disclosure entries, company filing profiles, filing-anchored financial screens, 35 verified recent issuer-exhibit briefs and funding/stress comparisons are implemented. The v1.12 front exposes active change desks; v1.13 juxtaposes dated funding/stress/banking measures; v1.14 adds BEA's dated GDP stage record; live v1.15 aligns GDPNow, SPF and BEA by target quarter. The approved v1.16 candidate adds 12 source-matched issuer filed-quarter reads with direct exhibit/10-Q links. This is not complete earnings-driver, legal-news, valuation or credit analysis. |
| Historical and forward-looking context | Revised macro history and sampled ALFRED vintages; FOMC projections, GDPNow and target-fixed SPF survey histories. Live v1.14 retains eight recent actual BEA GDP release-stage pages across three target quarters, distinct from current-revised FRED history, with four schedule-only future stages. It does not reconstruct a full original-release history or consensus surprises. Further forecast panels and prediction-market history are incomplete. |
| Reviewer validation | Independent PM, source/econometric and UI/UX gates approve the bounded v1.16 filing comparison after correcting source-identity and editorial framing findings. Earlier gates approved the bounded v1.15 GDP watch, v1.14 BEA, v1.13 credit, v1.12 changes and v1.11 Business increments. Fresh final product approval is still required after remaining gaps are resolved. |
| Responsive and accessible experience | Browser checks across 320–1920px, keyboard chart controls and resize-state preservation. Physical-device and screen-reader certification are not claimed. |
| Versioned, attributable publication | Semantic versions, changelog/citation/build consistency, source links and scoped noncommercial licenses. v1.15 and v1.16 are deployed, but their immutable tags and GitHub releases remain outstanding because GitHub CLI authentication is invalid. |

## Ingested provider families

This is a dated inventory, not a live status display. The Sources page and raw receipts control current availability. FRED/ALFRED are one provider family; the three selected court sites are also grouped rather than counted as three separate investor-data capabilities. Separately published Federal Reserve bank research/data services are named explicitly rather than presented as unrelated institutions.

| Provider family | Site | Current reader job / boundary |
| --- | --- | --- |
| St. Louis Fed | fred.stlouisfed.org / alfred.stlouisfed.org | Macro history and sampled as-of vintages; original statistical publishers remain credited. |
| BEA | bea.gov | Official release schedule and bounded source-verified recent real-GDP advance/second/third release record. Other numeric BEA macro series currently arrive through FRED; this is not a full first-release archive. |
| Federal Reserve Board | federalreserve.gov | FOMC calendar, projections and official announcements. |
| US Treasury | treasurydirect.gov / fiscaldata.treasury.gov | Announced auctions; matched-FYTD receipts, outlays, net interest and balance, reconciled accounting bridge and monthly history. Not comprehensive financing accounts or a debt-stock bridge. |
| Federal Register | federalregister.gov | Published rules/notices and public inspection; not legal-effect certification. |
| SEC | sec.gov / data.sec.gov | Selected filings, current 8-K feed, standardized companyfacts screens and bounded Item 2.02 issuer-exhibit text; other filing-body announcements, missing latest-filing facts and issuer-specific KPIs remain explicit. |
| Federal district courts | ecf.cand / ecf.nysd / ecf.cacd.uscourts.gov | Three partial rolling feeds, procedural explanations; not complete dockets. |
| Atlanta Fed | atlantafed.org | Extracted GDPNow estimate, horizon and publication date. |
| New York Fed | newyorkfed.org / markets.newyorkfed.org | Overnight funding levels, distributions, volumes and same-date comparisons. |
| Office of Financial Research | financialresearch.gov | Global stress history and component contributions; not bond-level pricing. |
| FDIC | fdic.gov | Six banking measures, nine histories and explicit historical reconciliation exceptions from the official QBP workbook. Institution aggregates, not bank holding-company valuations or original-release vintages. |
| Philadelphia Fed | philadelphiafed.org | Six SPF median measures by survey and fixed target quarter; current historical workbook edition, not original-release file vintages. |

BLS's direct calendar remains unavailable in the current collection environment and is **not** counted as a successful direct provider. BLS-origin macro history remains available through FRED. Failed access is not evidence that the publisher has no feed.

## Next high-value iterations

The [unified change edition](CHANGE-EDITION-PLAN.md), [Treasury fiscal increment](FISCAL-PLAN.md), [FDIC banking increment](BANKING-PLAN.md) and [SPF forecast increment](SPF.md) are verified live. Broader outlook and cross-source synthesis remain completion requirements, not deferred out of scope.

1. **Business reading depth after v1.16:** searchable issuer profiles and exact-filing detail lead with source-backed text for 35 of 49 selected recent Item 2.02 accessions; 14 deliberately remain metadata-only. Twelve of 25 selected registrants have a verified issuer-exhibit/10-Q filed-quarter read. The next content gap is source-supported drivers and guidance, especially for exceptional net-income moves, plus issuer-specific KPIs, segments and debt context. Other 8-K announcements, alternative exhibits and broader issuer/news coverage remain incomplete; standardized facts are not a full company model.
2. **Banking conditions — bounded increment completed in v1.8:** [FDIC aggregate plan](BANKING-PLAN.md) with verified units, institution population and stock/flow definitions. Treasury budget flows and matched-period bridge shipped in v1.7.0; financing/debt-stock analysis remains separate. Bank ratios cannot be summed or naively averaged.
3. **Changes across the whole publication — completed for current channels in v1.6, front corrected in v1.12:** company filings and research updates join core and issuer-financial differences with independent prior-success baselines. Active disclosure/calendar desks now surface without arbitrary case promotion; the full ledger remains source-filterable. Future providers must adopt the same boundaries. Individual court-row substance and more readable ledger detail remain gaps.
4. **Broader outlook and release coverage:** SPF quarterly medians and bounded recent BEA GDP release stages are live; the target watch aligns them with current GDPNow. Extend to prior BEA editions and other major releases with source-bound first values; add an accessible official BLS schedule, additional forecasts and energy/inventory information when source access and publication rights permit. Build consensus/surprise and market-implied paths as separate, explicitly sourced layers.
5. **Cross-source synthesis and final review:** the v1.13 credit read is one bounded daily/quarterly evidence sheet; the v1.15 GDP target watch is a second candidate synthesis, not a real-time forecast-error history. More investor tasks across macro, equity and credit, direct provenance, freshness at the point of use, and fresh PM/econometric/UI approval of the full site remain required.

These items are not implemented merely by being listed. Do not mark the persistent goal complete on the basis of a ten-row inventory, a passing unit-test suite or a narrow release approval.
