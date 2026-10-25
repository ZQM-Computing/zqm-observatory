# ZQM Observatory

**ZQM Observatory** is an open-source geospatial intelligence (GEOINT) and public-data research project for reproducible mapping, public-source provenance, geospatial data quality assurance (QA), imagery discovery, and community briefs. It is being designed to turn appropriately licensed public information into auditable geographic products—not unsourced claims, personal tracking, or private-data aggregation.

**Volusia County, Florida is the proving ground, not the boundary.** The project remains at **Stage 0 / build-out**: this repository does not claim a live map, feed, dashboard, or published data product. Product concepts below describe intended outputs, not deployed capabilities.

[![License: Apache-2.0](https://img.shields.io/badge/Code%20license-Apache--2.0-blue.svg)](LICENSE) [![Data license: CC BY 4.0](https://img.shields.io/badge/Planned%20data%20license-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/) [![Repository](https://img.shields.io/badge/status-Stage%200%20%7C%20build--out-orange.svg)](docs/roadmap.md)

## Mission and focus

The Observatory is intended to help residents, visitors, families, and practitioners answer practical place-based questions using traceable public evidence:

- **Safety context:** what the available evidence says about places and routes—and what remains unverified.
- **Situational awareness:** dated information about conditions and changes in a defined area.
- **Operational awareness:** the documented state of public services, infrastructure, and systems.
- **Security awareness:** public-source risk context within lawful, passive collection boundaries.
- **Family life:** sourced public places and activities, with access details and conditions clearly distinguished from unverified map attributes.
- **Geospatial engineering:** repeatable source capture, metadata preservation, CRS-aware processing, data-quality checks, and publication gates.

Conservation and environmental conditions are in scope, but they are one use case rather than the entire mission.

## Status: what exists and what does not

**Current state:** repository standards, source-governance documentation, metadata-only preflight tooling, an item-level Volusia source audit, a machine-readable source-rights register, and product-bundle validation standards are being developed in version control.

**Not yet established:** a live public service; a released data product; a production data pipeline; a deployed PostGIS/GeoServer stack; an operational weekly digest; a live STAC catalog; or a verified end-to-end handoff between the geospatial repositories. Repository documentation and green CI checks are not proof of deployment or source permission.

Real-source collection and publication remain gated by the exact source's rights decision, provenance, data QA, privacy review, and product-level human approval. While those permissions are unresolved, use deterministic synthetic fixtures for pipeline development.

## Planned outputs — not live services

- **Dated community briefs** with a defined question, geography, sources, methods, and limitations.
- **Family guides** to sourced public places and activities, without inferring opening hours, safety, accessibility, or public access from geometry alone.
- **Map layers and OGC/tiles delivery** only after data and service deployment are verified.
- **STAC imagery discovery** with item-level metadata, licensing review, and provenance.
- **Dated research digests** with explicit retrieval dates and correction history.
- **Reusable methods and QA reports** so practitioners can reproduce and audit the workflow.

Every future product must distinguish source-recorded facts, calculated values, analyst interpretation, and conditions that require field verification.

## Non-negotiable principles

1. **Public and permitted sources only.** Public accessibility is not a license. Credentialed, paywalled, or private sources are outside scope.
2. **Passive collection against third parties.** Active tests or scans are limited to owned or explicitly authorized systems.
3. **Verify before claim.** Record source identity, retrieval date, version, method, and material limitations for every product.
4. **Free and open-source stack.** No purchases are required as a project principle.
5. **Privacy by design.** Publish only appropriately aggregated or generalized information. Never publish individual tracks, personal data, or identifiable children's data.
6. **No game-telemetry crossover.** ZQM Labs game telemetry and individual movement data are not Observatory inputs, evidence, or join keys.
7. **No silent corrections.** Material corrections to a published product must be dated and explained.
8. **Fail closed.** Unknown source rights, missing provenance, unresolved privacy risks, or incomplete review block publication.

## Developer quickstart

The core structural checks use the Python standard library. From a local clone, run:

```bash
python -m unittest discover -s tests -v
python scripts/validate_source_rights.py
python scripts/validate_products.py
```

Run the metadata-only ArcGIS preflight only when a fresh metadata snapshot is needed:

```bash
python scripts/audit_source_metadata.py --output build/source-metadata-preflight.json
```

The preflight is deliberately bounded to eligible ArcGIS layer metadata on the documented host. It does not request feature records, authorize collection, establish a license, or approve publication. Review its output before committing any report. See [metadata-only source preflight](docs/metadata-only-source-preflight.md) for the exact network boundaries.

A passing validator proves only the structural rules it checks. It cannot prove that source terms have been interpreted correctly, claims are true, field verification happened, privacy review is sufficient, or a service is deployed.

## First-product release workflow

Do not begin with bulk collection. Begin with a decision-relevant question and the smallest suitable product.

1. **Define the question and scope.** Choose geography, audience, publication date, shelf life, owner, and reviewer.
2. **Review every source item.** Preserve the authoritative terms and evidence; record permission separately for capture, transformation, joins, display, and redistribution.
3. **Keep unknown rights blocked.** A public URL, blank copyright field, or “as is” disclaimer is not a redistribution grant.
4. **Develop on synthetic data** until the intended real-source operations are explicitly permitted.
5. **Validate data and provenance.** Check schema, nulls, identifiers, geometry, CRS, units, temporal coverage, joins, and transformation lineage.
6. **Review privacy and field conditions.** Aggregation alone is not a privacy guarantee. State where on-the-ground verification has not occurred.
7. **Validate the product bundle** and obtain an independent human review at the exact proposed commit.
8. **Publish only with approval.** Keep a dated correction path and an appropriate review/expiry trigger.

Use the [first-product release gate](docs/first-product-release-gate.md) as the execution checklist and the [data product standard](docs/product-standard.md) for bundle structure. No single script or CI badge can approve a product.

## Repository guide

- [Scope](docs/scope.md) — mission, intended users, and explicit boundaries.
- [Methods](docs/methods.md) — evidence, repeatability, field verification, privacy, and corrections.
- [Data sources](docs/data-sources.md) — candidate source categories and the current Volusia research.
- [Source rights review](docs/source-rights-review.md) — item-level rights-evidence workflow.
- [Machine-readable source rights register](docs/source-rights-register.md) — conservative decisions and validation rules.
- [Metadata-only source preflight](docs/metadata-only-source-preflight.md) — bounded ArcGIS metadata inspection; no feature collection.
- [Item-level Volusia source audit](docs/item-level-source-audit.md) — layer semantics, staleness, rights gaps, and exclusions.
- [Data product standard](docs/product-standard.md) — machine-checkable product-bundle contract.
- [First-product release gate](docs/first-product-release-gate.md) — end-to-end review checklist.
- [Geospatial repository integration map](docs/geospatial-repository-integration.md) — proposed handoffs and the evidence needed before calling them integrated.
- [Roadmap](docs/roadmap.md) — stage gates; stages are completed by evidence, not by calendar promise.
- [Data directory](data/README.md) — confirms that no verified product has been published yet.
- [Contributing](CONTRIBUTING.md) — product proposal and review requirements.

## ZQM Computing geospatial ecosystem

The Observatory is intended to reuse proven methods from the independently maintained [ZQM Computing geospatial cookbooks](https://github.com/ZQM-Computing/geospatial-cookbooks), including [GDAL](https://github.com/ZQM-Computing/gdal-cookbook), [GeoPandas](https://github.com/ZQM-Computing/geopandas-cookbook), [GeoParquet](https://github.com/ZQM-Computing/geoparquet-cookbook), [DuckDB Spatial](https://github.com/ZQM-Computing/duckdb-spatial-cookbook), [PostGIS](https://github.com/ZQM-Computing/postgis-cookbook), [QGIS resources](https://github.com/ZQM-Computing/qgis-resources), [COG](https://github.com/ZQM-Computing/cog-cookbook), [STAC](https://github.com/ZQM-Computing/stac-cookbook), [H3](https://github.com/ZQM-Computing/h3-cookbook), [pgRouting](https://github.com/ZQM-Computing/pgrouting-cookbook), and the [geospatial API reference](https://github.com/ZQM-Computing/geospatial-api-reference).

These are candidate method and tooling handoffs—not a claim of shared runtime dependencies or a verified integrated pipeline. The [integration map](docs/geospatial-repository-integration.md) identifies what must be built and tested before any handoff is described as operational.

## Licensing

- **Code:** Apache License 2.0; see [LICENSE](LICENSE).
- **Future Observatory data products:** intended to use CC BY 4.0 with attribution, but only where the upstream source terms permit that output license and distribution. The product's source-specific terms remain controlling; the planned output license does not override them.
- **Upstream data:** retains its own license and terms.

The data-product license file and first product should arrive together, after the source-rights and release gates are satisfied.

## Contact

Questions or corrections: <zqmcomputing@gmail.com>.
