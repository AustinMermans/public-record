# Public Record

**Dashboard: [austinmermans.github.io/public-record](https://austinmermans.github.io/public-record/)**

A source-linked observatory for US economic releases, regulation, corporate disclosure, and legal activity. Public source repository and read-only GitHub Pages publication, as authorized by the owner.

## Read the edition

- **Front page and desks:** cross-section publication front page; separate Economy, Business, Government & Politics, Disclosures, Outlook and Changes landing pages, with deeper tools and breadcrumbs.
- **Search:** name, ticker, CIK, topic and filing-form search across captured metadata, with verified issuer-exhibit headlines/excerpts where available. Company profiles rank ahead of documents; filters, pages and company-name scopes are shareable. This is not full-document or whole-web search.
- **Calendar:** month grid and selected-day agenda, filters, official schedules and filtered iCalendar exports.
- **Economy:** 24 series: 13 FRED macro histories, two bounded New York Fed rate histories, and nine OFR index/contribution histories. Transformations and CSV exports; optional sampled ALFRED vintages for GDP, payrolls, unemployment and CPI. The [GDP release record](https://austinmermans.github.io/public-record/#gdp-releases) separately shows recent BEA advance, second and third real-GDP estimates as published, with exact release links and retrieval evidence; it does not infer precise revisions from rounded values. The [energy read](https://austinmermans.github.io/public-record/#energy) adds source-reconciled EIA weekly crude, gasoline and distillate inventories, interactive histories, a five-year same-season reference, and expected release-calendar entries. See [GDP](docs/BEA-RELEASES.md) and [energy](docs/ENERGY.md) methods.
- **Funding & credit:** a [dated credit read](https://austinmermans.github.io/public-record/#funding) places same-date SOFR/EFFR, OFR global stress/credit contribution and FDIC quarterly loan-quality measures side by side, with separate clocks and direct sources. Detailed rate/volume charts and FDIC banking histories remain available. This is not a composite score or a synchronized credit trend. See [credit-read methodology](docs/CREDIT-READ.md), [funding methodology](docs/FUNDING.md) and [banking methodology](docs/BANKING.md).
- **Fiscal:** Treasury receipts, outlays, net interest and the deficit with matched fiscal-year-to-date comparisons; a source-reconciled accounting bridge and interactive monthly history. Exact-dollar inputs and one-edition history, not mixed original-release vintages. See [fiscal methodology](docs/FISCAL.md).
- **Business:** a [searchable headline desk](https://austinmermans.github.io/public-record/#business), 25 SEC registrant profiles, topic filters and complete pagination through selected filings. A single-company match puts issuer identity and filing-anchored financial context first. Recent Item 2.02 reports show exact issuer exhibit headlines and short source-linked excerpts when reliably extracted; other entries fall back to SEC form/item metadata. Three current matched issuer results (Amazon, Lilly and Home Depot) add [short earnings reads](docs/ISSUER-READS.md) that separate issuer-reported drivers, unusual items and guidance from 10-Q facts, with claim-level source cues. Search exact tickers, CIKs, forms, accession numbers or reported 8-K items, plus company names, topics and captured exhibit text. Ownership forms have their own filter. CIK-linked filings remain separate from unverified name matches; current and prior Exxon registrants stay distinct. This is not independent news reporting or full-document coverage.
- **Government & Politics:** federal fiscal conditions alongside institutional coverage from Federal Reserve communications and Federal Register activity. Politician profiles, votes and political-finance data remain planned.
- **News & announcements:** captured Federal Reserve press releases; explicitly official communications, not independent reporting or a comprehensive news service.
- **Disclosures:** government and selected court records, original documents, local reading lists and saved keyword lenses with transparent match reasons.
- **Changes:** a unified edition across economic data, company filings/financial facts, funding, forecasts, disclosures and calendars. Active desks lead; court-feed changes are summarized by publisher and distinct docket links, not promoted as ranked legal news. Source-linked values and analytical drill-downs lead to a complete company/desk/source/type-filtered ledger with shareable pagination. Each channel retains its own successful-capture window.
- **Outlook and sources:** the [inflation watch](https://austinmermans.github.io/public-record/#inflation-watch) shows dated Cleveland Fed CPI/PCE model estimates, each measure's next pending target and the publisher's current-edition monthly forecast path; it does not reconstruct original daily editions. A [one-quarter GDP watch](https://austinmermans.github.io/public-record/#outlook?forecast=gdp-watch) aligns dated GDPNow, Philadelphia Fed SPF and BEA advance-or-pending evidence for the same real-GDP target without treating them as a single forecast. Select a target quarter to see how its SPF forecast moved across surveys, with workbook-cell and release-date evidence. Extracted FOMC projections and other SPF medians remain separate. Historical SPF cells are from the current official workbook edition, not reconstructed original-release files. See [inflation](docs/INFLATION.md), [GDP watch](docs/GDP-WATCH.md), [SPF methodology](docs/SPF.md), further references and collector health.

The editorial direction is a newspaper-like research publication, not a directory of APIs. The bounded credit read and three curated issuer reads are first synthesis units; broader issuer, macro and legal dossiers and additional reporting feeds remain future work. Keep facts, interpretation and unresolved questions distinct. See [the editorial architecture](docs/EDITORIAL.md) and [company coverage](docs/COMPANY-COVERAGE.md).

The broader investor-hub goal remains in progress. The [completion audit](docs/GOAL-AUDIT.md) separates currently ingested providers from missing investor workflows; endpoint counts alone do not establish completion.

## Development

Python 3.11+ and Node 22+. No application dependencies or API keys are required for the core.

```sh
python3 scripts/collect.py
python3 scripts/research.py
python3 scripts/bea_releases.py
# SEC_USER_AGENT must identify the project and an authorized contact address.
python3 scripts/corporate.py
python3 scripts/business_briefs.py
python3 scripts/collect_financials.py
python3 scripts/fiscal.py
python3 scripts/banking.py
python3 scripts/energy.py
python3 scripts/spf.py
python3 scripts/inflation.py
python3 -m unittest discover -s tests
node --test tests/*.test.mjs
python3 scripts/build.py
python3 -m http.server 8040 --directory dist
```

Source responses and collection receipts live in `data/`; only normalized public records and site assets enter `dist/`. Collection failures are explicit and retain the last successful snapshot. Observed snapshots are not historical ALFRED vintages. See `docs/METHODOLOGY.md`.

Company profiles include filing-anchored financial screens with distinct quarter/YTD/balance-sheet periods, source-linked comparatives and calculation inputs. Availability depends on standard facts in the controlling filing, not merely a successful download. See [issuer financials methodology](docs/FINANCIALS.md).

## Versioning

Public Record uses Semantic Versioning. `v0.0.0` was the founding specification; `v1.0.0` was the first reviewed edition verified on GitHub Pages. New capabilities use minor releases (`1.4.0`), compatible corrections use patch releases (`1.3.1`), and incompatible changes to supported public data or URL contracts require a major release. Work proceeds on feature/fix branches with conventional commits. Data-only refreshes do not change the application version: capture timestamps identify the data edition.

`VERSION`, `CITATION.cff`, and the latest released changelog entry must agree; the build enforces this. Pending work belongs under **Unreleased**, not in a shipped release's notes. Version tags are immutable and published only after the reviewed deployment is verified. See the [release procedure](docs/RELEASING.md).

## Publication

Repository and GitHub Pages contain public-source records only. Scheduled collection is bounded, cached, and observable. No investment recommendations or trade execution are provided.

The publication workflow refreshes sources at **13:43 and 21:43 UTC, seven days a week**, subject to GitHub Actions availability/delays. It is not a real-time service. Manual dispatch can also refresh. Tests and data validation precede deployment; source evidence is committed before the site is published. Failed collectors retain their last successful data with explicit stale/unavailable labels. A daily retrieval does not imply a new observation from a business-day or quarterly publisher.

The BLS calendar request remains blocked from the collection environment; other sources can independently become stale or unavailable. SEC access requires the identifying contact supplied through the `SEC_USER_AGENT` Actions secret/environment variable. It is never sent to non-SEC sources. Company requests are sequential, at most two per second, and the workflows are serialized. Court feeds are partial and Federal Register published coverage is latest-100. FOMC/GDPNow/SPF figures are ingested; other forecast providers, patents, political donations, transaction-level insider analysis and prediction-market overlays are not yet ingested. ALFRED dates are sampled vintages, not every original release. See [methodology](docs/METHODOLOGY.md) and [independent reviews](docs/REVIEWS.md).

## License and citation

**Attributed noncommercial reuse only, under the applicable scoped license.** Original software uses [PolyForm Noncommercial 1.0.0](LICENSES/PolyForm-Noncommercial-1.0.0.md); original writing and visualization output use [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Third-party source data is not relicensed. Commercial use outside these grants requires separate permission. This is source-available, not open-source. See [LICENSE](LICENSE), [reuse guidance](docs/REUSE.md) and [CITATION.cff](CITATION.cff).
