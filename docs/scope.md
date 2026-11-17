# Scope

## What the Observatory is

The ZQM Observatory is a self-hosted, open-source observatory that turns
public data into mapped, verifiable intelligence: GEOINT (land, water,
infrastructure, imagery, sensors), OSINT (entities, domains, records), and
SIGINT (publicly observable signals) fused into one picture.

Its products are written for ordinary people making ordinary decisions:
where is safe, what is happening nearby, which services and systems can be
relied on today, and which places are worth a family's time.

## Proving ground, not boundary

Volusia County, Florida is the proving ground, not the boundary. The first
products are built there because the ground is known and the sources can be
checked on foot. The pattern is built to travel anywhere public data allows,
and the AI tools grown on it are meant for everyone's use.

A product that only works in one county is a prototype. A product earns the
Observatory name when its method is written down well enough that someone
elsewhere can repeat it with their own county's public data.

## Focus

Not only environmental conservation. Conservation is one line among them.
The Observatory is focused on:

- Safety: safe places and routes, and the conditions that make them safe.
- Situational awareness: what is happening around you right now.
- Operational awareness: the state of the systems, services, and activities
  you depend on.
- Security awareness: threats and risks, as one of the three awarenesses,
  not the whole.
- Family values: family-friendly places and activities, and products a
  family can use and trust.

## Geospatial intelligence (GEOINT)

GEOINT is the mapped picture of a place: land, water, infrastructure,
imagery, and sensors, drawn from public data. Topography, surface water,
land cover, weather and coastal observations, boundaries and demographics
in aggregate, Earth-observation imagery, and community-mapped roads, paths,
and facilities — joined into one map a reader can check against the
sources it names.

A map layer is a record, not a verdict. GEOINT here does not claim a place
is open, accessible, safe, or served at a particular time solely because
it appears in a layer. Place conditions that matter — access, entrances,
hours, route continuity, amenities — are field-verified before they are
published as fact, or the gap is stated plainly. Measurements respect the
source: the original coordinate system is preserved and any reprojection
is documented, and a straight-line distance is never presented as a
walkable route.

GEOINT is reported as aggregates, under the same rule as everything else
in this repository: no individual tracks, no personal data, and no
children's identifiable data, ever.

## Open-source intelligence (OSINT)

OSINT is the recorded picture of who and what: entities, domains, and
public records — what an organization is, what a record says, what a
registration or filing shows — established from sources anyone can name,
link, and re-check.

Every claim traces to a named public source with a retrieval date. A
source that cannot be named and linked cannot be used. Public and open
sources only: no credentialed, paywalled, or private data of any kind, and
no individual-level records. Where a record is stale, conflicting, or
incomplete, the product says so instead of smoothing it over.

OSINT is reported as aggregates, under the same rule as everything else
in this repository: no individual tracks, no personal data, and no
children's identifiable data, ever.

## Signals intelligence (SIGINT)

SIGINT is the systematic observation of publicly visible activity and
change: procurement feeds, hiring posts, press releases, public posts,
public page changes, and public-record updates, read as signals about what
is happening and what is about to happen. Where GEOINT maps what is there
and OSINT establishes who and what is recorded, SIGINT watches what moves.

The boundary is hard and public-only. SIGINT here means signals anyone can
observe without a login, a credential, or a private account: no
interception of private communications, no private accounts, no
behind-login access. A fact that can only be reached behind a login is
marked unresolved, not chased. Aggregators and search-index mirrors are
corroboration only, never the basis for a claim on their own.

Signals are about institutions, projects, and places, not people. SIGINT
is reported as aggregates, under the same rule as everything else in this
repository: no individual tracks, no personal data, and no children's
identifiable data, ever.

## What it is not

The Observatory is not a live service yet. Nothing in this repository is a
running map, feed, or dashboard today. Stage 1 is documentation and
standards: the scope, methods, and source categories a product must satisfy
before it lands here. The first data product, when it arrives, will be dated,
sourced, and verified under the standard in [methods](methods.md), and it
will be the moment the repository stops being only a plan.

## Who it serves

- Residents and visitors who want a clear, sourced picture of a place.
- Families choosing where to go and what to trust.
- Practitioners who want to reuse the methods, code, and pipelines rather
  than take a finished claim on faith.

## Related documents

- [Methods](methods.md): how a product is built and verified.
- [Data sources](data-sources.md): the public source categories products
  draw on.
- [Roadmap](roadmap.md): the stages from here to the first data product.
- [Contributing](../CONTRIBUTING.md): how to propose a product.
- [Data](../data/README.md): what belongs in the data directory, and when.
