# ZQM Observatory — MapExplain

**Ask about places. See the map, sources, and steps.**

**Traceable location analysis.** MapExplain is the question-to-map workspace within **ZQM Observatory**,
from **ZQM Computing**. Ask a supported location question and compare locations,
find illustrative coverage gaps, or inspect ranked results alongside the map,
source notes, calculation steps, and limitations. This is a **synthetic GIS
engineering demonstration**, not a released Observatory data product or a live
service. It belongs to ZQM Computing; it does not integrate ZQM Labs games.

## Product identity

| Level | Name | Purpose |
| --- | --- | --- |
| Publisher | ZQM Computing | Geospatial tools and engineering |
| Platform | ZQM Observatory | Traceable place-based research and analysis |
| Feature | MapExplain | Ask location questions; inspect maps, results, and methods |

Use **ZQM Observatory — MapExplain** for the full product/feature name,
**MapExplain** inside the Observatory interface, and **by ZQM Computing**
when publisher context is needed. Keep the descriptive value statement alongside
first mentions. Demo labeling and evidence limits remain visible separately.

The working name follows a [competitor and naming screen](../../docs/observatory-competitive-landscape.md).
It is a provisional development name, not a statement of trademark, domain, or
social-handle clearance. No separate domain or paid brand service is required.

## Run and verify

Requires Node.js 22.12 or newer and npm. From this directory:

```sh
npm ci --ignore-scripts
npm test
npm run build
npm run dev
```

`npm run preview` serves the built `dist/` output for local review. The relative
asset base also supports reviewing the build under a static subdirectory. No
deployment workflow, credentials, database, paid API, or source collection is
configured by this application.

## What works

- Fixed English question patterns for sample attribute rankings and filters,
  nearest-place distances, point containment, counts by invented neighborhood,
  and illustrative coverage scores.
- Interactive local SVG map, map/list selection, layer toggles, zoom, and a
  fit-all control. The map has no external basemap or tile requests.
- CSV and RFC 7946 Point GeoJSON ingestion, bounded to 2 MB and the first 2,000
  valid points. CSV coordinate columns are assumed to be WGS84 degrees; that
  assumption cannot establish that the source was actually georeferenced correctly.
- Local-only queries, files, and recent question history. Reloading clears them.
- CSV, GeoJSON, and copied summaries with explicit unverified-demo status,
  interpretation, limitations, and no publication authorization.

Examples are built into the interface. Distances from 50 m through 100 km are
accepted. Decimal thresholds retain their values. Attribute comparisons support
strict under/over and inclusive at-most/at-least semantics.

## Evidence boundaries

The Providence neighborhood shapes, demographic values, clinic locations,
customer records, and warehouse are invented. Some place names resemble real
places; none establish actual access, conditions, service availability, or
source permission. See the persistent demo banner and source notes in each answer.

Distances are great-circle point-to-point calculations on a spherical Earth.
Neighborhood access uses a representative centroid, not the nearest boundary.
Drawn buffer rings use a local approximation, and the SVG map is an illustrative
equirectangular view, not a survey or authoritative basemap. It is unsuitable for
global, polar, or antimeridian cartography. Rankings and coverage scores are
demonstrations, not recommendations to open a real facility.

The interpreter declines routed travel time, live conditions, census tracts,
unsupported geography, multi-attribute filters, and distances outside its range.
It never sends an unmatched question to a model. There is no general natural
language reasoning, address geocoding, reprojection, polygon upload analysis,
voice service, cloud persistence, or share-link backend.

Use synthetic or appropriately permitted public, nonpersonal upload records.
Files are never committed or sent to an analysis service by this app. Invalid
uploads clear the previous active upload and derived answer; unsupported geometry
is dropped rather than silently replaced with an invented centroid. Removing a
file clears its answer and restores the default synthetic example.

Browser exports are local drafts. They are **not** Observatory product bundles,
and must not be copied into `data/products/` or treated as approved publications.
The repository's [source-rights](../../docs/source-rights-review.md),
[privacy and methods](../../docs/methods.md), and
[first-product release gates](../../docs/first-product-release-gate.md) still apply.
Export labels are informational and cannot prevent someone from redistributing a
downloaded file; human release review remains necessary.

## Import and maintenance

Adapted from the user-supplied `grok-workspace.zip` on November 16, 2026.
Archive SHA-256:
`5735fb863e27e6df0fa15c9d3e7bf92a5e34a2f23ea2902449728326a887221f`.
The supplied prototype's engine, data, geometry, intent, workspace, and styling were
adapted into a standalone Vite/React application. The source archive's hosting,
authentication, database, AI planner, generated art, personal attachments, and
platform scaffolding are not runtime dependencies of this application.

Code follows the repository's [Apache 2.0 license](../../LICENSE). Dependencies
retain their respective licenses, with exact versions recorded in the lockfile.
No upstream public dataset or data-publication license is asserted by this import.

CI runs the app's regression tests, TypeScript checks, production build, and
dependency audit on trusted same-repository changes. It does not deploy or approve
any data product. The existing Python governance checks remain independent.
See the [verification record](QA.md) for observed browser behavior and remaining
device/CI verification.
