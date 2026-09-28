# Issuer financials — next reviewed increment

Proposed v1.5.0 scope, recommended by the PM after v1.4 approval. **Not implemented or shipped.** Reader job: understand what changed in reported operations, cash generation and the balance sheet without a compulsory filing click. Keep the existing 25 CIKs before expanding the universe further.

## Source and collection

Use the keyless [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), collected server-side with the approved private SEC_USER_AGENT setting and serialized requests below two per second. Do not send that identity to other providers. Retain exact raw-response hashes, capture/last-success times and stale-success caches. Consider lossless compressed raw retention because individual responses are several megabytes; hashing and reproducibility must remain explicit.

Retain each candidate's CIK, namespace, concept, unit, start/end, value, accession, form, filed date, fiscal labels and optional frame. Standard companyfacts coverage is not a comprehensive source of issuer-specific operating KPIs.

## Profile displays

- Nonfinancial operating period: revenue, operating income, operating margin, net income and directly reported diluted EPS; matched prior-year fiscal period when defensible.
- Cash generation: reported YTD operating cash flow and cash PPE expenditure, exact start/end dates, plus explicitly labelled Public Record subtraction. Do not call the subtraction universally defined free cash flow or distributable cash.
- Balance sheet: cash/equivalents, assets, liabilities and equity at exact instants, compared with fiscal year-end where available. Liabilities are not debt.
- Up to five validated annual periods below the current profile. Do not force TTM reconstruction into the first increment.
- Banks JPM/BAC: separately mapped net revenue, net interest income, noninterest income, credit-loss provision, earnings, deposits, assets and equity. No industrial FCF or operating-margin template. NIM/CET1/loan-loss ratios need additional verified definitions.
- Specialist views: BRK insurance conglomerate, UNH health insurance/services, PLD REIT and NEE utility carry explicit comparability boundaries. No inferred underwriting result, medical-care ratio, FFO/AFFO, same-store NOI or distress score from generic tags. CAT/GE consolidation changes likewise preclude automatic leverage claims. Keep both Exxon CIK histories separate.

## Selection invariants

1. Anchor to a verified periodic filing and report end first; do not independently choose each tag's latest observation and assemble mixed-year headlines.
2. Use exact start/end dates, not fiscal labels alone, to distinguish quarter, YTD and annual. Duration windows are candidate checks, not proof of fiscal identity. Handle 52/53-week calendars and explicitly label/reject stubs.
3. Prefer corresponding comparative periods from the same current filing. Preserve actual dates and units. Do not silently convert currencies or divide incompatible concepts.
4. Revenue candidates are issuer-specific mappings, not interchangeable aliases: RevenueFromContractWithCustomerExcludingAssessedTax, RevenueFromContractWithCustomerIncludingAssessedTax, Revenues and SalesRevenueNet. Preserve the chosen concept and definition.
5. Instant facts match end dates. Never subtract cumulative EPS, average quarter EPS, sum debt-tag name matches or substitute liabilities for debt.
6. Group by concept/unit/exact period. Preserve conflicting same-basis facts as exceptions. Later eligible comparative values are latest reported history, not originally known history. An amendment does not automatically replace an entire report.
7. No defensible mapping/period bridge means unavailable comparison, not an invented estimate. Suppress misleading growth on nonpositive denominators and show absolute change where useful. Margin differences use percentage points.
8. Link every displayed value to its actual accession. Filing dates alone do not support intraday or point-in-time backtest claims.

## Concrete regression evidence from PM source probes

The PM verified keyless HTTP 200 for [Apple](https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json) and [JPMorgan](https://data.sec.gov/api/xbrl/companyfacts/CIK0000019617.json) on September 28, 2026, using the approved SEC-only contact.

- Apple: one current 10-Q contains nine-month revenue of $364.357 billion and quarter revenue of $109.417 billion under the same fiscal labels. CFO of $116.996 billion is nine-month YTD, not quarter cash flow. Refetch and retain authoritative fixtures during implementation; this planning note is not raw-source evidence.
- JPM: FinancingReceivableAllowanceForCreditLosses exists but its latest fact is from 2021, while other current facts are in 2026. A latest-per-alias rule would mix obsolete allowance data with current balance-sheet figures.

## Release acceptance

Independently reconcile a technology issuer, retailer, industrial, bank and specialist profile to source facts. Test quarter/YTD ambiguity, 53-week years, stubs, duplicate frames, obsolete concepts, missing current facts, amendment conflicts, currency differences and metadata-only refreshes. Include newly observed periods and changed previously reported facts in cross-section Changes, distinguishing revisions from mapping/definition boundaries. Require PM/content/econometric and responsive UI approval before publication. The plan is a useful increment, not a claim to build a complete valuation or credit model.
