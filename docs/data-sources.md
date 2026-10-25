# Data sources

## Read this first

This page lists source categories the Observatory draws on. It is not a
claim that any dataset has been ingested, processed, or published. No data
product exists yet. A source listed here is a source a future product may
use, under the standard in [methods](methods.md): named, dated, public, and
attributed.

When a product does use a source, the product itself names the exact
dataset, the retrieval date, and the method. This page never substitutes
for that.

## National public sources

### U.S. Geological Survey

Topography, surface-water observations, land cover, and imagery programs.
Useful for the shape of the land, what sits on it, and what has been
observed there over time. Most USGS data is U.S. Government public domain;
a product still attributes the dataset it used.

### National Oceanic and Atmospheric Administration

Weather and climate observations, coastal data, and related environmental
records. Useful for conditions over time and for the state of the coast and
atmosphere around a place. Products attribute the NOAA dataset used.

### U.S. Census Bureau

Demographics, housing, and boundary data, including the TIGER/Line
geographic datasets. Useful for who lives where, in aggregate, and for the
boundaries communities actually sit inside. Census reporting here is always
aggregated; no individual records are used or published.

### National Aeronautics and Space Administration

Earth-observation imagery and science data, including the Landsat program
operated with the USGS. Useful for land change and imagery over time, at a
scale where individual people are not identifiable.

## Community-mapped sources

### OpenStreetMap

Community-mapped roads, paths, facilities, parks, and points of interest.
Useful for the fine grain of a place: which paths exist, where facilities
sit, and how a neighborhood connects. OpenStreetMap data is published under
the Open Database License; a product that uses it attributes OpenStreetMap
and its contributors and respects that license.

## State and local open data

State agencies, counties, and cities publish open data portals covering
parks, facilities, services, and public infrastructure. For the proving
ground, Volusia County and Florida state open data are the first local
sources a product checks, after the national sources above. A local source
is used only when it is genuinely public, documented, and attributable.

## Researched candidates for the first product

**Research reviewed: 2026-10-25.** These are source candidates, not ingested
datasets. No product has been created, no files have been downloaded into
this repository, and source licenses have not all been cleared for
redistribution. Record the actual retrieval timestamp, item metadata, terms,
and file checksum in a product's own `sources.json` when collection begins.

### Proposed first question

Start with a bounded public-recreation inventory for one community in
Volusia County: **which parks, mapped trails, and transit stops are listed
in official public sources, and which access details still need field
verification?** Publish only sourced locations and explicit limitations.
Do not claim a place is open, accessible, safe, family-friendly, or served at
a particular time solely because it appears in a map layer. Verify hours,
public access, entrances, route continuity, and relevant amenities before
making those claims. Keep this separate from games telemetry and individual
movement data.

### Candidate source register

| Source and exact dataset/layer | Proposed use | Review status and limitations |
| --- | --- | --- |
| [Volusia County Open Data portal](https://opendata-volusiacountyfl.hub.arcgis.com/) and [Open_Data/Open_Data_4 MapServer](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/MapServer): Park Locations (layer 4), Park Boundaries (layer 2), Trails (layer 32), VOTRAN Bus Stops (layer 33), VOTRAN Bus Routes (layer 37). | Primary candidate for a county-maintained inventory of mapped recreation features and transit locations. | The service lists these layers and reports spatial reference WKID 2881 with feet as units. For a community boundary, the county also exposes [Cities Dissolved Weekly (layer 27)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_1/MapServer/27), described as municipal polygon boundaries; filter the documented city-name field for the chosen municipality and verify the boundary vintage. Preserve the original source CRS and reproject deliberately before distance/area analysis. The service copyright field is blank; this does **not** establish a redistribution license. Inspect each portal item's terms, metadata, steward, update date, geometry, and attribute definitions before use. |
| [Florida Natural Areas Inventory GIS data](https://www.fnai.org/publications/gis-data): Florida Conservation Lands (FLMA), feature-class ZIP, updated September 2026. | Optional cross-check for managed conservation areas, not a substitute for a public-park inventory. | FNAI requests citation. Its records include public and private managed lands; FNAI explicitly warns that not all conservation lands are open to the public. Never infer public access from a polygon or conservation designation. Use only if the product needs this distinct context and terms are checked. |
| [2025 Census TIGER/Line files](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2025.html). | Optional geographic context for a later tract-level aggregate, if a defined question genuinely needs population context. | Boundary vintage is 2025; the Census page states legal boundaries and names are as of January 1, 2025. TIGER/Line geometry does not itself contain demographic estimates. Record the exact geography layer and vintage. |
| [2024 American Community Survey 5-Year data](https://www.census.gov/data/developers/data-sets/acs-5year/2024.html). | Optional aggregate population/housing context joined to matching census geography; not required for the initial inventory. | Use estimates at a stated geography and vintage, include relevant uncertainty/margins of error, and do not treat estimates as exact counts. Avoid demographic joins unless they answer the stated question. |
| [Florida Geospatial Open Data Portal](https://geodata.floridagio.gov/) and [Florida Geographic Data Library](https://fgdl.org/explore-data/). | Secondary discovery catalogs when a needed official state layer is missing from the county portal. | Both expose multiple data formats and sources, but each dataset's steward, vintage, license, and redistribution terms must be reviewed individually. A portal being open does not automatically clear every hosted dataset for redistribution. |

### Collection and acceptance gates

Before treating any candidate as a product source:

1. Open the exact catalog item, not just its map service; save the title,
   publisher/steward, stable item ID, metadata URL, license/terms, update
   date, field definitions, geometry type, and retrieval timestamp.
2. Download or query a reproducible snapshot where terms permit it. Record
   the request/query, source URL, date, file format, feature count, CRS,
   and SHA-256 checksum. Do not rely on a live layer remaining unchanged.
3. Check for duplicate features, null or malformed coordinates, invalid
   geometries, stale or conflicting names, missing access attributes, and
   inconsistent park/trail identifiers. Preserve source identifiers and
   document every filter and transformation.
4. Reproject from the source's stated CRS before calculating distances or
   areas; document the target CRS, units, and method. Do not interpret
   straight-line proximity as a walkable route.
5. Verify public access, entrances, hours, route continuity, and any amenity
   claim on official pages and in the field where relevant. Record each
   check's date and status; label unresolved attributes as unknown.
6. Confirm redistribution rights and attribution for every input and output.
   If county terms cannot be established, do not redistribute its data files
   or publish a derivative until the rights question is resolved.

The first product should remain an inventory, not a ranking or accessibility
score, unless the sources and method can substantiate that stronger claim.

## What is never a source

- Credentialed, paywalled, or private data of any kind.
- Individual-level records, personal data, or children's identifiable data.
- Data whose license forbids the Observatory's use, or whose provenance
  cannot be stated.

## How a source becomes a product

A source graduates from this list to a product only through the
verification standard in [methods](methods.md) and the proposal process in
[Contributing](../CONTRIBUTING.md): a named dataset, a retrieval date, a
repeatable method, field verification where place conditions matter, and
aggregates-only reporting. Until then, it stays on this list and nowhere
else.

## Related documents

- [Methods](methods.md): the verification standard every product must pass.
- [Roadmap](roadmap.md): the stages from here to the first data product.
