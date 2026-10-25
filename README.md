# ZQM Observatory

**ZQM Observatory** is an open-source **geospatial intelligence (GEOINT) and public-data research** project for reproducible mapping, source provenance, geospatial data quality assurance (QA), imagery discovery, and community briefs. It is being built to turn appropriately licensed public information into auditable geographic products—not unsourced claims or private-data aggregation.

**Volusia County, Florida is the proving ground, not the boundary.** The Observatory remains at **Stage 0 / build-out**. This repository does not claim a live map, feed, dashboard, or published data product. The outputs described below are planned capabilities, not deployed services.

## Mission and focus

The Observatory is intended to help residents, visitors, families, and practitioners answer practical place-based questions using traceable public evidence:

- **Safety context:** what available evidence says about places and routes—and what remains unverified.
- **Situational awareness:** dated information about conditions and changes in a defined area.
- **Operational awareness:** the documented state of public services, infrastructure, and systems.
- **Security awareness:** public-source risk context within lawful, passive collection boundaries.
- **Family life:** sourced public places and activities, with access details and conditions clearly distinguished from unverified map attributes.
- **Geospatial engineering:** repeatable source capture, metadata preservation, CRS-aware processing, QA, and publication gates.

Conservation and environmental conditions are in scope, but they are one use case rather than the entire mission.

## Status: what exists and what does not

**In version control today:** repository standards, source-governance documentation, metadata-only source preflight tooling, an item-level Volusia source audit, a machine-readable source-rights register, and data-product bundle validation standards.

**Not yet established:** a live public service; a released data product; a production data pipeline; a deployed PostGIS/GeoServer stack; an operational weekly digest; a live STAC catalog; or a verified end-to-end handoff between the geospatial repositories. Documentation and green CI checks are not proof of deployment, factual accuracy, or source permission.

Real-source collection and publication remain gated by the exact source's rights decision, provenance, data QA, privacy review, and product-level human approval. While source permissions are unresolved, use deterministic synthetic fixtures for pipeline development.

## Planned outputs — not live services

- **Dated community briefs** with a defined question, geography, sources, methods, and limitations.
- **Family guides** to sourced public places and activities, without inferring opening hours, safety, accessibility, or public access from geometry alone.
- **Map layers and OGC/tiles delivery** only after data and service deployment are verified.
- **STAC imagery discovery** with item-level metadata, licensing review, and provenance.
- **Dated research digests** with explicit retrieval dates and correction history.
- **Reusable methods and QA reports** so practitioners can reproduce and audit the workflow.

Every future product must distinguish source-recorded facts, calculated values, analyst interpretation, and conditions that require field verification.

## Principles

1. **Public and permitted sources only.** Public accessibility is not a license. Credentialed, paywalled, or private sources are outside scope.
2. **Passive collection against third parties.** Active tests or scans are limited to owned or explicitly authorized systems.
3. **Verify before claim.** Record source identity, retrieval date, version, method, and material limitations for every product.
4. **Free and open-source stack.** No purchases are required as a project principle.
5. **Privacy by design.** Publish only appropriately aggregated or generalized information. Never publish individual tracks, personal data, or identifiable children's data.
6. **No silent corrections.** Material corrections to a published product must be dated and explained.
7. **Fail closed.** Unknown source rights, missing provenance, unresolved privacy risks, or incomplete review block publication.

## Quick start: validate the repository

The governance checks run locally without connecting to a data source or collecting source records. Requires Python 3.

```sh
python -m unittest discover -s tests -v
python scripts/validate_source_rights.py
python scripts/validate_products.py
```

A clean validation run confirms structural checks only. It does **not** clear source licenses, establish factual accuracy, prove privacy safety, or authorize publication. Unknown source permissions remain blocked.

Run the metadata-only ArcGIS preflight only when a fresh metadata snapshot is useful:

```sh
python scripts/audit_source_metadata.py --output build/source-metadata-preflight.json
```

This preflight is deliberately bounded to eligible layer metadata. It does not request feature records, authorize collection, establish a license, or approve publication. Review its output before committing a report; the exact network boundaries are documented in [metadata-only source preflight](docs/metadata-only-source-preflight.md).

## Reproducible synthetic pipeline

A first offline end-to-end pipeline is available for engineering and CI validation. It uses an invented GeoJSON fixture only; it does not fetch real sources or authorize publication. Run it with:

```sh
python scripts/build_synthetic_product.py --output-dir build/synthetic-product --bundle-dir build/synthetic-product-bundle
```

It produces deterministic normalized GeoJSON, a QA report, and SHA-256 provenance under `build/synthetic-product/`, then packages a standards-shaped draft under `build/synthetic-product-bundle/`. The draft intentionally fails the publication gate until a human privacy review is recorded; it is not a publishable product. Run `python scripts/verify_synthetic_provenance.py --input tests/fixtures/synthetic-places.geojson --output-dir build/synthetic-product` to check that the recorded input, pipeline source, normalized output, and QA report hashes still match. Compare normalized runs with `scripts/compare_product_runs.py` to identify added, removed, and changed features by stable ID, including geometry and attribute differences plus extent changes. Invalid input fails closed and emits no normalized product. See [synthetic pipeline quickstart](docs/synthetic-pipeline.md) for the contract and limitations.

## First-product release workflow

Start with a decision-relevant question and the smallest suitable product—not bulk collection.

1. **Define the question and scope:** geography, audience, publication date, shelf life, owner, and reviewer.
2. **Review each source item:** preserve authoritative terms and evidence; record permissions separately for capture, transformation, joins, display, and redistribution.
3. **Keep unknown rights blocked:** a public URL, blank copyright field, or “as is” disclaimer is not a redistribution grant.
4. **Develop on synthetic data** until the intended real-source operations are explicitly permitted.
5. **Validate data and provenance:** schema, nulls, identifiers, geometry, CRS, units, temporal coverage, joins, and transformation lineage.
6. **Review privacy and field conditions:** aggregation alone is not a privacy guarantee. State where on-the-ground verification has not occurred.
7. **Validate the product bundle** and obtain independent human review at the exact proposed commit.
8. **Publish only with approval:** keep a dated correction path and an appropriate review/expiry trigger.

Use the [first-product release gate](docs/first-product-release-gate.md) as the execution checklist and the [data product standard](docs/product-standard.md) for bundle structure. No single script or CI badge can approve a product.

## How questions flow

Every question travels the same cycle: **Direction → Collection → Processing → Analysis → Dissemination → Feedback → Governance.** The software exists to serve the cycle, not the other way around.

## Repository guide

- [Scope](docs/scope.md) — mission, intended users, and explicit boundaries.
- [Methods](docs/methods.md) — evidence, repeatability, field verification, privacy, and corrections.
- [First-product release gate](docs/first-product-release-gate.md) — operational checklist from question selection through independent review and publication decision.
- [Data product standard](docs/product-standard.md) — machine-checkable product-bundle contract.
- [Data sources](docs/data-sources.md) — candidate source categories and the current Volusia research.
- [Source rights review](docs/source-rights-review.md) — item-level rights-evidence workflow.
- [Machine-readable source rights register](docs/source-rights-register.md) — conservative decisions and validation rules.
- [Metadata-only source preflight](docs/metadata-only-source-preflight.md) — bounded ArcGIS metadata inspection; no feature collection.
- [Item-level Volusia source audit](docs/item-level-source-audit.md) — layer semantics, staleness, rights gaps, and exclusions.
- [Geospatial repository integration map](docs/geospatial-repository-integration.md) — proposed handoffs and the evidence needed before calling them integrated.
- [Roadmap](docs/roadmap.md) — stage gates completed by evidence, not calendar promise.
- [Data directory](data/README.md) — confirms no verified product has been published yet.
- [Contributing](CONTRIBUTING.md) — product proposal and review requirements.

## ZQM Computing geospatial ecosystem

The Observatory is intended to reuse methods from the independently maintained [ZQM Computing geospatial cookbooks](https://github.com/ZQM-Computing/geospatial-cookbooks), including [GDAL](https://github.com/ZQM-Computing/gdal-cookbook), [GeoPandas](https://github.com/ZQM-Computing/geopandas-cookbook), [GeoParquet](https://github.com/ZQM-Computing/geoparquet-cookbook), [DuckDB Spatial](https://github.com/ZQM-Computing/duckdb-spatial-cookbook), [PostGIS](https://github.com/ZQM-Computing/postgis-cookbook), [QGIS resources](https://github.com/ZQM-Computing/qgis-resources), [Cloud Optimized GeoTIFF](https://github.com/ZQM-Computing/cog-cookbook), [STAC](https://github.com/ZQM-Computing/stac-cookbook), [H3](https://github.com/ZQM-Computing/h3-cookbook), [pgRouting](https://github.com/ZQM-Computing/pgrouting-cookbook), and the [geospatial API reference](https://github.com/ZQM-Computing/geospatial-api-reference).

These are candidate method and tooling handoffs—not a claim of shared runtime dependencies or a verified integrated pipeline. The [integration map](docs/geospatial-repository-integration.md) identifies what must be built and tested before any handoff is described as operational.

## Contact

Questions or corrections: <zqmcomputing@gmail.com>.

## Licensing

- **Code:** Apache License 2.0; see [LICENSE](LICENSE).
- **Future data products:** intended to use CC BY 4.0 with attribution, but only where upstream source terms permit that output license and distribution.
- **Upstream data:** retains its own license and terms. The Observatory's planned output license does not override source-specific conditions.

The data-product license file and first product should arrive together, after the source-rights and release gates are satisfied.
