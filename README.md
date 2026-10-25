# ZQM Observatory

ZQM Observatory is an open-source geospatial intelligence and public-data research project for source-attributed maps, geospatial QA, imagery discovery, and community briefs. It combines GEOINT methods for land, water, infrastructure, and imagery with OSINT methods for public records and signals.

**Volusia County, Florida is the proving ground, not the boundary.** Observatory remains at Stage 0: no live service or published data product is claimed until its sources, methods, and outputs are verified.

## Focus

Not only environmental conservation — conservation is one line among them.
The Observatory is focused on:

- **Safety** — safe places and routes, and the conditions that make them safe.
- **Situational awareness** — what is happening around you right now.
- **Operational awareness** — the state of the systems, services, and activities
  you depend on.
- **Security awareness** — threats and risks, as one of the three awarenesses,
  not the whole.
- **Family values** — family-friendly places and activities, and products a
  family can use and trust.

## Principles

1. **Public/open sources only.** No credentialed, paywalled, or private data.
2. **Passive-only against third parties.** Active tools run on owned or
   authorized targets only.
3. **Verify before claim.** Source, retrieval date, and method on every product.
4. **No purchases, ever.** The entire stack is free and open-source.
5. **Privacy and product separation.** Report only sourced public-place facts
   and appropriately aggregated public data. No individual tracks, personal
   data, or identifiable children's data. ZQM Labs game telemetry is outside
   Observatory scope and is not ingested, joined, or used as evidence.

## What it ships

- Living map layers (OGC + tiles) and a STAC imagery catalog.
- A weekly intel digest (dated report).
- Community briefs — safety, situational, operational, and family-life
  intelligence for communities.
- Family guides — sourced public places and activities, with access
  details and conditions clearly distinguished between published claims and
  field-verified observations.
- Reproducible source registers, capture metadata, geospatial QA reports, and
  correction histories that let others audit how a claim was produced.
- Demos, dashboards, and public methods — code, pipelines, and documentation
  other practitioners can reuse.

## Status

**Stage 0 — build-out in progress.** The fleet stack (PostGIS, GeoServer,
orchestration, collection, and intelligence tooling) is being installed node by
node. Nothing here is a live service yet; products land here as they are
verified, dated, and sourced.

## How questions flow

Every question travels the same cycle: Direction → Collection → Processing →
Analysis → Dissemination → Feedback → Governance. The software exists to serve
the cycle, not the other way around.

## What lives here

- [Scope](docs/scope.md): what the Observatory covers, and where it starts.
- [Methods](docs/methods.md): how a product is built and verified.
- [Geospatial repository integration map](docs/geospatial-repository-integration.md): recommended handoffs across ZQM Computing's geospatial tools, with implementation status stated explicitly.
- [Geospatial Cookbooks index](https://github.com/ZQM-Computing/geospatial-cookbooks): the independent cookbook and reference-repository catalog.
- [Data sources](docs/data-sources.md): the public source categories products draw on.
- [Source rights review](docs/source-rights-review.md): the item-level permission and publication gate.
- [Machine-readable source rights register](docs/source-rights-register.md): source-by-source decisions and the fail-closed validator.
- [Metadata-only source preflight](docs/metadata-only-source-preflight.md): bounded, non-feature ArcGIS metadata snapshots with no bulk collection.
- [Item-level Volusia source audit](docs/item-level-source-audit.md): metadata findings and unresolved semantics for each candidate.
- [Roadmap](docs/roadmap.md): the stages from here to the first data product.
- [Contributing](CONTRIBUTING.md): how to propose a data product.
- [Data](data/README.md): no data products yet, and the license gate for the first one.

## Contact

Questions or corrections: <zqmcomputing@gmail.com>.

## License

Code in this repository is licensed under the Apache License 2.0 (see LICENSE). Data products published from the Observatory — datasets, maps, and digests — are licensed under CC BY 4.0 (<https://creativecommons.org/licenses/by/4.0/>), with attribution to their stated sources. Upstream source licenses still apply to their own data.
