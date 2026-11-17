# Observatory maintenance — November 17, 2026

This record covers workflow reliability and consolidation of older governance
PRs. ZQM Observatory remains a ZQM Computing prototype. No production deployment,
real-source collection, source-rights approval, or data publication is included.

## Workflow fixes

[PR #77](https://github.com/ZQM-Computing/zqm-observatory/pull/77) fixes persistent
layer visibility, count queries with mixed geometry types, and prepared private
Data Prep results between the browser's 2 MB upload budget and the existing
8 MB project budget. Private source uploads remain limited to 4 MB.

Shared projects retain ordinary Unicode as UTF-8 and escape lone UTF-16
surrogates. HTTP tests cover large CJK projects, truncated emoji names, legacy
documents and operation receipts, and identical retries. SQLite handles close
after commit or rollback. Desktop browser QA verifies that visibility changes
in both directions and survives reload; see the
[app QA record](../apps/map-explain/QA.md).

## Older PR disposition

These branches overlap stronger checks already on main. Their useful missing
behavior is consolidated rather than merging the older branches wholesale.

| PR | Adopted behavior or retained policy | Regression evidence |
| --- | --- | --- |
| [#64](https://github.com/ZQM-Computing/zqm-observatory/pull/64) | `INTERNAL_ONLY` requires an explicit non-public permission; malformed decisions and blocked/rejected grants remain rejected. | `test_internal_only_requires_explicit_non_public_permission` and existing malformed-decision tests |
| [#65](https://github.com/ZQM-Computing/zqm-observatory/pull/65) | Non-layer and non-ASCII layer paths make no request; protocol errors remain per-source failures; response ID must match the requested URL even without a registered ID. Full register validation remains required. | Metadata preflight tests for skipped paths, wrong IDs, and continuation after `IncompleteRead`/`BadStatusLine` |
| [#66](https://github.com/ZQM-Computing/zqm-observatory/pull/66) | Drafts require verified canonical fixture outputs. Reruns invalidate old reviews before assets change; failures clear only pipeline-owned bundle files. | CLI invalid/custom-input reruns, interrupted rebuild, tampered/rehashed assets, and preservation of unrelated notes |
| [#68](https://github.com/ZQM-Computing/zqm-observatory/pull/68) | Malformed geometry types and write failures clear stale artifacts; IDs are compared after trimming; empty GeoJSON omits `bbox`; passing QA is written last. Existing unreadable-input cleanup is retained. | Stale-output, output-write/QA-write failure, whitespace-ID, malformed-geometry, and empty-collection tests |
| [#69](https://github.com/ZQM-Computing/zqm-observatory/pull/69) | Bundle-wide symlink rejection remains stronger than asset-only checking. A malformed source URL does not prevent validation of later bundles. | Symlink-loop and malformed-URL/later-bundle tests |
| [#71](https://github.com/ZQM-Computing/zqm-observatory/pull/71) | Canonical paths remain required. `./brief.csv` and duplicate separators are rejected; the older test's normalization expectation is deliberately superseded. | `test_noncanonical_declared_paths_are_rejected` plus existing bundle-wide symlink tests |

## Validation and limits

- 51 app tests, TypeScript checks, and production builds passed on Node 22.23.5
  and Node 24.
- All 16 private-service/GIS tests passed without skips.
- All 167 governance tests passed, including failure and interruption regressions.
  Synthetic CLI checks verified build/provenance, baseline registration, comparison,
  release triage, and the expected privacy block. Pipeline version is 0.1.1; CI
  and quickstart registry examples use that version.
- GitHub prose checks pass for the workflow PR. Self-hosted Windows validation
  remains queued; local evidence does not establish a completed CI run.

Canonical draft packaging deliberately fails the publication validator until a
human privacy review is recorded. Custom Point inputs still support artifact-only
builds. Source permission, factual accuracy, privacy, and product release remain
separate human gates. Authenticated browser sync, device GPS/mobile checks, and
production operation remain unverified.
