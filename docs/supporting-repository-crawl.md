# Supporting-repository crawl — 2026-10-25

## Scope and evidence standard

This crawl inspected the Observatory's integration map and source-governance documents, repository metadata, selected README files, and relevant implementation contracts in the ZQM Computing geospatial portfolio. It is a repository-level desk review, not an execution of a cross-repository pipeline. No source data were downloaded as part of this crawl, and no runtime integration is claimed.

A repository being active, having passing local CI, or documenting a pattern does not prove compatibility with Observatory. A handoff becomes **verified** only after a pinned commit is checked out and its actual interface is executed against a deterministic fixture in CI.

## Findings that change implementation priorities

1. **The strongest immediately reusable QA boundary is `qgis-resources/scripts/dataset_qa.py`.** Its documentation describes a read-only GDAL/OGR inventory tool that emits JSON and optional Markdown, accepts explicit inputs and expected-CRS/required-field/ID-field checks, and fails on an empty scan. This is a concrete candidate contract—not yet an Observatory dependency. Runtime requires GDAL Python bindings, so the integration runner must use a compatible GDAL/QGIS environment.
2. **GDAL and GeoPandas cookbooks are executable examples, not importable shared libraries.** Their READMEs document self-contained synthetic-data examples. Do not write imports or CLI invocations against an assumed API; pin a commit and call a specific documented example only after confirming its input/output contract.
3. **GeoParquet + DuckDB is the lowest-friction next cross-repo data handoff.** The repositories document file-oriented synthetic examples and DuckDB's GeoParquet/GeoJSON analysis. Define a small file contract first: CRS, geometry column/type, schema version, stable fixture IDs, and output hashes.
4. **PostGIS and the OGC API reference are later-stage integration candidates.** They have database and API integration workflows/tests, but those are repository-local demonstrations. No Observatory database, API endpoint, shared schema, or network route was verified by this crawl.
5. **COG/STAC and MapLibre should remain optional branches**, not prerequisites for the initial vector inventory. They introduce raster asset and presentation concerns that do not need to block source rights review, metadata QA, and deterministic vector transformations.
6. **Source rights remain a hard gate.** The Observatory's item-level source audit says the county park/trail candidates remain blocked pending item-specific terms review, and the county transit layers described as downloaded in February 2023 are stale for current-service claims. An accessible ArcGIS endpoint is not permission to redistribute its contents.
7. **Repository-status mismatch found outside the integration path:** the repository metadata API reports `ZQM-Computing/zqm-data` as archived, while its README describes it as active. This repository is not the Observatory's public geospatial source registry and should not be treated as a live Observatory feed. Reconcile its README/status if that repository is reopened; do not make it an Observatory dependency.

## Repositories inspected

The SHA values below are the recursive Git tree object IDs observed during this crawl, not release tags or a claim that a particular test passed. They provide a reproducible snapshot of the inspected tree. Default branch was `main` for the listed active repositories.

| Repository | Observed status | Snapshot tree SHA | Relevant evidence reviewed | Observatory handoff assessment |
| --- | --- | --- | --- | --- |
| [qgis-resources](https://github.com/ZQM-Computing/qgis-resources) | Active, public | `004d037da5301264d3f2ac462d835f2d5c75f8cb` | `scripts/dataset_qa.py`, `docs/DATASET_QA.md`, `docs/WORKFLOW_CONTRACTS.md`, QGIS runtime workflow and QA tests | **First candidate.** Wrap the documented read-only QA contract behind an Observatory-owned adapter; do not import the script or assume a shared package. |
| [gdal-cookbook](https://github.com/ZQM-Computing/gdal-cookbook) | Active, public | `1c7959ced0ec18f18359f572d0de654a0462f1bd` (README blob) | README quickstart and documented GDAL command-line examples | **Candidate conversion stage.** Select one documented example and prove preservation of inputs, CRS, command/version capture, and output hashes. |
| [geopandas-cookbook](https://github.com/ZQM-Computing/geopandas-cookbook) | Active, public | `4204bce1db22f2c8506492dc35511a3c29d083d2` (README blob) | README, synthetic examples, declared install and example invocation | **Candidate vector stage.** Reuse a pinned example only after specifying null, duplicate-ID, geometry-validity, and CRS expectations. |
| [geoparquet-cookbook](https://github.com/ZQM-Computing/geoparquet-cookbook) | Active, public | `d9bbe8f217ed7a7a633328ba943f7d9182871baa` (README blob) | README; repository metadata | **Candidate interchange format.** Define and validate schema/CRS metadata before downstream consumption. |
| [duckdb-spatial-cookbook](https://github.com/ZQM-Computing/duckdb-spatial-cookbook) | Active, public | `a38e038d2d02eb83b4b94690af7f9d4c885902ea` | README and `docs/pattern-guide.md` references; repository file tree | **Candidate analytical stage.** Prefer aggregate QA summaries; never send personal or game telemetry into this workflow. |
| [postgis-cookbook](https://github.com/ZQM-Computing/postgis-cookbook) | Active, public | `ed303089039f1cb000a588f43069357d3c994cd4` | README, `scripts/run_examples.sh`, `docs/production-runbook.md`, SQL assertions, validation workflows | **Later-stage persistence.** Use disposable schemas and synthetic fixtures; no Observatory database integration verified. |
| [stac-cookbook](https://github.com/ZQM-Computing/stac-cookbook) | Active, public | `014c775f7131eabb27caf2f47d37da997d9dc921` | README and tests/workflow tree | **Optional imagery discovery.** Catalog metadata only after item rights, asset URLs, checksums, and retrieval terms are recorded. |
| [cog-cookbook](https://github.com/ZQM-Computing/cog-cookbook) | Active, public | `73259c1060568feca190ff094852715b50e0a4e3` | README and tests/workflow tree | **Optional raster branch.** Validate COG structure and raster semantics independently from source authorization. |
| [geospatial-api-reference](https://github.com/ZQM-Computing/geospatial-api-reference) | Active, public | `2051fe8ed5d15739b5e4bf4512defc8d7018a40a` | README, API tests, PostGIS integration tests/workflow, OGC notes | **Later-stage serving adapter.** Reference implementation is not an Observatory endpoint or proof of full OGC conformance. |
| [geospatial-cookbooks](https://github.com/ZQM-Computing/geospatial-cookbooks) | Active, public | `d15f1f3e7aa5f1a902bed70b190687614443a2b0` | README, repository manifest, index/documentation tests | **Discovery index only.** Its manifest is a useful repository catalog, not an integration registry for Observatory runtime dependencies. |
| [zqm-supply-chain](https://github.com/ZQM-Computing/zqm-supply-chain) | Active, private | `fe51d82d38869f22506d7af0e26f798578a09fa7` | README and script/workflow tree | **Security tooling candidate, not a geospatial stage.** It is a CLI script, not a GitHub Action; pin and invoke explicitly if adopted. No Observatory invocation verified. |
| [zqm-data](https://github.com/ZQM-Computing/zqm-data) | Archived per repository metadata | Not captured in this crawl | README role/status text compared with repository metadata | **Not an Observatory source.** Status text conflicts with repository metadata; do not rely on it as an active service or feed. |
| [pgrouting-cookbook](https://github.com/ZQM-Computing/pgrouting-cookbook) | Active, public | Not captured in this crawl | Repository metadata and current integration-map entry | **Deferred.** Route geometry alone cannot establish safety, accessibility, public access, or service availability. |
| [h3-cookbook](https://github.com/ZQM-Computing/h3-cookbook) | Active, public | Not captured in this crawl | Repository metadata and current integration-map entry | **Optional aggregation technique.** H3 aggregation is not a privacy guarantee; conduct a separate disclosure-risk review. |
| [maplibre-cookbook](https://github.com/ZQM-Computing/maplibre-cookbook) | Active, public | Not captured in this crawl | Repository metadata and current integration-map entry | **Presentation layer only.** Do not begin frontend integration before a rights-cleared, validated product contract exists. |
| [zqm-observatory](https://github.com/ZQM-Computing/zqm-observatory) | Active, public; Stage 0/build-out | Current source files reviewed from `main`; this report is not a release artifact | README, source governance, source audit, release gate, attestation and provenance tooling | **Owns source governance and release gates.** Keep it independent of cookbook internals; adapters and pinned smoke tests belong in the Observatory. |

## Recommended next implementation

Build one **Observatory-owned, offline integration harness** with a tiny synthetic GeoPackage/GeoJSON fixture. Its first adapter should invoke the documented `qgis-resources/scripts/dataset_qa.py` command in a pinned checkout/runtime, then normalize the resulting report into the Observatory's own manifest. Test at least:

- input and output SHA-256 values and no input mutation;
- explicit CRS and feature/schema expectations;
- nonzero failure on missing/unsupported/empty inputs and CRS mismatch;
- report determinism (excluding explicitly declared volatile fields);
- provenance fields for producer repository, exact commit, command, and tool versions;
- no network access and no real public-source records;
- rights gate remains blocked even when technical QA succeeds.

Only after that stage passes should the same fixture be written to GeoParquet and checked with DuckDB. PostGIS/API, STAC/COG, routing, and MapLibre remain separate increments with their own tests. This sequence provides evidence of real compatibility without falsely claiming the repositories are already wired together.
