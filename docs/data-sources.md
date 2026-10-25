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


### First-pass layer schema review

**Schema inspection reviewed: 2026-10-25.** The county's live ArcGIS service metadata is useful for planning a collection, but it does not resolve dataset licensing or guarantee that the current records are complete. The service-level copyright text is blank; individual layer metadata must be checked for terms before redistribution. The County GIS page describes its data as provided “as is” without an express or implied warranty of accuracy ([Geographic Information Services](https://www.volusia.org/_deleted/information-technology/geographic-information-services/)). An accessible service is not, by itself, a redistribution grant.

The layer metadata currently exposes these fields and limitations:

| Layer | Confirmed schema signals | Collection implications |
| --- | --- | --- |
| [Park Locations (4)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/4) | Point geometry. Fields include `Name`, `Address`, `CityName`, `Type`, `Status`, `Owner`, `MaintAuth`, `URL`, `ParkID`, `Acres`, and amenity flags such as `Restrooms`, `Playground`, `Trails`, `Sidewalk`, and `Parking`. | Treat amenity flags as source assertions, not field-verified current conditions. Preserve `ParkID` where populated; assess duplicates and nulls before joining. Determine the meaning and allowed values of each flag from item metadata or the data steward. |
| [Park Boundaries (2)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/2) | Polygon geometry. Fields include `Name`, `Address`, `CityName`, `Type`, `Owner`, `MaintAuth`, `URL`, `Acres`, `Acreage`, `ParkID`, `created_date`, and `last_edited_date`. | Test geometry validity and compare the two acreage fields against calculated area only after confirming their definitions and units. Join to points only through a verified identifier such as `ParkID`; do not assume names uniquely identify the same park. |
| [Trails (32)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/32) | Polyline geometry. Fields include `Name`, `Name2`, `Name3`, `Type`, `SubType`, `Surface`, `Width_Ft`, `Seg_Miles`, `miles`, `TrailName`, `MaintainedBy`, and `Owner`. | Length fields may have different semantics; compare them with geometry-derived lengths and document discrepancies rather than silently selecting one. A mapped line alone does not prove a continuous, open, or walkable trail. |
| [VOTRAN Bus Stops (33)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/33) | Point geometry. The service description says the layer was downloaded in February 2023 and created with ESRI Streets and the GTFS tool. Fields include `stop_id`, `stop_code`, `stop_name`, `stop_lat`, `stop_lon`, `stop_url`, `location_type`, `parent_station`, and `wheelchair_boarding`. | The stated February 2023 source date is a material staleness risk. Do not present it as current service information. VOTRAN's [official GIS & GTFS files page](https://www.votran.org/documents-data/) lists GTFS data effective October 4, 2026; compare against that current agency-published feed and record its version/date before publishing any stop inventory. Treat the wheelchair field as unverified until definitions and current conditions are checked. |
| [VOTRAN Bus Routes (37)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/37) | Polyline geometry; display field `shape_id`. Service description likewise says the layer was downloaded in February 2023 and generated with the GTFS tool. | This is a dated mapped shape layer, not proof of current route patterns, stop sequence, frequency, or operating times. Cross-check against the [official VOTRAN GIS & GTFS files page](https://www.votran.org/documents-data/) and a dated agency feed; exclude schedules/timing claims unless separately verified. |
| [Cities Dissolved Weekly (27)](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_1/FeatureServer/27) | Polygon geometry, described as municipal boundaries. Display/name field is `CITYNAME`; `Acres` is also exposed. | The title says “Weekly” but does not establish the actual last refresh. Capture metadata and retrieval timestamps; verify the selected municipality and boundary vintage before clipping features. |

The layers report spatial reference WKID 2881 and service units in feet. Keep the source CRS and service metadata with the snapshot. Confirm the exact WKID definition and coordinate transformation used by the chosen GIS stack before measuring distances or areas. Do not trust similarly named attribute fields, flags, or precomputed measures without checking their definitions.

**Current decision:** schemas support a carefully bounded *candidate inventory*, but not a claim of current access, accessibility, route service, or comprehensive coverage. The transit layers' explicit February 2023 source date makes them unsuitable as the sole evidence for a current transit claim. Licensing and the portal item records remain a hard gate; do not download for republication or publish derivatives until terms are confirmed.

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
