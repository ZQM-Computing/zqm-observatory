# Geospatial repository integration map

This document separates verified synthetic CI handoffs from candidate integrations. The pinned QGIS dataset-QA and GeoParquet/DuckDB Spatial adapters have executable cross-repository runtime jobs; these verify only their declared contracts. The Observatory remains Stage 0: no live product or production service is implied.

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
| Desktop inspection and dataset QA | [qgis-resources](https://github.com/ZQM-Computing/qgis-resources) | Inspect a local synthetic fixture; generate a read-only dataset QA report before transformation. | Implemented adapter and pinned runtime workflow; this change refreshes the pin to the merged QGIS Resources PR #22 commit `40bf07d435281e46099eb028b1b1a9258cba87ef`. Exact-head CI must pass for the refreshed pin before merge. |
| Format conversion and metadata | [gdal-cookbook](https://github.com/ZQM-Computing/gdal-cookbook) | Convert/reproject bounded synthetic or approved data; preserve input and record GDAL version and command. | Separate examples; no Observatory pipeline wired. |
| Python spatial validation | [geopandas-cookbook](https://github.com/ZQM-Computing/geopandas-cookbook) | Check geometry validity, CRS, duplicate keys, nulls, and spatial joins on the normalized fixture. | Candidate QA stage; exact reusable CLI/interface must be established before automation. |
| Columnar analysis | [geoparquet-cookbook](https://github.com/ZQM-Computing/geoparquet-cookbook) and [duckdb-spatial-cookbook](https://github.com/ZQM-Computing/duckdb-spatial-cookbook) | Exchange GeoParquet with declared CRS/geometry metadata; use DuckDB for reproducible analytical QA and aggregate-only outputs. | Verified synthetic handoff in `scripts/run_geoparquet_duckdb_handoff.py`; pinned commits and runtime workflow are in `.github/workflows/geoparquet-duckdb-handoff.yml`. Exact-head run 40249451463 succeeded for PR #45 head `1308e5a457aab66486fa9e674946d3bc8c2e437e`. |
| Spatial system of record and routing | [postgis-cookbook](https://github.com/ZQM-Computing/postgis-cookbook) and [pgrouting-cookbook](https://github.com/ZQM-Computing/pgrouting-cookbook) | Load approved normalized layers into a disposable PostGIS schema; test topology and routing only when source semantics support it. | Synthetic GeoJSON-to-PostGIS handoff is implemented in `scripts/run_postgis_handoff.py` with a disposable PostGIS 16 CI service, schema-isolation guard, SRID/extent/count assertions, cleanup, and a short-retention report artifact. This is an Observatory-owned adapter, not a runtime dependency on PostGIS cookbook SQL. No production database or routing workflow exists. Do not infer safe/public routes from line geometry alone. |
| Raster and imagery | [rasterio-cookbook](https://github.com/ZQM-Computing/rasterio-cookbook), [cog-cookbook](https://github.com/ZQM-Computing/cog-cookbook), and [stac-cookbook](https://github.com/ZQM-Computing/stac-cookbook) | Read/write and window-process local rasters, validate COG layout, then catalog approved imagery with STAC metadata and provenance. | Rasterio has executable read/write and windowed-read examples with CI; COG validation and STAC local-asset examples are also implemented. These are repository-local tests, not an Observatory raster or imagery catalog pipeline. |
| API and map delivery | [geospatial-api-reference](https://github.com/ZQM-Computing/geospatial-api-reference), [geoserver-cookbook](https://github.com/ZQM-Computing/geoserver-cookbook), [martin-cookbook](https://github.com/ZQM-Computing/martin-cookbook), and [maplibre-cookbook](https://github.com/ZQM-Computing/maplibre-cookbook) | Publish approved layers through OGC services or serve PostGIS vector tiles, then render a browser map. | GeoServer has a disposable PostGIS→REST publication→WFS integration test; Martin has a PostGIS table-source smoke test covering catalog, TileJSON, and a tile. These are cookbook-level evidence only; no live Observatory API, server, or frontend connection is established. |
| STAC database layer | [pgstac-cookbook](https://github.com/ZQM-Computing/pgstac-cookbook) | Validate a disposable pgSTAC schema/migration before considering catalog persistence. | Reproducible pgSTAC 0.10.0 migration and schema assertions pass against disposable PostGIS in CI. pgSTAC is a database schema/function layer, not an HTTP STAC API; no Observatory catalog exists. |
| Spatial aggregation | [h3-cookbook](https://github.com/ZQM-Computing/h3-cookbook) | Produce coarse, documented aggregates where aggregation is analytically appropriate and privacy-reviewed. | Candidate analytical technique, not a privacy guarantee by itself. |

The umbrella [Geospatial Cookbooks index](https://github.com/ZQM-Computing/geospatial-cookbooks) is the catalog for these independently maintained examples. A link between repositories is documentation discoverability, not a runtime dependency.

## Minimal integration contract for future handoffs

Use one tiny deterministic synthetic dataset (for example, a few points and lines in a declared CRS) and require each stage to produce:

- `manifest.json`: fixture ID, schema version, input hash, CRS, producer repository/commit, tool versions, command, and output paths/hashes;
- a machine-readable QA report with geometry type/validity, feature count, required-field/null checks, CRS, and explicit warnings;
- a nonzero exit on invalid input, mismatched CRS assumptions, missing required metadata, or changed source files;
- no network access and no source records from Volusia while rights remain unresolved.

A cross-repository smoke test should only be called **verified** after CI checks out pinned commits (or versioned releases), runs the actual documented commands, compares expected outputs, and uploads the reports as artifacts. Do not make a floating main branch or a green repository-local badge stand in for compatibility evidence.

## First executable handoff: pinned QGIS dataset QA

The initial offline adapter is implemented in `scripts/run_qgis_dataset_qa_handoff.py`; its contract tests are in `tests/test_qgis_dataset_qa_handoff.py`, and CI is defined in `.github/workflows/external-geospatial-qa.yml`.

The workflow checks out `ZQM-Computing/qgis-resources` at the explicit merged commit `40bf07d435281e46099eb028b1b1a9258cba87ef` (the merge commit for QGIS Resources PR #22), installs the GDAL command-line and Python bindings, and runs the upstream `scripts/dataset_qa.py` twice against the Observatory's synthetic GeoJSON fixture. It requires the declared `id` and `name` fields, candidate identifier uniqueness, EPSG:4326, zero warnings, zero errors, matching feature count, byte-identical QA reports, and an unchanged input hash. The workflow uploads both reports and a handoff manifest as a short-retention CI artifact.

The manifest captures the pinned producer commit, Python/GDAL versions, invocation contract, fixture hashes, and QA-report hash. It explicitly records that source-rights, privacy, and human release review are not approved. A successful technical QA handoff is not release authorization.

Run locally in an environment with GDAL Python bindings:

```sh
python -m unittest discover -s tests -p 'test_qgis_dataset_qa_handoff.py' -v
/usr/bin/python3 scripts/run_qgis_dataset_qa_handoff.py \
  --qa-script support/qgis-resources/scripts/dataset_qa.py \
  --fixture tests/fixtures/synthetic-places.geojson \
  --output-dir build/qgis-dataset-qa-handoff \
  --producer-commit 40bf07d435281e46099eb028b1b1a9258cba87ef
```

The prior pin passed exact-head CI, and the refreshed QGIS Resources pin is required to pass the same upstream runtime contract in this change. The producer commit remains explicit: any future pin update must review the upstream interface and rerun contract tests plus the pinned runtime job.

## Second executable handoff: GeoParquet and DuckDB Spatial

The adapter is `scripts/run_geoparquet_duckdb_handoff.py`, with contract tests in `tests/test_geoparquet_duckdb_handoff.py` and CI in `.github/workflows/geoparquet-duckdb-handoff.yml`. It follows the GeoParquet cookbook's documented GeoPandas write/read and metadata-inspection pattern, and the DuckDB Spatial cookbook's file-based GeoParquet query and expected-value assertion pattern. These are cookbook patterns, not imported APIs; the Observatory adapter owns the contract.

The workflow checks out `ZQM-Computing/geoparquet-cookbook` at `4433a6e561659e880d9e59529159ac4fe1d9c6fe` and `ZQM-Computing/duckdb-spatial-cookbook` at `a38e038d2d02eb83b4b94690af7f9d4c885902ea`. It installs pinned Python packages, provisions DuckDB Spatial, converts only `tests/fixtures/synthetic-places.geojson`, validates GeoParquet's primary geometry, WKB encoding, Point type, CRS metadata, row count and geometry validity, then compares DuckDB aggregates against fixed expected values. It checks stable IDs, nulls, geometry types, extent, category counts, and input immutability. CI uploads the Parquet output, aggregate QA report, and handoff manifest as a 14-day artifact.

The runtime's data-processing phase reads local files only. CI setup does download packages and provisions DuckDB Spatial, so this workflow is not described as a fully network-isolated build. The manifest explicitly marks rights, privacy, and human release review as not approved. It does not authorize publication of real-world records.

Run contract tests with:

```sh
python -m unittest discover -s tests -p 'test_geoparquet_duckdb_handoff.py' -v
```

Run the full adapter in an environment with GeoPandas, PyArrow, PyProj, and DuckDB Spatial already installed:

```sh
python scripts/run_geoparquet_duckdb_handoff.py \\
  --fixture tests/fixtures/synthetic-places.geojson \\
  --output-dir build/geoparquet-duckdb-handoff \\
  --geoparquet-commit 4433a6e561659e880d9e59529159ac4fe1d9c6fe \\
  --duckdb-commit a38e038d2d02eb83b4b94690af7f9d4c885902ea
```


## Third executable handoff: synthetic GeoJSON to PostGIS

The adapter is `scripts/run_postgis_handoff.py`; its contract tests are in `tests/test_postgis_handoff.py` and the disposable integration workflow is `.github/workflows/postgis-handoff.yml`. It first runs the deterministic synthetic-product normalizer, then inserts the three-point fixture into a dedicated `observatory_handoff_ci` schema in a disposable PostGIS 16 service.

The runtime asserts row count, unique stable identifiers, SRID 4326, and a spatial extent matching the normalized source coordinates. It refuses to reuse a pre-existing schema, quotes the schema identifier, parameterizes data values, and removes only the schema created by this run. CI uploads a machine-readable report and manifest for 14 days. The manifest marks publication as unauthorized.

This handoff uses the PostGIS database engine directly; it does not claim to execute or depend on a PostGIS cookbook script. The [PostGIS cookbook](https://github.com/ZQM-Computing/postgis-cookbook) remains the reference for independently tested spatial SQL patterns, including row-level security. The handoff establishes only a synthetic data-loading contract—not production grants, RLS policy design, backup readiness, public API availability, source rights, or release approval.

Run the local contract tests with:

```sh
python -m unittest discover -s tests -p 'test_postgis_handoff.py' -v
```

Run the runtime adapter only against a disposable PostGIS database:

```sh
python -m pip install "psycopg[binary]==3.2.9"
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/observatory \
  python scripts/run_postgis_handoff.py \
  --fixture tests/fixtures/synthetic-places.geojson \
  --output-dir build/postgis-handoff \
  --producer-commit "$(git rev-parse HEAD)"
```

## Implementation order

1. Keep the pinned QGIS QA, GeoParquet/DuckDB, and PostGIS handoffs green on the exact latest commit, including artifact checks and input immutability where applicable.
2. Extend the PostGIS handoff with explicit read-only role/grant and row-level-security tests using synthetic service areas before considering any production database integration.
3. Add a catalog-specific handoff only after deciding whether the first need is a database schema (pgSTAC) or an HTTP API; keep GeoServer/Martin delivery and imagery/STAC as separate optional tracks.
