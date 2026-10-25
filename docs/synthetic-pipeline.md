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
geometry-change flags, counts, and before/after extents. For example:

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
