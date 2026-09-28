# Independent product reviews

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
