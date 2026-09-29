# Funding and global financial stress

This desk provides context for money-market and credit research, not a corporate-bond valuation, default-probability estimate or trading signal.

The [dated credit-conditions read](CREDIT-READ.md) now juxtaposes source-bound New York Fed, OFR and FDIC measures above the detailed charts. It preserves each publisher's effective/observation period and retrieval clock, withholds the cross-source prose on missing, old or definition-mismatched evidence, and does not infer a synchronized daily/quarterly trend.

## New York Fed

SOFR and EFFR come directly from the [New York Fed reference-rate API](https://markets.newyorkfed.org/static/docs/markets-api.html). Each request is bounded to the latest 400 published effective dates. Rates are percentages; volumes are billions of US dollars. The percentile range describes the transaction-rate distribution, not statistical uncertainty about the median. The markets differ, so their volumes are not summed.

The displayed spread is a **Public Record calculation**: `(SOFR − EFFR) × 100`, in basis points. Both rates must have the same effective date. Missing dates are omitted, not carried forward. The most recent common date can differ from either series's latest standalone observation. These are realized overnight rates, not forward policy expectations.

Effective dates are distinct from publication and retrieval. The source ordinarily publishes SOFR around 8 a.m. Eastern and EFFR around 9 a.m., with possible afternoon revisions. The API revision indicator is retained verbatim. Current history can incorporate corrections; retained captures provide evidence only from our collection start onward. See [methodology](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates).

The source's reference-rate disclaimer, nonaffiliation notice, SOFR third-party acknowledgment and [terms link](https://www.newyorkfed.org/privacy/termsofuse) accompany the page, series charts, ledger and CSV exports. These third-party data are **not** relicensed under Public Record's noncommercial licenses. Their source permissions and conditions continue to apply; no endorsement is implied. Derived spread calculations are ours, not New York Fed publications.

## Office of Financial Research

The [Financial Stress Index](https://www.financialresearch.gov/financial-stress-index/) is a global measure based on 33 variables. Its signed index points describe stress relative to a historical-average reference; negative is below average, not an absence of risk. It is not a percentage or a US-only index.

The CSV supplies history beginning in 2000, the total, five market-category contributions and three regional contributions. Each decomposition describes the same total: adding all eight components double-counts it. Contributions are not standalone indices; the credit component is not a corporate credit spread. Published rounding can prevent exact summation.

The parser records residuals greater than 0.005 points as source-quality exceptions without changing the supplied values. In the September 28 capture, the regional contributions on November 1, 2018 sum to −1.731 while the published total is −1.623: a −0.108-point residual, larger than rounding. The page exposes this historical exception separately; the latest decompositions reconcile.

The dashboard's short overview chart shows the latest 260 observations; the explorer and export expose all captured history. The index normally lags by two business days. History may be revised, and the source has documented corrections to May 2026 observations. Capture differences are not original-release vintages.

Source credit is retained in normalized data and exports. [OFR legal notices](https://www.financialresearch.gov/legal-notices/) distinguish government-authored work from third-party copyrighted material. We redistribute OFR's published aggregate index/contributions, not its underlying proprietary vendor series, and do not claim a license to those inputs.

## Operations and validation

Collection runs at 13:43 and 21:43 UTC every day, subject to GitHub Actions availability. A successful daily poll need not produce a new business-day observation. Each feed retains its own last-success time, raw response and SHA-256. Failed feeds retain their prior data with stale/unavailable status. Funding-page receipts additionally flag retrievals older than 36 hours; that age check is not a claim about the publisher's release timetable.

Parsers reject invalid/future dates, duplicate periods, nonfinite values, missing required fields, incomplete bounded rate responses and implausible rate-distribution ordering. OFR requires its full column schema and a minimum history length; this cannot detect every syntactically valid truncation, so the latest observation remains visible for freshness assessment. Any changed unit or measurement definition creates a change-ledger boundary rather than an ordinary numerical revision.
