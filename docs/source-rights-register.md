# Machine-readable source rights register

The canonical register is [`config/source-rights.json`](../config/source-rights.json). It tracks each candidate separately and distinguishes:

- `true`: the documented terms explicitly permit the named use for the reviewed source/version.
- `false`: the review found the use is not permitted.
- `null`: permission is unknown or has not been evidenced. This is **not** permission.

A source decision is scoped to the recorded item, terms, intended product, and uses. Do not copy an approval to adjacent layers, new versions, or different outputs.

## Current gate

All candidates reviewed in the initial Volusia inventory are blocked pending rights review, except Trail Features (layer 30), which is rejected from the trail inventory pending semantic review. The current VOTRAN GTFS index is recorded as a candidate only; the archive has not been captured or validated.

The register is a documentation and governance control, not a legal opinion. Its validator checks internal consistency; it cannot determine whether a license actually grants the rights claimed.

## Validate locally

Run:

```sh
python scripts/validate_source_rights.py
python -m unittest discover -s tests -v
```

The CI workflow runs the rights validator and unit tests on relevant changes. The validator rejects approvals without retained terms evidence and explicit per-use permission. An `APPROVED` decision requires all listed uses to be explicitly permitted; narrower permission should be recorded as `APPROVED_WITH_CONDITIONS` or `INTERNAL_ONLY` with a correspondingly limited use map.

## Review and update procedure

1. Identify the actual rights holder and authoritative source item.
2. Preserve the exact terms URL and durable evidence reference, date, version, and required attribution.
3. Set each use to `true`, `false`, or `null` based on the evidence; do not infer from public availability or an “as is” disclaimer.
4. Clear unresolved questions only when the evidence addresses them.
5. Run the validator and tests, review the diff, and obtain normal PR approval before merging.
6. Re-review when the source version, license, output, spatial join, or distribution changes.

No bulk collection or public release should be enabled by this register alone; data QA, privacy review, provenance, and product validation remain separate gates.
