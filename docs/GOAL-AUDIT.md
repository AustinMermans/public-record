# Investor-hub completion audit

Updated for the v1.14.0 BEA GDP release-history candidate, September 29, 2026 (Pacific). **Full goal: not approved.** A reviewed application increment is not proof that the entire product is complete. Publication receipts are recorded separately in REVIEWS.md.

## Acceptance requirements

| Requirement | Current evidence and remaining work |
| --- | --- |
| Data refresh at least daily | Seven-day twice-daily workflow is live. Hosted v1.11 refresh 36617568267 succeeded and its published payload matched the rebuilt capture. Future scheduler execution is not guaranteed by configuration. |
| At least ten high-value source sites, keyless first | Twelve provider families appear below, grouping Treasury services and repeated endpoints rather than inflating counts. This inventory is not an assertion that the best investor data needs are covered. Broader forecasts remain a material gap. |
| Useful without opening every source | Macro charts, calendar, extracted FOMC/GDPNow/SPF, plain-language disclosure entries, company filing profiles, filing-anchored financial screens, 35 verified recent issuer-exhibit briefs and funding/stress comparisons are implemented. The v1.12 front exposes active change desks, including court-feed activity with source-specific counts/windows and filtered ledger links. The v1.13 Funding read juxtaposes five dated New York Fed/OFR/FDIC measures with guarded interpretation and direct sources. The v1.14 candidate adds a dated BEA GDP stage record. This is not substantive legal-news coverage or a complete valuation/credit model; broader cross-source and issuer synthesis remains incomplete. |
| Historical and forward-looking context | Revised macro history and sampled ALFRED vintages; FOMC projections, GDPNow and target-fixed SPF survey histories. The v1.14 candidate retains eight recent actual BEA GDP release-stage pages across three target quarters, distinct from current-revised FRED history, with four schedule-only future stages. It does not reconstruct a full original-release history or consensus surprises. Further forecast panels and prediction-market history are incomplete. |
| Reviewer validation | Independent PM, econometric and UI/UX gates approve the bounded v1.14 BEA candidate, pending hosted verification. Earlier independent gates approved bounded v1.13 credit, v1.12 changes and v1.11 Business increments. Fresh final product approval is still required after remaining gaps are resolved. |
| Responsive and accessible experience | Browser checks across 320–1920px, keyboard chart controls and resize-state preservation. Physical-device and screen-reader certification are not claimed. |
| Versioned, attributable publication | Semantic versions, changelog/citation/build consistency, source links and scoped noncommercial licenses. Tags follow verified deployments. |

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

1. **Business reading depth after v1.11:** searchable issuer profiles and exact-filing detail now lead with source-backed text for 35 of 49 selected recent Item 2.02 accessions; 14 deliberately remain metadata-only. The next content gap is item-bounded narrative from other 8-K announcements, alternative exhibits, broader issuer/news coverage and research-grade company dossiers. Verified issuer-specific KPIs, segments and debt context remain valuable; selected standardized facts are not complete coverage. Broader sources below take priority over multiplying generic ratios.
2. **Banking conditions — bounded increment completed in v1.8:** [FDIC aggregate plan](BANKING-PLAN.md) with verified units, institution population and stock/flow definitions. Treasury budget flows and matched-period bridge shipped in v1.7.0; financing/debt-stock analysis remains separate. Bank ratios cannot be summed or naively averaged.
3. **Changes across the whole publication — completed for current channels in v1.6, front corrected in v1.12:** company filings and research updates join core and issuer-financial differences with independent prior-success baselines. Active disclosure/calendar desks now surface without arbitrary case promotion; the full ledger remains source-filterable. Future providers must adopt the same boundaries. Individual court-row substance and more readable ledger detail remain gaps.
4. **Broader outlook and release coverage:** SPF quarterly medians are live and the BEA candidate begins an actual release-stage archive for recent real GDP. Extend to prior BEA editions and other major releases with source-bound first values; add an accessible official BLS schedule, additional forecasts and energy/inventory information when source access and publication rights permit. Build consensus/surprise and market-implied paths as separate, explicitly sourced layers.
5. **Cross-source synthesis and final review:** the v1.13 credit read is one bounded daily/quarterly evidence sheet. More investor tasks across macro, equity and credit, direct provenance, freshness at the point of use, and fresh PM/econometric/UI approval of the full site remain required.

These items are not implemented merely by being listed. Do not mark the persistent goal complete on the basis of a ten-row inventory, a passing unit-test suite or a narrow release approval.
