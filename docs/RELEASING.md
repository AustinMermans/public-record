# Release procedure

The application version describes shipped functionality, not the age of its data. `VERSION` is the source of truth; the build copies it into `data.json` and `release.json`. Each collector retains its own capture and last-success timestamps. A successful build does not certify that every source is fresh.

## Choosing a version

- **Patch** (`1.3.1`): compatible correctness, accessibility, responsive-layout or security fixes.
- **Minor** (`1.4.0`): additive desks, datasets, search capabilities, analytical displays or other user-facing features that preserve supported contracts.
- **Major** (`2.0.0`): incompatible changes to documented public data schemas, exports, or supported shareable URLs. Document migration guidance; visual redesign alone does not require a major version.
- **No application bump**: routine captures and documentation/test/tooling-only commits. These remain traceable by commit and capture timestamp. They can accompany the next application release.

This project currently publishes stable versions only. Feature-branch builds retain the last released version until the release candidate is prepared; they are not new public releases. Use branch/commit identity to distinguish development builds. If prereleases are needed later, extend the validator and procedure explicitly before introducing them.

## Implementation and release gate

1. Start a scoped `feat/…` or `fix/…` branch from the current main. Preserve unrelated work. Use conventional commit prefixes and record implemented, unpublished changes under `Unreleased` in `CHANGELOG.md`; keep unimplemented roadmap items elsewhere.
2. Complete tests, source reconciliation, responsive/browser checks and relevant independent reviewer passes. Record the review scope and unresolved limitations in `docs/REVIEWS.md`. Approval of one increment does not establish completion of the full product goal.
3. Select the next version. Update `VERSION`, the `version` and `date-released` fields in `CITATION.cff`, and a dated changelog entry together. Move only completed work out of `Unreleased`. Never rewrite a released version's notes to claim later features.
4. Run `python3 scripts/versioning.py --tag vX.Y.Z`, `python3 -m unittest discover -s tests`, `node --test tests/*.test.mjs`, `node --check site/app.js`, and `python3 scripts/build.py`. The build rejects inconsistent release metadata.
5. Merge the reviewed release to main. Wait for the publication workflow; for collector changes, also run and verify a hosted refresh. Verify the public `release.json`, application assets and data against the expected deployed build. Distinguish the deployed commit from any subsequent data-only commit. Report a failed deployment as failed, not as a release.
6. Create the immutable `vX.Y.Z` tag at the verified deployed commit and a GitHub release linking to the live site and the applicable changelog entry. Confirm the tag resolves to that commit. Never move an existing version tag to replace a faulty release; correct the issue in a new patch release.

The full expansion goal remains separate from release numbering. A useful, reviewed minor release can ship while additional source coverage or investor workflows remain unfinished.
