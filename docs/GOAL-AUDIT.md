# Investor-hub completion audit

Updated after the verified v1.4.0 release, September 28, 2026. **Full goal: not approved.** A reviewed application increment is not proof that the entire product is complete.

## Acceptance requirements

| Requirement | Current evidence and remaining work |
| --- | --- |
| Data refresh at least daily | Seven-day twice-daily workflow is live. Hosted expanded-feed refresh 36496725413 succeeded and its published payload matched the rebuilt capture. Future scheduler execution is not guaranteed by configuration. |
| At least ten high-value source sites, keyless first | Ten successful provider families appear below, counting repeated endpoints and related feeds once. This inventory is not an assertion that the best ten investor data needs are covered. Fiscal, banking and broader forecasts remain material gaps. |
| Useful without opening every source | Macro charts, calendar, extracted FOMC/GDPNow, plain-language disclosure entries, company filing profiles and funding/stress comparisons are implemented. Issuer financial substance and deeper cross-source synthesis remain incomplete. |
| Historical and forward-looking context | Revised macro history and sampled ALFRED vintages; FOMC projections and GDPNow. Original-release surprise histories, broader forecast panels and prediction-market history are incomplete. |
| Reviewer validation | PM, econometric and narrow source-rights reviewers approve the v1.4 funding increment, not the full goal. Fresh final product approval is still required after remaining gaps are resolved. |
| Responsive and accessible experience | Browser checks across 320–1920px, keyboard chart controls and resize-state preservation. Physical-device and screen-reader certification are not claimed. |
| Versioned, attributable publication | Semantic versions, changelog/citation/build consistency, source links and scoped noncommercial licenses. Tags follow verified deployments. |

## Ingested provider families

This is a dated inventory, not a live status display. The Sources page and raw receipts control current availability. FRED/ALFRED are one provider family; the three selected court sites are also grouped rather than counted as three separate investor-data capabilities. Separately published Federal Reserve bank research/data services are named explicitly rather than presented as unrelated institutions.

| Provider family | Site | Current reader job / boundary |
| --- | --- | --- |
| St. Louis Fed | fred.stlouisfed.org / alfred.stlouisfed.org | Macro history and sampled as-of vintages; original statistical publishers remain credited. |
| BEA | bea.gov | Official release schedule; numeric BEA macro series currently arrive through FRED. |
| Federal Reserve Board | federalreserve.gov | FOMC calendar, projections and official announcements. |
| TreasuryDirect | treasurydirect.gov | Announced Treasury auctions, not comprehensive fiscal accounts. |
| Federal Register | federalregister.gov | Published rules/notices and public inspection; not legal-effect certification. |
| SEC | sec.gov / data.sec.gov | Selected company filings and current 8-K feed; normalized company financials still missing. |
| Federal district courts | ecf.cand / ecf.nysd / ecf.cacd.uscourts.gov | Three partial rolling feeds, procedural explanations; not complete dockets. |
| Atlanta Fed | atlantafed.org | Extracted GDPNow estimate, horizon and publication date. |
| New York Fed | newyorkfed.org / markets.newyorkfed.org | Overnight funding levels, distributions, volumes and same-date comparisons. |
| Office of Financial Research | financialresearch.gov | Global stress history and component contributions; not bond-level pricing. |

BLS's direct calendar remains unavailable in the current collection environment and is **not** counted as a successful direct provider. BLS-origin macro history remains available through FRED. Failed access is not evidence that the publisher has no feed.

## Next high-value iterations

1. **Issuer financial substance:** SEC companyfacts with correct fiscal durations, units, restatements and industry-specific displays. Do not apply industrial leverage heuristics to banks.
2. **Fiscal and banking conditions:** Treasury financing/deficit/interest flows with fiscal-year alignment; FDIC aggregates with verified units, institution population and stock/flow definitions. Debt-stock changes are not deficits; bank ratios cannot be summed or naively averaged.
3. **Changes across the whole publication:** company filings and research updates must join the currently core-only comparison ledger, with independent prior-success baselines.
4. **Broader outlook and release coverage:** Philadelphia Fed forecasts, an accessible official BLS schedule, and energy/inventory information when source access and publication rights permit.
5. **Cross-source synthesis and final review:** investor tasks across macro, equity and credit, direct provenance, freshness at the point of use, and fresh PM/econometric/UI approval of the full site.

These items are not implemented merely by being listed. Do not mark the persistent goal complete on the basis of a ten-row inventory, a passing unit-test suite or a narrow release approval.
