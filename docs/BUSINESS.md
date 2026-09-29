# Business desk

The Business front is a searchable reading surface over the selected SEC submissions capture. It covers 25 registrants, including separate old/new Exxon identities; it does not promise the full listed-company universe or the full EDGAR history. The underlying per-form capture quotas are documented in COMPANY-COVERAGE.md.

## Headlines and detail

Headlines describe filing forms and recorded 8-K item codes. The [SEC Form 8-K](https://www.sec.gov/files/form8-k.pdf) is the item-definition reference. A substantive known item leads ahead of general disclosure/exhibit items, while the explanation preserves every recorded code. Unknown codes remain visible. Leadership/compensation categories do not assert that a departure occurred; proposed-sale notices do not prove completed sales; nomination timing does not prove nominations. Amendments retain their label.

Clicking a headline opens the company profile at the exact selected accession, with date, reported period, item explanation and original document. These are metadata-based reading aids. Specific terms, counterparties, document-body announcements and independent news are not yet extracted.

## Search and selection

Exact covered tickers resolve issuer identity before general text matching. Numeric CIKs accept padded, unpadded or `CIK `-prefixed values; bare `3`, `4`, `5` and `144` resolve filing forms, so use the prefix for ambiguous CIKs. Item queries such as `5.03` or `Item 5.03`, filing forms and full accession numbers use structured fields. Other queries match token prefixes for partial names and topics.

The default excludes ownership forms 3/4/5 and proposed-sale Form 144. All selected filings remain accessible under separate topic filters or All selected filings. Twelve headlines per page are sorted by acceptance time, falling back to filing date, with deterministic accession/CIK tie breaks. Search, topic and page are encoded in URLs; new filters reset pagination. The company sidebar matches issuer identity independently from disclosure topics.

## Financial context

Briefs use the validated SEC companyfacts bundle. Source-reported USD revenue and net income must match the controlling report accession and URL. An unrelated event never receives the latest periodic-report financials. Current/prior comparisons require a validated comparable row, matching concepts and positive prior values; zero/negative priors do not produce percentage changes. Periods and the financial channel's own capture/stale state remain visible. Company profiles retain the fuller financial tables and evidence.

## Interaction and verification

Search updates preserve the input and persistent status node. Input blur does not redraw a clicked headline or pagination link. Native links preserve ordinary browser behavior; page navigation and selected filings restore focus to their detail targets. The layout stacks on narrow screens.

The Business tests cover identity/item/form query boundaries, source-bound financial briefs, amendments, missing/unknown items, escaping, pagination and the blur/live-region regression. Browser verification and independent release-gate outcomes are recorded in REVIEWS.md.
