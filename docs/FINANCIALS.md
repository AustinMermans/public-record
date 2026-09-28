# Reported issuer financials

Company profiles add a financial screen to the selected SEC filing universe. This is not a complete financial model, a recommendation, an earnings-consensus comparison or a valuation. The initial implementation covers the same 25 CIKs as the filings desk; predecessor and successor Exxon registrants remain separate.

## Evidence and collection

The keyless [SEC companyfacts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) supplies standardized, entity-wide XBRL facts. Custom issuer KPIs and all dimensions of the statements are not covered. A successful API retrieval does not imply that the latest filing has corresponding facts: the profile explicitly distinguishes collection status from current-fact availability.

Collection runs after company submissions, serially, with a 0.65-second pause between requests and the approved identifying User-Agent supplied through the private `SEC_USER_AGENT` environment setting. It is sent only to SEC endpoints. Public error records never serialize private subprocess arguments. No browser-to-SEC requests or API key are required.

`data/financials/receipts/` records actual retrieval and attempt timestamps. Raw responses are retained losslessly as content-addressed gzip files; their SHA-256 is computed over the original **uncompressed response bytes**. `--reparse` verifies those hashes and preserves source clocks; `processed_at` records normalization time separately. Failed refreshes retain successful evidence with explicit stale status. The public build contains normalized facts and evidence indexes, not raw archives or request identity.

## Period and definition rules

- Choose the latest verified original 10-Q or 10-K and its report end before selecting any value. Require the exact accession, form, filing date, concept, unit and dates. Missing latest-report facts are not backfilled from a different report.
- Keep quarterly operations separate from year-to-date cash flow and balance-sheet instants. Fiscal labels and calendar frames alone do not identify a quarter; week-based calendars retain their real dates. Ambiguous or stub durations are withheld.
- Use comparable prior-year durations from the same filing, and actual prior fiscal year-end dates for balance-sheet comparisons. Preserve missingness, currency differences and concept boundaries rather than estimating a bridge.
- Conflicting same-basis facts or amendments suppress the affected row. An amendment does not automatically replace an entire filing. Identical duplicate frames do not create a conflict.
- Revenue mappings are issuer-specific. Walmart and Berkshire use consolidated total revenue, not a narrower contract-revenue concept. Earnings/equity labels distinguish parent-only and noncontrolling-interest-inclusive bases. Separately tagged temporary equity is shown when available and included in balance-sheet reconciliation.
- Up to five defensible annual periods are shown, limited by the verified recent-submission coverage. They are anchored to selected original annual filings, not a fully restated series, TTM reconstruction or exhaustive original-release vintage archive. Filing dates do not establish intraday availability.

## Calculations and presentation

Operating margin is 100 × operating income / revenue with a positive denominator. Cash generation includes reported operating cash flow, cash PPE payments, and their explicit subtraction. The latter is a Public Record calculation, not universally defined free cash flow or distributable cash. Inputs must have identical periods, currencies and accessions. Every derived value exposes its formula and source-linked inputs.

Percentage changes require a positive comparable prior; otherwise the display uses an absolute difference. Margin changes are percentage points. Balance-sheet liabilities are not debt. Displayed amounts are rounded with a visible scale; normalized evidence retains original source precision.

Banks use net revenue, interest/noninterest income, credit-loss provisions, earnings, deposits and balance-sheet facts, without industrial operating-margin/cash-flow templates. REIT, insurance, health-services, utility and industrial-finance profiles carry explicit boundaries. FFO, underwriting ratios, medical-care ratios, NIM, CET1, organic growth and industrial leverage are not inferred from generic tags.

## Change tracking and validation

Issuer comparisons use their own last successful capture. New periods, newly available historical facts, revised reported values, recalculated derived values and definition changes have distinct labels. Derived definitions include their input concepts/units. Definition changes suppress numeric-revision claims. Disappearing facts are not treated as zero, withdrawals or an issuer correction. Reparsing uses the retained comparison baseline rather than comparing a capture with itself.

The publication gate checks CIK, source-index membership, accession URLs, exact current periods and controlling filings, comparative provenance and compatible derived-input units. Normalization keeps source indexes, QA flags, checks actually performed and unavailable-comparison reasons. Independent numerical review and responsive/browser checks are recorded in [REVIEWS.md](REVIEWS.md).

Local usage:

```sh
python3 scripts/corporate.py
python3 scripts/collect_financials.py
# Rebuild normalized facts without a new retrieval:
python3 scripts/collect_financials.py --reparse
```
