# Public Record

**Dashboard: [austinmermans.github.io/public-record](https://austinmermans.github.io/public-record/)**

A source-linked observatory for US economic releases, regulation, corporate disclosure, and legal activity. Public source repository and read-only GitHub Pages publication, as authorized by the owner.

## Read the edition

- **Front page:** economic context, upcoming catalysts and a balanced selection across disclosure channels.
- **Calendar:** searchable official schedules, regulatory publication dates and filtered iCalendar exports.
- **Economy:** 13 historical series with explicit units, transformations, source links and CSV exports.
- **Disclosures:** government and selected court records, original documents, local reading lists and saved keyword lenses with transparent match reasons.
- **Changes:** differences between successful captures, separating new documents, revisions and schedule changes.
- **Outlook and sources:** forecast/research references, collector health and coverage boundaries.

The editorial direction is a newspaper-like research publication, not a directory of APIs. Subject desks and cross-cutting dossiers should connect siloed evidence while keeping facts, interpretation and unresolved questions distinct. See [the editorial architecture](docs/EDITORIAL.md) for the next-stage design; planned desks are not claims of current ingestion.

## Development

Python 3.11+ and Node 22+. No application dependencies or API keys are required for the core.

```sh
python3 scripts/collect.py
python3 -m unittest discover -s tests
node --test tests/*.test.mjs
python3 scripts/build.py
python3 -m http.server 8040 --directory dist
```

Source responses and collection receipts live in `data/`; only normalized public records and site assets enter `dist/`. Collection failures are explicit and retain the last successful snapshot. Observed snapshots are not historical ALFRED vintages. See `docs/METHODOLOGY.md`.

## Versioning

Semantic Versioning: `v0.0.0` is the founding specification. Development proceeds on reviewed feature branches; core and extension releases are tagged in the `0.x` series. `v1.0.0` is reserved for reviewed functionality verified on GitHub Pages. Conventional commit prefixes (`feat`, `fix`, `docs`, `test`, `chore`) describe each change. Main remains deployable; data-only refreshes do not change the application version.

## Publication

Repository and GitHub Pages contain public-source records only. Scheduled collection is bounded, cached, and observable. No investment recommendations or trade execution are provided.

The publication workflow refreshes sources at **13:43 and 21:43 UTC, Monday–Friday**, subject to GitHub Actions availability/delays. It is not a real-time service. Manual dispatch can also refresh. Tests and data validation precede deployment; source evidence is committed before the site is published. Failed collectors retain their last successful data with explicit stale/unavailable labels.

At launch, BLS calendar and SEC current-filing requests are blocked from the collection environment. Direct source links remain available. Court feeds are partial, Federal Register published coverage is latest-100, and forecasts, patents and prediction markets are reference-only. FRED history is currently revised history, not original-release vintages. See [methodology](docs/METHODOLOGY.md) and [independent reviews](docs/REVIEWS.md).
