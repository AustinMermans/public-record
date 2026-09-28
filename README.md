# Public Record

A source-linked observatory for US economic releases, regulation, corporate disclosure, and legal activity. Private source repository; public, read-only GitHub Pages publication.

## Development

Python 3.11+ and Node 22+. No application dependencies or API keys are required for the core.

```sh
python3 scripts/collect.py
python3 -m unittest discover -s tests
python3 scripts/build.py
python3 -m http.server 8040 --directory dist
```

Source responses and collection receipts live in `data/`; only normalized public records and site assets enter `dist/`. Collection failures are explicit and retain the last successful snapshot. Observed snapshots are not historical ALFRED vintages. See `docs/METHODOLOGY.md`.

## Versioning

Semantic Versioning: `v0.0.0` is the founding specification. Development proceeds on `feat/core-observatory`; review and extension releases are tagged in the `0.x` series. `v1.0.0` is reserved for reviewed functionality verified on GitHub Pages. Conventional commit prefixes (`feat`, `fix`, `docs`, `test`, `chore`) describe each change. Main remains deployable; data-only refreshes do not change the application version.

## Publication

The source repository must remain private. GitHub Pages is public and contains public-source records only. Scheduled collection is bounded, cached, and observable. No investment recommendations or trade execution are provided.
