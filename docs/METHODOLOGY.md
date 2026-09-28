# Evidence and measurement

Every normalized record preserves its source ID, URL, source date (if supplied), and capture timestamp. Source receipts retain fetch status, count, raw-body SHA-256, and last successful timestamp. The collector validates response shape rather than equating HTTP success with data availability.

## Calendar

iCalendar unfolding and timezone-aware conversion preserve scheduled times. Date-only events remain date-only. FOMC meeting end dates come from the Fed's calendar, not a fabricated time-of-day assumption. Treasury times are competitive bidding deadlines; announced offering amounts are not actual issuance proceeds. Public-inspection expected publication dates are not effective dates. Past calendar dates do not certify release.

For sorting only, date-only records precede timed records on their Eastern calendar day. This convention does not assert an intraday publication time. Publisher calendar UIDs persist across rescheduling; Treasury event identity includes CUSIP, announcement date and issue date to distinguish reopenings. Court entry identity uses publisher GUIDs, retaining distinct descriptions and document links when multiple RSS items describe the same entry.

## Economics

The initial universe is 13 public series from BLS, BEA, Census/HUD, DOL and the Federal Reserve, distributed through FRED. Each carries units, frequency, seasonal adjustment and a preferred transformation. CPI and core CPI growth use seasonally adjusted indices and may differ from headline NSA year-over-year releases. Payroll growth is calculated from latest revised levels; it is not a first-release surprise. GDP uses quarterly real levels and annualized compound growth. No model or analyst consensus is inferred.

## Legal and disclosure

Public inspection contains prepublication filings. Read an official PDF before relying on legal effect. Published Federal Register coverage is a bounded latest-100 sample, explicitly not exhaustive. Court coverage is restricted to three selected RSS channels and their observed windows. Feed volumes cannot be compared as legal-risk incidence. Court records are entry metadata, not full dockets or judgments. SEC 8-K availability is monitored; errors are reported rather than hidden. Patents, forecasts and prediction markets are explicitly linked research references until ingestion is established.

## Resilience and history

Each collector fails independently. A failure retains its own prior successful payload and original timestamps with a stale flag. No first-success payload means unavailable. Builds validate unique IDs, dates, links, series ordering and source membership. A missing entire core calendar or economic series collection blocks publication. Original raw bodies are content-addressed; repeated bodies are not duplicated. Capture snapshots begin at launch and do not reconstruct past vintages, unobserved intraday transitions, or feed items lost between polls.

## Selection

Overview comparisons use explicit arithmetic. Economic mechanism text is labelled context, not a causal test. The overview disclosure table selects one latest record per available channel; the complete captured stream is chronological. A high-volume court cannot crowd every agency off the homepage. Source outages, stale captures, frequency mismatches and partial history remain visible.

## Research workflows

Capture comparisons use each source's own previous successful timestamp. Unavailable current sources are excluded. Newly captured records may have existed before either capture. A record leaving a rolling feed is not treated as withdrawal. Economic comparisons distinguish new periods, added historical observations and changed values. The initial corrected baseline was reconstructed from the retained raw responses with the current parser; the earlier original snapshot remains available as captured.

Exposure lenses are case-insensitive literal substring matches over title, summary, agency and publisher. They do not infer exposure, entity identity or materiality. Lens definitions and reading lists stay in browser local storage and may be lost if storage is cleared or unavailable. Shareable URLs preserve public filters, not those local contents.

The capture archive currently has no automatic deletion; raw responses are content-addressed. Storage growth must be reviewed before expanding cadence or source volume. Source access, redistribution rights and operational reliability are separate acceptance checks for every new feed.
