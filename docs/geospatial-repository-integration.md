# Geospatial repository integration map

This document identifies useful handoffs between Observatory and the ZQM Computing geospatial repositories. It is an integration plan, **not evidence that these repositories currently call one another or that an end-to-end pipeline has passed**. The Observatory remains Stage 0; no live product or production service is implied.

The latest repository-level evidence crawl, including inspected commit snapshots, confirmed interfaces, status discrepancies, and the proposed order of integration, is recorded in [supporting-repository-crawl.md](supporting-repository-crawl.md). That crawl is a desk review; it does not claim cross-repository runtime compatibility.

## Guardrails before any handoff

1. Resolve source-specific rights before collecting or redistributing records. A repository's ability to read a format does not grant permission to use the data.
2. Preserve provenance at every step: source identifier and URL, retrieval timestamp, source metadata/hash, transformation command and version, CRS/SRID, output hash, and validation result.
3. Keep raw source, normalized intermediate, and publication-ready outputs distinct. Never overwrite inputs.
4. Use deterministic synthetic fixtures for cross-repository integration tests until a real source is rights-cleared.
5. Treat access, route safety, current service, accessibility, and facility conditions as separate claims; geometry or metadata alone does not prove them.
6. Do not ingest ZQM Labs game telemetry, individual movement traces, personal data, or identifiable children's data.

## Recommended handoff map

| Stage | Repository | Intended handoff | Status and evidence needed |
| --- | --- | --- | --- |
| Source governance and product gate | [zqm-observatory](https://github.com/ZQM-Computing/zqm-observatory) | Rights register and source evidence define whether a source can be collected, transformed, or published. | Governance files and validator exist; individual source permissions remain unresolved. |
| Desktop inspection and dataset QA | [qgis-resources](https://github.com/ZQM-Computing/qgis-resources) | Inspect a rights-cleared local fixture; generate a read-only dataset QA report before transformation. | Separate repository. No Observatory invocation or shared fixture contract verified yet. |
| Format conversion and metadata | [gdal-cookbook](https://github.com/ZQM-Computing/gdal-cookbook) | Convert/reproject bounded synthetic or approved data; preserve input and record GDAL version and command. | Separate examples; no Observatory pipeline wired. |
| Python spatial validation | [geopandas-cookbook](https://github.com/ZQM-Computing/geopandas-cookbook) | Check geometry validity, CRS, duplicate keys, nulls, and spatial joins on the normalized fixture. | Candidate QA stage; exact reusable CLI/interface must be established before automation. |
| Columnar analysis | [geoparquet-cookbook](https://github.com/ZQM-Computing/geoparquet-cookbook) and [duckdb-spatial-cookbook](https://github.com/ZQM-Computing/duckdb-spatial-cookbook) | Exchange GeoParquet with declared CRS/geometry metadata; use DuckDB for reproducible analytical QA and aggregate-only outputs. | File-format/SQL handoff proposed; no shared fixture or end-to-end test yet. |
| Spatial system of record and routing | [postgis-cookbook](https://github.com/ZQM-Computing/postgis-cookbook) and [pgrouting-cookbook](https://github.com/ZQM-Computing/pgrouting-cookbook) | Load approved normalized layers into a disposable PostGIS schema; test topology and routing only when source semantics support it. | No Observatory database or route workflow established. Do not infer safe/public routes from line geometry alone. |
| Raster and imagery | [cog-cookbook](https://github.com/ZQM-Computing/cog-cookbook) and [stac-cookbook](https://github.com/ZQM-Computing/stac-cookbook) | Validate a Cloud Optimized GeoTIFF and catalog approved imagery with STAC metadata and provenance. | Future imagery path; no Observatory STAC catalog exists yet. |
| API and map delivery | [geospatial-api-reference](https://github.com/ZQM-Computing/geospatial-api-reference) and [maplibre-cookbook](https://github.com/ZQM-Computing/maplibre-cookbook) | Serve a synthetic/approved aggregate through OGC API – Features, then render it in a browser map. | Reference examples only; no live Observatory API or frontend connection verified. |
| Spatial aggregation | [h3-cookbook](https://github.com/ZQM-Computing/h3-cookbook) | Produce coarse, documented aggregates where aggregation is analytically appropriate and privacy-reviewed. | Candidate analytical technique, not a privacy guarantee by itself. |

The umbrella [Geospatial Cookbooks index](https://github.com/ZQM-Computing/geospatial-cookbooks) is the catalog for these independently maintained examples. A link between repositories is documentation discoverability, not a runtime dependency.

## Minimal integration contract to implement next

Use one tiny deterministic synthetic dataset (for example, a few points and lines in a declared CRS) and require each stage to produce:

- `manifest.json`: fixture ID, schema version, input hash, CRS, producer repository/commit, tool versions, command, and output paths/hashes;
- a machine-readable QA report with geometry type/validity, feature count, required-field/null checks, CRS, and explicit warnings;
- a nonzero exit on invalid input, mismatched CRS assumptions, missing required metadata, or changed source files;
- no network access and no source records from Volusia while rights remain unresolved.

A cross-repository smoke test should only be called **verified** after CI checks out pinned commits (or versioned releases), runs the actual documented commands, compares expected outputs, and uploads the reports as artifacts. Do not make a floating main branch or a green repository-local badge stand in for compatibility evidence.

## First executable handoff: pinned QGIS dataset QA

The initial offline adapter is implemented in `scripts/run_qgis_dataset_qa_handoff.py`; its contract tests are in `tests/test_qgis_dataset_qa_handoff.py`, and CI is defined in `.github/workflows/external-geospatial-qa.yml`.

The workflow checks out `ZQM-Computing/qgis-resources` at the explicit commit `004d037da5301264d3f2ac462d835f2d5c75f8cb`, installs the GDAL command-line and Python bindings, and runs the upstream `scripts/dataset_qa.py` twice against the Observatory's synthetic GeoJSON fixture. It requires the declared `id` and `name` fields, candidate identifier uniqueness, EPSG:4326, zero warnings, zero errors, matching feature count, byte-identical QA reports, and an unchanged input hash. The workflow uploads both reports and a handoff manifest as a short-retention CI artifact.

The manifest captures the pinned producer commit, Python/GDAL versions, invocation contract, fixture hashes, and QA-report hash. It explicitly records that source-rights, privacy, and human release review are not approved. A successful technical QA handoff is not release authorization.

Run locally in an environment with GDAL Python bindings:

```sh
python -m unittest discover -s tests -p 'test_qgis_dataset_qa_handoff.py' -v
/usr/bin/python3 scripts/run_qgis_dataset_qa_handoff.py \
  --qa-script support/qgis-resources/scripts/dataset_qa.py \
  --fixture tests/fixtures/synthetic-places.geojson \
  --output-dir build/qgis-dataset-qa-handoff \
  --producer-commit 004d037da5301264d3f2ac462d835f2d5c75f8cb
```

CI must be green before this handoff is described as verified. The pinned producer commit is deliberately explicit: updating it requires reviewing the upstream interface and re-running the contract tests.

## Implementation order

1. Add a small synthetic fixture and manifest contract to the best-owned QA entry point, likely `qgis-resources` or a dedicated integration harness.
2. Confirm exact CLI contracts in GDAL and GeoPandas examples; avoid inventing interfaces from cookbook prose.
3. Add one CI workflow that pins repository commits and runs only those proven commands.
4. Extend the same fixture into GeoParquet/DuckDB, then PostGIS/API, only after earlier stages pass.
5. Keep imagery/STAC and routing as separate optional tracks; they have different data semantics and runtime requirements.
