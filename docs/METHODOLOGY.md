# Evidence and measurement

Every normalized record preserves its source ID, URL, source date (if supplied), and capture timestamp. Source receipts retain fetch status, count, raw-body SHA-256, and last successful timestamp. The collector validates response shape rather than equating HTTP success with data availability.

## Calendar

iCalendar unfolding and timezone-aware conversion preserve scheduled times. Date-only events remain date-only. FOMC meeting end dates come from the Fed's calendar, not a fabricated time-of-day assumption. Treasury times are competitive bidding deadlines; announced offering amounts are not actual issuance proceeds. Public-inspection expected publication dates are not effective dates. Past calendar dates do not certify release.

For sorting only, date-only records precede timed records on their Eastern calendar day. This convention does not assert an intraday publication time. Publisher calendar UIDs persist across rescheduling; Treasury event identity includes CUSIP, announcement date and issue date to distinguish reopenings. Court entry identity uses publisher GUIDs, retaining distinct descriptions and document links when multiple RSS items describe the same entry.

## Economics

The initial universe is 13 public series from BLS, BEA, Census/HUD, DOL and the Federal Reserve, distributed through FRED. Each carries units, frequency, seasonal adjustment and a preferred transformation. CPI and core CPI growth use seasonally adjusted indices and may differ from headline NSA year-over-year releases. Payroll growth is calculated from latest revised levels; it is not a first-release surprise. GDP uses quarterly real levels and annualized compound growth. No model or analyst consensus is inferred.

## Legal and disclosure

Public inspection contains prepublication filings. Read an official PDF before relying on legal effect. Published Federal Register coverage is a bounded latest-100 sample, explicitly not exhaustive. Court coverage is restricted to three selected RSS channels and their observed windows. Feed volumes cannot be compared as legal-risk incidence. Court records are entry metadata, not full dockets or judgments. Rule-based explanations clarify supported procedural labels; they do not infer allegations, judicial reasoning, or outcomes. SEC 8-K availability is monitored; errors are reported rather than hidden. Patents, prediction markets and unimplemented forecast channels remain linked references. FOMC projection medians and GDPNow figures are now extracted separately with evidence receipts.

## Resilience and history

Each collector fails independently. A failure retains its own prior successful payload and original timestamps with a stale flag. No first-success payload means unavailable. Builds validate unique IDs, dates, links, series ordering and source membership. A missing entire core calendar or economic series collection blocks publication. Original raw bodies are content-addressed; repeated bodies are not duplicated. Capture snapshots begin at launch and do not reconstruct past vintages, unobserved intraday transitions, or feed items lost between polls.

## Selection

Overview comparisons use explicit arithmetic. Economic mechanism text is labelled context, not a causal test. The overview disclosure table selects one latest record per available channel; the complete captured stream is chronological. A high-volume court cannot crowd every agency off the homepage. Source outages, stale captures, frequency mismatches and partial history remain visible.

## Research workflows

Capture comparisons use each source's own previous successful timestamp. Unavailable current sources are excluded. Newly captured records may have existed before either capture. A record leaving a rolling feed is not treated as withdrawal. Economic comparisons distinguish new periods, added historical observations and changed values. The initial corrected baseline was reconstructed from the retained raw responses with the current parser; the earlier original snapshot remains available as captured.

Exposure lenses are case-insensitive literal substring matches over title, summary, agency and publisher. They do not infer exposure, entity identity or materiality. Lens definitions and reading lists stay in browser local storage and may be lost if storage is cleared or unavailable. Shareable URLs preserve public filters, not those local contents.

The capture archive currently has no automatic deletion; raw responses are content-addressed. Storage growth must be reviewed before expanding cadence or source volume. Source access, redistribution rights and operational reliability are separate acceptance checks for every new feed.

## Unified change edition

Core feeds, each covered SEC issuer's submissions and financial facts, and each extracted forecast retain independent comparison channels. Each uses its own previous successful capture, not one publication-wide interval. A current failed/stale feed is not compared; a first comparable payload establishes a baseline. Legacy payloads lacking per-channel receipts recover windows from retained items where possible and otherwise remain unavailable for comparison until refreshed. Capture timing is not publication timing, and unseen changes between polls cannot be reconstructed.

Corporate identity uses CIK and accession; amendments remain separate filings. Summary references to the same verified SEC archive identity are grouped across feeds without deleting ledger rows or treating them as independent corroboration. Financial recalculations are not issuer-reported changes. Economic revision batches group by series, source, change type and capture pair, led by the newest affected observation. Selection is latest capture, latest affected period, then title, with at most three developments per investor desk; it is not a materiality score. The complete ledger retains disclosure/calendar rows and all grouped items with filters and pagination.

GDPNow compares values only within the same target and definition. SEP aligns measure names and horizons rather than table positions; new measures/horizons and changed definitions are explicit boundaries. A same-publication-date value change is a same-date update, not a proven publisher correction. Cached ALFRED vintage files are excluded from forecast news. Before/after values link to the supplied publisher evidence; a publisher's mutable page is not a historical vintage permalink. Retained comparison baselines and capture receipts provide the historical evidence trail in the repository.

## ALFRED and forecasts

Current FRED downloads have no arbitrary 2015 cutoff. Each series begins at its earliest available observation. The optional ALFRED view currently covers GDP, unemployment, payrolls and CPI at July 30, 2020 and year-end dates from 2020 onward. Its selector is the exact collected universe. Each CSV header must identify the requested series and vintage date; future observations, invalid values and duplicate dates are rejected. Historical requests are cached with immutable retrieval receipts. ALFRED as-of data is not a reconstruction of every first release or an intraday information set.

Historical chart windows are anchored to the selected vintage date. Transformations use only that vintage's observations. Then/now comparisons align observation periods, not publication dates. GDP units change from chained 2012 to chained 2017 dollars on September 28, 2023 according to the ALFRED metadata; levels across different bases are not subtracted. Growth-rate differences are percentage points. Original source: https://alfred.stlouisfed.org/series?seid=GDPC1 .

FOMC medians are parsed from the latest dated accessible projections linked by the official meeting calendar. Three- and four-year horizon layouts are supported; blank longer-run core PCE stays missing. GDP and inflation are Q4/Q4 projections, unemployment a Q4 average, and the funds rate a year-end target midpoint. GDPNow is a model estimate for a named quarter, in quarterly annualized growth; it is not directly comparable to a Q4/Q4 annual projection. Forecast failures preserve prior successful data with stale status and original retrieval/publication times.

## Corporate coverage

The initial universe is Apple, Microsoft, Amazon, JPMorgan Chase, Walmart and Exxon Mobil, identified by CIK and checked against SEC response identity. It is a starter cross-industry sample, not a screen or investment recommendation. Each recent-submissions response contributes up to 6 annual, 12 quarterly, 20 current-event, 4 proxy, 12 ownership and 6 other selected-form entries; amendments count within quotas. This prevents ownership filings crowding out operating reports but does not provide complete company history. Acceptance timestamps are retained for ordering when provided. Filing, transaction and report-period dates are distinct.

Form and 8-K item descriptions label disclosure categories; no full-document conclusion is claimed. Form 4 is not automatically an open-market purchase. Original and amended forms are retained as separate records and must not be summed as independent economic events. Contact-bearing user agents are restricted to SEC requests, with a private workflow secret and conservative sequential pacing.
