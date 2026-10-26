# Synthetic pipeline: quickstart and contract

This is the first end-to-end engineering slice for the Observatory. It proves a
repeatable flow without collecting third-party data or implying that any source
has been cleared for use. The fixture is invented and must never be presented
as a real map of Volusia County.

## Run locally

From the repository root:

```sh
python -m unittest discover -s tests -v
python scripts/build_synthetic_product.py --output-dir build/synthetic-product --bundle-dir build/synthetic-product-bundle
python scripts/verify_synthetic_provenance.py --input tests/fixtures/synthetic-places.geojson --output-dir build/synthetic-product
python scripts/compare_product_runs.py --before build/synthetic-product/normalized.geojson --after build/synthetic-product/normalized.geojson --output build/change-report/self-comparison.json
python scripts/validate_source_rights.py
python scripts/validate_products.py
```

The pipeline uses only the Python standard library. It reads a GeoJSON
FeatureCollection, checks the expected Point/attribute contract, rejects
duplicate IDs and invalid WGS84 longitude/latitude, normalizes feature order,
and writes:

- `build/synthetic-product/normalized.geojson` — deterministic normalized data.
- `build/synthetic-product/qa-report.json` — checks, counts, extent, and errors.
- `build/synthetic-product/provenance.json` — input/output SHA-256 hashes and
  pipeline version.

Identical input bytes and pipeline version produce byte-identical artifacts.
No build timestamp is inserted, so hashes remain useful for comparisons.

## Compare two product runs

Use `scripts/compare_product_runs.py` to compare two normalized GeoJSON files
by stable `properties.id`, not row order. The report includes input hashes,
added and removed IDs, changed feature IDs with before/after attribute values,
geometry-change flags, counts, and before/after extents. Longitude extents use
the shortest circular interval; when a bounding box crosses the antimeridian,
its west longitude is greater than its east longitude, as permitted by GeoJSON.
Do not treat such a bbox as a conventional west-to-east interval without
checking for this wrap condition. For example:

```sh
python scripts/compare_product_runs.py \\
  --before build/run-a/normalized.geojson \\
  --after build/run-b/normalized.geojson \\
  --output build/change-report/run-a-to-run-b.json
```

The command rejects malformed data, duplicate IDs, unsupported geometry types,
and invalid coordinates rather than producing a partial report. Identical
feature content in a different order is reported as unchanged. For geometry
changes, it also reports great-circle movement in meters and applies a
configurable threshold for triage (default 0 meters):

```sh
python scripts/compare_product_runs.py \\
  --before build/run-a/normalized.geojson \\
  --after build/run-b/normalized.geojson \\
  --movement-threshold-meters 25 \\
  --output build/change-report/run-a-to-run-b.json
```

The report separates geometry movement above the chosen threshold from
movement at or below it, and summarizes the number exceeding the threshold.
Optionally supply a review-rules JSON file to classify changed features by
severity. The example `config/change-review-rules.example.json` demonstrates
low default severity, medium geometry severity, and high category-change severity:

```sh
python scripts/compare_product_runs.py \\
  --before build/run-a/normalized.geojson \\
  --after build/run-b/normalized.geojson \\
  --rules-json config/change-review-rules.example.json \\
  --output build/change-report/run-a-to-run-b.json
```

The report records the effective rules and SHA-256 of the supplied rules file;
feature severity is the highest configured severity among its changed geometry
and properties. Valid levels are `info`, `low`, `medium`, `high`, and
`critical`. Severity is a configurable review-priority label, not a probability,
risk determination, or automatic publication decision.
Distance uses a spherical great-circle calculation and handles antimeridian
crossings. The threshold is a review heuristic—not a positional-accuracy
statement, a determination of real-world significance, or a release gate by
itself. The report does not establish source rights, privacy approval, or
publication eligibility.

## Product-bundle handoff

The optional `--bundle-dir` flag packages the three generated artifacts with
`product.json`, `sources.json`, and `method.md` in a dated, standards-shaped
draft bundle. The bundle is written under `build/`, not `data/`, and is not a
published product. Its privacy review deliberately remains incomplete
(`reviewed: false`), so `python scripts/validate_products.py --data-dir
build/synthetic-product-bundle` must reject it until a human reviewer records
the required review. This is an intentional release-gate test, not a validation
failure to suppress. Do not change the review fields merely to make CI green.

## Fail-closed behavior

On invalid input, the pipeline writes a failure QA report, returns exit code 1,
and does not emit normalized data or provenance. It removes stale data/provenance
outputs from a prior successful run in the same output directory. This prevents
a failed run from leaving old outputs looking current.

## Deliberate limits

This is a synthetic-fixture pipeline, not a real-source ingestion connector and
not a publication approval mechanism. It does not validate polygon topology,
external source licenses, source truth, field conditions, or privacy risk in
real datasets. The provenance record explicitly sets `publication_authorized`
to `false`. Human rights, privacy, factual, and product review gates remain
mandatory for any future real-source product.

## Baseline identity and release-gate evaluation

Supply explicit immutable/versioned run identifiers when comparing a baseline and candidate. Avoid mutable labels such as “latest”:

```sh
python scripts/compare_product_runs.py --before build/run-a/normalized.geojson --before-id places-v1 --after build/run-b/normalized.geojson --after-id places-v2 --output build/change-report/change.json
python scripts/evaluate_change_release.py --report build/change-report/change.json --rules-json config/release-gate-rules.example.json --output build/change-report/release-gate.json
```

The example policy requires both run IDs, blocks critical-severity changes, and blocks any removals. The evaluator exits 2 when policy blocks the candidate, 1 for invalid inputs/policy, and 0 when eligible for human release review. Eligibility is not publication authorization: source rights, data quality, factual review, privacy, and product-owner approval remain independent gates. IDs are supplied labels; content hashes are not digital signatures.

## Content-addressed baseline registry

The registry binds a stable run ID to the exact dataset file hash, pipeline version, and a description. Register each dataset version once; the CLI rejects attempts to reuse a run ID. A changed file must receive a new ID. The JSON registry is not a signed ledger: protect write access and preserve reviewed copies for stronger audit history.

```sh
python scripts/baseline_registry.py register --registry build/baseline-registry.json --run-id places-v1 --dataset build/run-a/normalized.geojson --pipeline-version 0.1.0 --description "Reviewed baseline dataset"
python scripts/baseline_registry.py register --registry build/baseline-registry.json --run-id places-v2 --dataset build/run-b/normalized.geojson --pipeline-version 0.1.0 --description "Candidate dataset for review"
python scripts/compare_product_runs.py --before build/run-a/normalized.geojson --before-id places-v1 --after build/run-b/normalized.geojson --after-id places-v2 --registry build/baseline-registry.json --output build/change-report/change.json
```

With `--registry`, comparisons require both run IDs to exist and both file hashes to match. Missing IDs, unknown versions, malformed registries, or content drift fail closed. This does not prove source authority or who approved a run; those remain separate controls.

## Deterministic release-evidence manifest

The release-evidence tool ties the exact candidate artifacts, baseline/candidate run identities, change report, release-gate decision, and human review record into one deterministic manifest. It verifies dataset hashes against both the change report and content-addressed baseline registry before producing evidence.

The required review record is JSON with schema version 1 and four independent gates: `source_rights`, `privacy`, `factual_quality`, and `product_owner`. Each gate requires an explicit `approved` decision, reviewer, ISO date, and evidence reference. A pending or missing review fails closed. A blocked change gate or hash mismatch also fails closed.

Example invocation:

```sh
python scripts/build_release_evidence.py \
  --product-dir build/synthetic-product \
  --before-dataset build/synthetic-product/normalized.geojson \
  --after-dataset build/synthetic-product/normalized.geojson \
  --registry build/baseline-registry.json \
  --change-report build/change-report/self-comparison.json \
  --release-gate build/change-report/release-gate.json \
  --reviews config/release-reviews.example.json \
  --output build/release-evidence/manifest.json
```

The synthetic fixture intentionally records `publication_authorized: false`, so a structurally valid evidence manifest reports `blocked` even when example review fields are populated. The example review file is deliberately pending and must never be treated as actual human approval. Do not replace its values merely to get a green check. Exit code 2 means evidence was built but the candidate remains blocked; exit code 1 means invalid or inconsistent evidence. This manifest is not a signature, approval authority, source license, or tamper-proof ledger.

The builder copies each input into the output directory under a role-specific filename, so identically named source files cannot overwrite each other. The bundle includes the exact release policy and all artifacts referenced by the manifest. Verify it independently after copying or moving the directory:

```sh
python scripts/verify_release_evidence.py --manifest build/release-evidence/manifest.json
```

The verifier checks every bundled artifact hash, confirms the change report's before/after hashes match the bundled datasets, and recomputes the release-gate decision from the bundled policy. It rejects policy/report drift and does not accept a manifest as publication authorization. Hashes detect accidental or uncoordinated changes; an attacker able to replace both manifest and artifacts can recompute them, so use signed attestations or access-controlled immutable storage when adversarial tamper resistance is required.

## Signed release attestations and release history

The optional attestation layer signs the exact, independently verified manifest with
Ed25519. Install the optional dependency in `requirements-security.txt`; keep the
private key outside the repository and provide it only through a controlled signing
environment. The private key must be an unencrypted PEM Ed25519 key for this CLI;
do not place it in CI logs, artifacts, source control, or this repository's secrets
unless a separately reviewed signing workflow explicitly requires that design.

Generate a key pair using a trusted local security tool or key-management service.
For a local test key only, OpenSSL can generate PEM Ed25519 keys:

```sh
openssl genpkey -algorithm Ed25519 -out release-signing-private.pem
openssl pkey -in release-signing-private.pem -pubout -out release-signing-public.pem
```

Sign only after building and independently verifying the bundle:

```sh
python scripts/verify_release_evidence.py --manifest build/release-evidence/manifest.json
python scripts/sign_release_attestation.py sign \
  --manifest build/release-evidence/manifest.json \
  --private-key /secure/path/release-signing-private.pem \
  --issuer "release-review-system" \
  --output build/release-evidence/attestation.json
python scripts/sign_release_attestation.py verify \
  --attestation build/release-evidence/attestation.json \
  --public-key /trusted/path/release-signing-public.pem \
  --manifest build/release-evidence/manifest.json
```

The signed payload binds the manifest SHA-256, all artifact hashes, policy hash,
human-review-record hash, decision, issuer, key fingerprint, and issuance time.
Verification requires an explicitly supplied trusted public key and also reruns
the existing bundle verifier. A signature proves integrity and possession of the
corresponding private key; it does not establish that the issuer was entitled to
approve a release, that review evidence is true, that data is licensed, or that
publication is authorized. The current verifier deliberately accepts only the
blocked, non-authorizing synthetic evidence bundle.

A local hash-linked history can record signed-attestation files:

```sh
python scripts/release_history.py append \
  --history build/release-history.jsonl \
  --attestation build/release-evidence/attestation.json
python scripts/release_history.py verify \
  --history build/release-history.jsonl \
  --attestation-dir build/release-evidence
```

The JSONL chain detects accidental edits, reordering, and missing/replaced
attestation files relative to its stored hashes. It is not append-only against an
administrator who can rewrite the whole file, and it does not itself verify
signatures. Preserve the ledger, attestations, and trusted public-key records in
access-controlled or immutable storage, with an external checkpoint/anchor, for
stronger audit guarantees. CI tests use ephemeral keys and synthetic blocked
evidence only; CI does not sign production releases or append a release ledger.
