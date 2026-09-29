# Outlook expansion: professional forecasts

Implemented for six quarterly median measures in the current development increment; hosted publication and independent final gates are recorded separately. This is a second kind of forward-looking evidence beside GDPNow and FOMC projections. Reader job: what do surveyed economists expect, for which period, and how did the same target change since the previous survey?

## Verified source starting points

- [Median forecasts](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/median-forecasts) links level/growth workbooks and documentation. The page identifies survey history beginning in 1968 Q4 and an August 14, 2026 update. Individual series need their own coverage checks. Moody's historical Aaa/Baa values are excluded as proprietary.
- [Q3 2026 release](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/spf-q3-2026) provides current/previous tables for real GDP, unemployment, payrolls and inflation, plus mean probabilities of a negative growth quarter. It separates quarterly annualized growth, annual-average GDP growth, Q4/Q4 inflation and longer-run averages. The release also discloses interpolated historical jump-off values for certain 2025 series; these are not interchangeable with subsequently revised official observations.

The collector retains and hashes the official median-growth workbook, median-level workbook and release-date text. Build-time validation reconstructs every published value from those bytes. The current capture has 3,360 survey/target observations; its 2026 Q3 source cells were reconciled independently against the official release. No original-release files are reconstructed from the current historical workbooks.

## Implemented boundaries and publication gate

Start with GDP, unemployment and headline/core inflation. Retain source workbooks, hashes, actual survey/release dates and target periods. Read documentation before choosing columns; do not confuse growth of a median level with the median of growth forecasts. Compare the same target and definition across surveys, not shifting horizons.

Keep SPF survey medians distinct from FOMC participant projections and model-based GDPNow. A negative-quarter probability is not an NBER recession probability; forecast dispersion is not automatically a confidence interval. Do not present proprietary historical series, inferred publication dates or ex-post data as an original information set.

The Outlook view shows a target-labelled five-quarter path and history of expectations for a selected target, with original-workbook links and point-of-use release/capture dates. The change ledger separates new target horizons, genuine same-target updates and historical workbook corrections. No future calendar events are inferred from a past release-date list. The release gate still requires malformed/missing-data tests, independent PM/econometric/UI review, hosted refresh and public-payload verification.
