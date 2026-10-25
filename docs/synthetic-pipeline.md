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
feature content in a different order is reported as unchanged. The report is a
deterministic change inventory, not an assessment of operational significance,
source rights, privacy risk, or publication eligibility.

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
