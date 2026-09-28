# Company coverage

The v1.3 expansion targets a deliberately selected cross-sector set, not an index replication or a market-wide universe. Tickers were resolved against the [SEC ticker directory](https://www.sec.gov/files/company_tickers.json) on September 28, 2026. Each response is bound to an exact CIK; the parser rejects a mismatched CIK. Current names and tickers come from the submissions response. The executable CIK list is in `scripts/corporate.py`; each profile links its SEC submissions source.

Selected ticker families: AAPL, MSFT, AMZN, JPM, WMT, XOM, NVDA, GOOGL, META, TSLA, BRK-B, LLY, V, JNJ, BAC, KO, CAT, PG, UNH, GE, HD, LIN, NEE and PLD. These provide exposure to technology, communications, consumer businesses, financial services, healthcare, energy, industrials, materials, utilities and real estate. This is a descriptive selection, not a claim of representative weighting.

There are 25 registrant profiles rather than 24 because the original Exxon Mobil CIK `0000034088` remains separate from the directory's current XOM holding-company CIK `0002115436`. Do not merge their filing timelines, infer a complete corporate-action history, or treat a ticker as a permanent entity identifier. The release capture contains 1,375 selected filings; this count will change with refreshes.

Each company uses bounded category quotas: up to 6 annual, 12 quarterly, 20 current-event, 4 proxy, 12 ownership and 6 other selected forms. These draws come from the SEC recent-submissions response, not a complete historical filing archive. Amendments remain separate and count within those quotas. Form 4 does not automatically mean an open-market purchase.

The collector requests companies sequentially with a 0.6-second pause after each request. Failed requests retain prior successful evidence with a stale label or mark a new company unavailable. An expanded universe must not increase request concurrency or obscure coverage failures.

Company profiles separate CIK-linked SEC records from wider-record name matches. The latter use explicit lexical matching and remain unverified research leads. Search preserves individual public-record IDs, because court entries can share a docket URL while representing different filings or procedural events.
