# Business desk

The Business front is a searchable reading surface over the selected SEC submissions capture. It covers 25 registrants, including separate old/new Exxon identities; it does not promise the full listed-company universe or the full EDGAR history. The underlying per-form capture quotas are documented in COMPANY-COVERAGE.md.

## Headlines and detail

Most headlines describe filing forms and recorded 8-K item codes. The [SEC Form 8-K](https://www.sec.gov/files/form8-k.pdf) is the item-definition reference. A substantive known item leads ahead of general disclosure/exhibit items, while the explanation preserves every recorded code. Unknown codes remain visible. Leadership/compensation categories do not assert that a departure occurred; proposed-sale notices do not prove completed sales; nomination timing does not prove nominations. Amendments retain their label.

For the newest two non-amended Item 2.02 Form 8-Ks per covered CIK, the collector reads the exact accession's SEC index header and accepts a unique `EX-99.1` text/HTML exhibit only. It extracts an issuer-written headline and one short opening excerpt, which may be a full sentence or a published bullet; the site labels this as issuer text, links to the exhibit and primary 8-K, and exposes capture/stale status. Original index/exhibit bytes and SHA-256 hashes are retained and the build replays extraction. Ambiguous, absent, image-only or unparseable material remains metadata-only; it is not filled with a guessed summary. This is a bounded earnings-announcement channel, not independent news or a complete document-body feed. Item 2.02 material may be **furnished**, not legally filed; “filing” in navigation identifies the SEC accession rather than asserting legal filing status.

The unfiltered Business front leads with the three most recent verified issuer results in this bounded capture, followed by the complete paginated selected-filing stream. It is a recency selection, not a ranking of economic or investment importance. Clicking a headline opens the company profile at the exact selected accession, with date, reported period, item explanation or verified excerpt, and original document. Other filings remain metadata-based reading aids; their specific terms, counterparties and outcomes are not extracted.

## Search and selection

Exact covered tickers resolve issuer identity before general text matching. A single-company match leads with a company spotlight and source-bound financial context. Numeric CIKs accept padded, unpadded or `CIK `-prefixed values; bare `3`, `4`, `5` and `144` resolve filing forms, so use the prefix for ambiguous CIKs. Item queries such as `5.03` or `Item 5.03`, filing forms and full accession numbers use structured fields. Other queries match token prefixes for partial names, topics and verified issuer text. Site-wide filing search opens the on-site accession detail and offers the SEC source alongside it.

The default excludes ownership forms 3/4/5 and proposed-sale Form 144. All selected filings remain accessible under separate topic filters or All selected filings. Twelve headlines per page are sorted by acceptance time, falling back to filing date, with deterministic accession/CIK tie breaks. Search, topic and page are encoded in URLs; new filters reset pagination. The company sidebar matches issuer identity independently from disclosure topics.

## Financial context

Briefs use the validated SEC companyfacts bundle. Source-reported USD revenue and net income must match the controlling report accession and URL. An unrelated event never receives the latest periodic-report financials. Current/prior comparisons require a validated comparable row, matching concepts and positive prior values; zero/negative priors do not produce percentage changes. Periods and the financial channel's own capture/stale state remain visible. Company profiles retain the fuller financial tables and evidence.

Abbreviated financials also carry specialist profile boundaries (bank, insurer, utility, REIT, industrial-finance/perimeter and predecessor/successor registrants) at the point of use. For current XOM coverage, the holding-company and prior Exxon CIKs remain separate: the shown year-over-year changes are periods within the linked current report, not an inferred splice of the two registrant filing histories. The Business match links to the prior registrant explicitly.

## Interaction and verification

Search updates preserve the input and persistent status node. Input blur does not redraw a clicked headline or pagination link. Native links preserve ordinary browser behavior; page navigation and selected filings restore focus to their detail targets. The layout stacks on narrow screens.

The Business tests cover identity/item/form query boundaries, source-bound financial briefs, amendments, missing/unknown items, escaping, pagination and the blur/live-region regression. Browser verification and independent release-gate outcomes are recorded in REVIEWS.md.
