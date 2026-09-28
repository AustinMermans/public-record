# Independent product reviews

## Publication desks and search gate — 1.3.0, September 28, 2026

Independent UI/UX and content/identity reviewers approved at P0=0, P1=0, P2=0, P3=0. The UI review corrected lost search-result pagination on Back/reload/share and removed a duplicate company directory that obscured profile-to-filings navigation. The content review corrected URL deduplication that suppressed distinct docket entries, aligned profile continuation with its exact lexical-mention set, and updated front-page selection methodology. Regression tests now retain all 6,093 captured disclosure IDs and independently searchable entries sharing a docket URL.

The content reviewer verified all 25 unique configured CIKs, all raw-response hashes, and exact reparse equality for all 1,375 selected filings. The new and predecessor Exxon registrants remain separate. News coverage is explicitly official Fed announcements; politician/vote/campaign data is explicitly not ingested. These are not certifications of each filing's substantive accuracy or completeness.

Host browser checks passed global search → company profile → company-filtered filings; paginated search reload and Back restoration; empty search results; exact Apple mention scope and scope reload; the formerly hidden Huizhong Geng petition; and ten new routes at 320, 390, 768, 1280 and 1920px without page-level horizontal overflow. The reviewers inspected desktop/mobile screenshots. The suite passed 29 Python and 22 JavaScript tests. Touch emulation and viewport checks are not a physical-device or screen-reader certification.

## Chart interaction gate — 1.2.0, September 28, 2026

An independent UI/UX reviewer approved with P0=0, P1=0, P2=0, P3=0 after identifying and verifying a fix for lost pins on responsive resizing. The review covered the integrated chart module, range controls, accessible inspection controls, units/vintage context, URL restoration, and desktop/mobile screenshots. The reviewer independently ran the 15 JavaScript tests and syntax check. The local codex-bus CLI dependency was unavailable (ENOENT), so the review used a native subagent with the same bounded critic/fixer gate.

Host browser checks exercised keyboard stepping with retained focus; full-plot pointer inspection and click-to-pin; latest reset; range pressed state and reload/share restoration; height-only resize and orientation changes with pin/focus preservation; mobile page overflow; and touch-emulated historical GDP selection/stepping. The full suite passed 29 Python and 15 JavaScript tests. Screenshots are local QA artifacts under output/playwright/chart-*-v12.png. Touch emulation is not a physical-device or screen-reader certification.

### Ongoing UI/UX release checks

For releases that change charts, navigation, filtering or responsive layout, request a focused UI/UX reviewer before publication. Review the actual interaction, not only a screenshot:

- Inspect an ordinary point and an endpoint by mouse, keyboard and touch. Confirm dates, values and units match the plotted data.
- Change range, series, measure and vintage; distinguish intentional resets from accidental loss of work.
- Pin an observation, rotate/resize, and check both the selection and keyboard focus.
- Reload a shared view and verify its filters, range and vintage. A temporary inspection pin is local to the current view, not a promised URL feature.
- Check narrow screens, overflow, control target sizes, focus visibility, readable states and source links.
- Resolve substantive findings, rerun regression checks, and record the review scope and any limitations here.

## Readable-record gate — 1.1.0, September 28, 2026

Content, portfolio-manager and UI reviewers approved with no P0/P1/P2 findings after correction. Content independently recomputed all 28 ALFRED vintages from their hashed raw responses and both forecast objects; found and closed a four-versus-five-horizon SEP parser defect. Corporate CIK/form/item/link bindings were independently matched to all six original responses. Subsequent per-category quotas preserve operating reports alongside ownership entries; a fixture verifies that 80 ownership entries cannot crowd out an annual report. Acceptance times are retained when supplied.

The designer reviewed desktop/mobile calendar, ALFRED, Outlook and Business screenshots. Keyboard focus is restored after month/day/vintage actions; a persistent calendar status announces selected-day counts. Parent browser tests covered date selection and source-backed day contents, responsive overflow, vintage state after reload, GDP base mismatch protection, actual vintage CSV download, five-row projection table, company/form filtering and legal explanations. The final code suite contains 29 Python and 12 JavaScript tests.

Political disclosures, full-document case/filing analysis, remaining forecast providers and historical prediction-market overlays are not represented as completed work. Current legal explanations describe procedure and feed content only. Licensing scope reflects the owner's explicit noncommercial-attribution choice; this review does not certify legal enforceability.

## Core gate — 0.1.0, September 28, 2026

Three separate subagents reviewed content/data integrity, portfolio-manager utility, and design/accessibility. Each initially requested changes; each subsequently explicitly approved the corrected core with no remaining P0/P1/P2 findings in its scope.

### Content

Corrected Treasury announcement URLs (verified official PDFs); retained court publisher GUIDs, merged descriptions and original document links; sorted offset timestamps by actual instant; fixed spread units and quarterly labels; stabilized calendar IDs across rescheduling; preserved hashes/raw paths on failed refreshes. Verified the specific CACD entries previously conflated. Reparsed original evidence while preserving capture timestamps. Approval limits: source metadata and supplied public records, not comprehensive legal coverage or independent verification of every document's substance.

### Portfolio-manager utility

Made economic/policy events the default calendar instead of burying them among expected regulatory publications. Excluded elapsed timed events from upcoming catalysts. Clarified daily, weekly, monthly and quarterly periods. Approved the bounded research product with BLS/SEC gaps and reference-only forecasts/patents/markets explicitly visible.

### Design and accessibility

Responsive charts use container width and fewer mobile ticks; mobile labels remain 13px. Record dialog is named, result updates preserve keyboard focus and announce counts, Save/Unsave labels track state, and chart inspection supports pointer/tap. Reviewed screenshots at desktop, 390px and 320px, with full-page capture artifacts noted as a testing-tool limitation. Core approved; ordinary viewport captures retained for further release QA.

## Approved extensions

1. PM recommendation: saved exposure lenses with transparent keyword/field matches, not inferred issuer exposure or materiality scores.
2. Content recommendation: compare successive successful source captures, distinguishing new documents, schedule changes, new periods and revisions. Never interpret a record leaving a rolling feed as withdrawal.
3. Design recommendation: preserve research-view state in shareable URLs where appropriate.

## Extension gate — 0.2.0, September 28, 2026

All three reviewers explicitly approved the extensions with no remaining P0/P1/P2 findings. Content independently reconstructed the corrected first capture from retained raw evidence and reproduced all 267 newly captured documents and 26 metadata changes in the second capture, with no missing or spurious differences. PM verified literal match explanations and the distinction between research leads and inferred exposure. Design verified clean desktop/mobile screenshots and corrected lens-deletion focus and announcements; parent browser assertions independently exercised the interactions. Local-only saved-list sharing caveat and final deletion-status wording were also corrected.

Validation: 18 Python tests and 6 JavaScript tests passed. Browser tests covered navigation, shareable calendar/series state after reload, lens creation and exact match reasons, record dialog, lens deletion focus and announcement, 390px responsive chart/no page overflow, and real ICS/CSV downloads. Ordinary screenshots were used for final visual review after asynchronous route/resize settling.

Nonblocking next-release opportunities: field-level metadata diffs; lenses on the change page; broader overview change summaries; one evidence-joined dossier before broadening subject desks. The later newspaper-style editorial direction is recorded in EDITORIAL.md as a design, not misrepresented as shipped coverage.

## Live publication gate — September 28, 2026

Initial GitHub Pages publication [run 36488493922](https://github.com/AustinMermans/public-record/actions/runs/36488493922) succeeded. A complete GitHub-hosted collection, validation, evidence commit and deployment [run 36488551477](https://github.com/AustinMermans/public-record/actions/runs/36488551477) also succeeded. The public release receipt reported capture 2026-09-28T21:48:59Z with 5,746 records, 540 calendar events (including captured history and expected regulatory publication) and 13 series. Twenty-two of 24 collectors succeeded; BLS calendar and SEC current filings remain explicit unavailable channels.

The public data.json and app.js SHA-256 values matched the locally reconstructed build. The live front page rendered the captured data, coverage gaps and source links. The README link, repository homepage/description, HTTPS Pages endpoint and remote feature branches/tags were verified. These checks authorize the 1.0.0 application-version promotion; they do not certify every source document's substance or future availability.
