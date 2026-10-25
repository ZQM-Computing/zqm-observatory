# ZQM Observatory

A self-hosted, open-source observatory that turns public data into mapped,
verifiable intelligence — GEOINT (land, water, infrastructure, imagery,
sensors) and OSINT (entities, domains, records, signals) fused into one picture.

**Volusia County, Florida is the proving ground, not the boundary.** The
pattern is built to travel anywhere public data allows, and the AI tools grown
on it are meant for everyone's use.

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
5. **Aggregates, never individuals.** Games telemetry feeds place intelligence
   only as anonymized, aggregated exports — no individual tracks, no personal
   data, no children's identifiable data, ever.

## What it ships

- Living map layers (OGC + tiles) and a STAC imagery catalog.
- A weekly intel digest (dated report).
- Community briefs — safety, situational, operational, and family-life
  intelligence for communities.
- Family guides — safe, family-friendly places and activities, built from place
  intelligence and games telemetry.
- Telemetry-enhanced place intelligence (aggregated, anonymized only): which
  places people actually use and enjoy, and field-verified place conditions
  from play.
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
- [Data sources](docs/data-sources.md): the public source categories products draw on.
- [Roadmap](docs/roadmap.md): the stages from here to the first data product.
- [Contributing](CONTRIBUTING.md): how to propose a data product.
- [Data](data/README.md): no data products yet, and the license gate for the first one.

## Contact

Questions or corrections: zqmcomputing@gmail.com.

## License

Code in this repository is licensed under the Apache License 2.0 (see LICENSE). Data products published from the Observatory — datasets, maps, and digests — are licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), with attribution to their stated sources. Upstream source licenses still apply to their own data.
