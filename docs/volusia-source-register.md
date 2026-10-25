# Volusia County public-source and document register

**Research date:** 2026-10-25  
**Purpose:** expand source discovery for a bounded public-recreation inventory and identify authoritative planning documents that can explain, validate, or qualify mapped features.

This is a research register, not a data-ingestion manifest. No datasets are claimed to have been downloaded, normalized, joined, or published. Inclusion does not establish permission to redistribute source data or derivatives. Before collection, record the exact catalog item, item ID, terms, retrieval timestamp, version, and checksum.

## Decision summary

Recommended first-pass source stack:

1. Volusia County's official park directory and GIS layers for park identity and mapped geometry.
2. Volusia County's Trails Master Plan and maps for network context, distinct from proof of current trail condition.
3. City of New Smyrna Beach GIS and its Parks Master Plan for municipal cross-checks if New Smyrna Beach is selected as the pilot.
4. VOTRAN's official current GTFS and Transit Development Plan materials for dated transit information; do not rely on the County's February 2023-derived transit layers as sole evidence of current service.
5. FNAI conservation lands only as a separate conservation-land context layer, never as proof that a property is open to the public.
6. Florida DEP greenways/trails, FDOT GIS, FGDL, Florida Geospatial Open Data, Census TIGER/Line and ACS as secondary/context sources only where they answer a defined question.

The initial product should remain an inventory of sourced places and mapped features, not a safety score, accessibility rating, route-planning product, or comprehensive statement of public access.

## A. Core local sources

### A1. Volusia County park directory and official park information

- **Official directory:** [Park Map and Locations](https://www.volusia.org/services/community-services/parks-recreation-and-culture/parks-and-trails/park-facilities-and-locations/)
- **Use:** human-readable cross-check for County-listed park names, addresses, contact information, categories, hours/rules guidance, and individual park pages.
- **Can support:** that the County lists a named park and publishes an address or park page, subject to page date and later changes.
- **Cannot support alone:** that a particular entrance is usable today, every amenity is functioning, a route is step-free, or the County owns/manages a park rather than a city.
- **QA:** compare names/addresses against GIS Park Locations; preserve differences rather than silently harmonizing. Check park-specific hours, fees, closures and access notices at review time. The County's general sunrise-to-sunset guidance has exceptions (“unless otherwise posted”), so record the individual park rule where relevant.
- **Rights:** public web access is not an automatic grant to bulk-republish directory content or images. Review applicable terms before copying substantial content.

### A2. Volusia County GIS open-data portal and service catalog

- **Portal:** [Volusia County Open Data](https://opendata-volusiacountyfl.hub.arcgis.com/)
- **Service:** [Open_Data/Open_Data_4 MapServer](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/MapServer)
- **Layer catalog:** [Open_Data_4 feature layers and metadata](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/layers)
- **Candidate layers:** Park Locations (4), Park Boundaries (2), Trails (32), VOTRAN Bus Stops (33), VOTRAN Bus Routes (37). Inspect Trail Features (30) and Public Facilities (39) only if their exact definitions fit the question.
- **Municipal boundary candidate:** [Cities Dissolved Weekly, Open_Data_1 layer 27](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_1/FeatureServer/27).
- **Technical notes:** Open_Data_4 reports WKID 2881 and feet as service units. Preserve source CRS and metadata; verify the CRS definition and transformation before measuring. Service availability is not a redistribution license.
- **Known limitations:** the service-level copyright field is blank. County GIS says its data is supplied “as is” without express or implied warranty of accuracy. Neither fact establishes a data license. Obtain the precise portal item, steward, update date, attribute definitions, usage terms and any written clarification needed before collection for publication. A catalog metadata response for layer 30 (`Trail Features`) currently describes the content as “County and City parks within Volusia County,” despite the layer name and point geometry. Treat this as a metadata/semantics discrepancy, not evidence that the layer contains trail features; inspect the actual schema and sample records before use.
- **QA:** test feature count and pagination, record query parameters, detect duplicate IDs and null geometries, check invalid polygons and line-length discrepancies, and store timestamped metadata plus SHA-256 checksum. A layer titled “Weekly” is not proof it is actually refreshed weekly. Do not infer meaning from layer names alone; compare service layer metadata, item metadata, geometry type, fields, coded-value domains and representative records.

### A3. Volusia County Trails Master Plan and maps

- **Official page:** [Trails and Trails Master Plan](https://www.volusia.org/services/community-services/parks-recreation-and-culture/parks-and-trails/trails/)
- **Statewide cross-check:** [Florida DEP Online Trail Guide](https://floridadep.gov/parks/ogt/content/online-trail-guide) describes more than 1,300 existing recreational trails and defines the category as trails open to the public, excluding on-road bike lanes and sidewalks. Its ArcGIS Existing Trails layer describes an October 2023 statewide snapshot, calls itself a work in progress, and says it may be updated without warning and is not complete until review is finished. Use it to find omissions or contradictions, not as a complete or live access inventory.
- **Available material described by the County:** trail maps; enhanced bicycle/pedestrian trails; primitive hiking, biking and equestrian trails; paddling trails; interactive Trails Master Plan map; public survey.
- **Useful technical metadata:** the County's legacy trail-layer catalog describes a line dataset with fields including `Type`, `SubType`, `Surface`, `Width_Ft`, `Seg_Miles`, `Mgmt`, `Date_Input`, `LastUpdate`, `Status`, `Status_Detail`, `Source` and `URL`. It documents status values including `EXISTING`, `EXISTING FUTURE UPGRADE`, `FUTURE`, and `PROG / FUNDED`; the last three must not be silently reported as presently built/open. The legacy catalog labels its existing-trails layer as last updated April 26, 2021, which is a warning to verify the current service layer's own edit/update metadata rather than treating the legacy page as current.
- **Use:** distinguish trail types, surface and management context, planning concepts, and candidate existing versus future segments where current layer attributes support those distinctions.
- **Critical distinction:** a master-plan segment may be proposed or planned rather than built/open. Classify segments as existing, planned, proposed, under construction, or unknown only when the legend/document and current attributes support it. Neither a plan nor a `Status` value establishes current continuity, condition, public access, or accessibility.
- **QA:** save exact map/document title, version/date, layer ID, metadata retrieval time, field domains and sample values. Compare current service layer 32 against the legacy catalog and municipal sources. Flag missing/contradictory status, stale `LastUpdate`, implausible widths/lengths, duplicate identifiers and geometry gaps; field-verify where current-condition claims are intended.

### A4. Volusia County Comprehensive Plan

- **Official index:** [Volusia County Comprehensive Plan](https://www.volusia.org/services/growth-and-resource-management/planning-and-development/long-range-planning/comprehensive-plan.stml)
- **Relevant sections:** Chapter 2 Transportation; Chapter 11 Coastal; Chapter 12 Conservation; Chapter 13 Recreation and Open Space; Appendix 1 maps and figures.
- **Page's reported update:** June 10, 2025; re-check before citing.
- **Use:** policy and planning context, definitions, objectives and future priorities—not a live inventory of open parks or current conditions.
- **QA:** cite exact element, policy, map, amendment/version and page. Separate adopted policy from draft recommendations and future projections.

### A5. New Smyrna Beach municipal GIS

- **Official page:** [Maps & GIS Data — City of New Smyrna Beach](https://cityofnsb.com/236/Maps-GIS-Data)
- **Listed resources:** city interactive map, city boundaries, parks, streets, zoning, future land use, capital improvement projects, development activity, annexations, commissioner districts and Community Redevelopment Agency boundaries.
- **Use:** authoritative municipal cross-check if New Smyrna Beach is chosen. County layers may include features inside a city without establishing which government owns or maintains them.
- **QA:** record the individual map/layer URL and metadata, not only the index page. Verify whether each layer is downloadable, current, and covered by reuse terms. Do not infer park ownership from a municipal boundary.
- **Contact:** use the official page to confirm the current GIS contact before requesting item metadata or reuse clarification.

### A6. New Smyrna Beach Parks Master Plan

- **Document:** [New Smyrna Beach Parks Master Plan (PDF)](https://cityofnsb.com/DocumentCenter/View/16255/NSB-Parks-Master-FINAL_CLEAN_12621_w-Appendix-compressed)
- **Use:** local parks planning rationale, identified needs, recommendations, proposed facilities and capital priorities.
- **Temporal caution:** search indexing suggests an older planning document, approximately 2021. Verify cover date, adoption status, appendices, and whether a later plan or amendment supersedes it.
- **QA:** cite page/table/appendix for each extracted claim. Label proposed facilities as proposals, not existing amenities. Treat embedded maps as document illustrations unless underlying GIS data is separately available with terms.

## B. Transit sources and planning documents

### B1. VOTRAN official documents and data

- **Official index:** [VOTRAN Documents & Data](https://www.votran.org/documents-data/)
- **Agency-listed feed:** the index currently lists a GTFS file effective October 4, 2026. Treat that date as the agency page's listed effective date, not a permanent “current” label; recheck the index at each collection.
- **Direct feed endpoint observed in the third-party Transitland catalog:** [VOTRAN static GTFS endpoint](https://realtimevotran.availtec.com/InfoPoint/gtfs-zip.ashx). Use the agency index as the discovery/authority path and confirm the endpoint target before retrieval. Do not treat a third-party catalog as the licensor.
- **Independent feed-catalog cross-check:** Transitland's feed record identifies version `cfdff85925d066d46c1ffc3b8df08061d5067241`, fetched/added on 2026-10-08, with service dates 2026-10-07 through 2027-10-02, 23 routes and 1,304 stops. Transitland reports a SHA-1 for its archived ZIP; that is a third-party archive identifier, not a substitute for the Observatory's own SHA-256 capture checksum. These are catalog-observed metadata, not a locally downloaded or independently validated snapshot. Counts and versions can change; re-check the record and reconcile against the exact agency download before relying on them.
- **Relevant agency documents listed:** Transit Development Plan (TDP), 2025 minor update, Transit Asset Management Plan (October 2025), fare policy and rider/service policies. Plans describe planning and investment context, not a substitute for dated scheduled-service data.
- **Use:** dated route/stop/schedule information and agency planning context, subject to exact feed reuse terms.
- **Freshness:** County GIS Bus Stops and Bus Routes describe their source as downloaded in February 2023. Do not treat these as current service truth. Compare stop IDs, route IDs, shapes, service calendars and exceptions with the agency's current dated GTFS feed.
- **Minimum reproducible feed capture:** record UTC retrieval timestamp, final resolved URL, HTTP status/content type, byte size, SHA-256 checksum, feed_info.txt version and dates, and agency page's displayed effective date. Preserve the original ZIP unchanged and keep derived outputs separate.
- **GTFS QA:** validate ZIP integrity and required files; parse every table; test primary-key uniqueness and foreign-key references; validate date ranges and calendar exceptions; confirm times beyond 24:00 are handled correctly; check stop coordinates and shape sequence/continuity; reconcile route/trip/stop counts; and record all warnings. Evaluate the feed for a named service date, not simply today's date or the overall feed range.
- **Accessibility limit:** a stop's wheelchair_boarding or a trip's accessibility field is a feed assertion, not a field audit of sidewalk, curb, shelter, boarding pad, path continuity, or physical accessibility.
- **Rights:** do not assume a downloadable GTFS feed is unrestricted. Check the agency's terms and any feed license; retain evidence of the applicable terms with the collection record. If terms are unclear, use the feed for internal evaluation only until clarified and do not republish source files or derivatives.

### B2. VOTRAN Transit Development Plan and Transportation Disadvantaged Service Plan

- **Official planning page:** [TDP / TDSP](https://www.votran.org/documents-data/development-plan.stml)
- **Current process noted by the agency:** FY 2027–FY 2037 plan update; the page also links the completed FY 2022–FY 2031 plan and 2025 minor update.
- **Use:** agency goals, documented needs, public input and proposed future improvements.
- **Temporal caution:** distinguish adopted plans, annual/minor updates, draft materials and the new update process. A planned service is not an existing service. Use GTFS for current scheduled operations and the plan for context.
- **QA:** capture exact PDF title, date, status, page and map/table; compare route references with the feed's effective date.

### B3. VOTRAN Transit Asset Management Plan

- **Official index:** [VOTRAN Documents & Data](https://www.votran.org/documents-data/) lists a Transit Asset Management Plan dated October 2025.
- **Use:** agency asset and investment context; probably not needed for the initial recreation inventory.
- **Decision:** defer until the research question explicitly includes transit infrastructure or capital planning. Asset-management summaries do not prove a stop is operational or accessible.

### B4. Volusia-Flagler Transportation Planning Organization

- **Official planning studies:** [Transit Planning and Studies](https://www.r2ctpo.org/planning-studies/transit-studies/)
- **Relevant materials listed:** VOTRAN Transit Asset Management Plan 2026, VOTRAN Public Transportation Agency Safety Plan (February 2025), Transit Development Design Guidelines, and an Accessible Pedestrian Signals Action Plan.
- **Use:** regional multimodal planning context and pedestrian-infrastructure policy. An Accessible Pedestrian Signals plan is not a comprehensive inventory of accessible sidewalks or transit stops.
- **QA:** record adopted date and geographic scope; check whether a newer plan supersedes the linked version. Avoid personal safety or universal accessibility claims from policy documents.

## C. Statewide parks, trails, and conservation context

### C1. Florida Department of Environmental Protection: Greenways and Trails System

- **Official page:** [Florida Greenways and Trails System Plan and Maps](https://floridadep.gov/parks/ogt/content/florida-greenways-and-trails-system-plan-and-maps)
- **Current plan:** 2024–2028 Florida Greenways and Trails System Plan and Maps.
- **GIS downloads listed:** land-trail opportunities and priorities; paddling-trail opportunities and priorities. The page also publishes updated statewide and regional maps, including trail-status maps.
- **Use:** statewide corridor context, regional connectivity, priorities and opportunities.
- **Critical distinction:** opportunity/priority layers are planning concepts, not evidence of built, open, publicly accessible trails. Check each layer's metadata and classification before joining it to a local inventory.
- **QA:** retain map/data vintage; compare corridor and status with local agency data. Do not derive a walking route from corridor lines alone.

### C2. Florida Natural Areas Inventory: Florida Conservation Lands

- **GIS download and metadata:** [FNAI GIS Data](https://www.fnai.org/publications/gis-data)
- **Conservation land overview:** [FNAI Conservation Lands](https://www.fnai.org/conslands/conservation-lands)
- **Latest version noted during research:** Florida Conservation Lands feature class updated September 2026; FNAI recommends citing its dataset and says updates are frequent.
- **Use:** cross-check managed conservation lands and management context, not as the primary parks directory.
- **Critical caveat:** FNAI explicitly says not all conservation lands are open to the public; the database includes private managed lands. Conservation designation does not prove public entry or recreational use.
- **Rights and attribution:** FNAI requires citation in reports/products using the data and provides data as-is without warranty. Preserve its recommended citation and check the specific download's metadata and terms. A citation requirement is not a complete license grant.
- **QA:** distinguish public land, private land, easement, acquisition project and managed area. Florida Forever project boundaries may include parcels not yet acquired; do not label all project polygons publicly owned/open.

### C3. Florida Geospatial Open Data Portal

- **Official portal:** [Florida Geospatial Open Data Portal](https://geodata.floridagio.gov/)
- **Potential use:** state-agency data discovery and download in open formats. The portal advertises 2026 statewide parcel data, but parcels are not needed for the initial product.
- **Decision:** search for a specific missing dataset only after local sources are assessed. Avoid broad parcel joins for a public recreation inventory; they add privacy and licensing complexity without a clear need.
- **QA:** check each item-level steward, update date, license, geographic scope, fields and download terms. A portal-level statement that open data is free does not replace item-level review.

### C4. Florida Geographic Data Library

- **Official catalog:** [Explore Data](https://fgdl.org/explore-data/)
- **Relevant listed layer:** “Parks and Recreational Facilities in Florida – December 2024” (GC_PARKS_DEC24); city-limits layers are also listed with older vintages.
- **Use:** secondary statewide cross-check when local datasets have gaps or to identify discrepancies against a dated snapshot.
- **Freshness:** the parks layer is dated December 2024 and should not be presented as the current authoritative inventory without newer metadata.
- **QA:** capture catalog entry, source agency, metadata, data date and terms. Treat it as a comparison dataset rather than silently blending it with current local features.

### C5. Florida Department of Transportation GIS

- **Official page:** [FDOT Geographic Information System](https://fdot.gov/statistics/gis/default.shtm)
- **Potential use:** roadway and transportation-network context if route access or network connectivity becomes part of a defined analysis.
- **Limitations:** FDOT describes statewide GIS files and an “as is”/“as available” disclaimer. A road centerline does not prove a sidewalk, safe crossing, accessible path or legal pedestrian connection.
- **QA:** verify layer date, coordinate system, road definitions and item-level terms. Defer unless the pilot question requires network analysis.

## D. National sources for boundaries and aggregate context

### D1. U.S. Census Bureau TIGER/Line

- **Official 2025 page:** [TIGER/Line Shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2025.html)
- **Use:** consistent county, place, tract and other Census geography where a reproducible national boundary vintage is needed.
- **Temporal limitation:** 2025 TIGER/Line boundary/name references are as of January 1, 2025 and may not match a later-updated municipal legal boundary. TIGER/Line geometry does not itself contain demographic estimates.
- **QA:** choose geography and vintage explicitly. Do not assume a Census place boundary equals the current municipal legal boundary. Preserve source identifiers and document crosswalks.

### D2. U.S. Census Bureau American Community Survey

- **Official 2024 5-year API/data page:** [ACS 5-Year Data](https://www.census.gov/data/developers/data-sets/acs-5year/2024.html)
- **Use:** optional aggregate population/housing context only if it directly answers a defined community question.
- **Limitations:** estimates are not exact counts; include relevant margins of error and geography/vintage. Avoid demographic joins in the initial recreation inventory unless needed. Do not collect or publish person-level records.
- **QA:** record table/variable, geography, period, retrieval date and uncertainty handling. Do not compare incompatible geographies or periods without explanation.

### D3. U.S. Geological Survey and NOAA

- **Discovery:** [USGS data and tools](https://www.usgs.gov/products/data-and-tools/data-and-tools) and [NOAA Data](https://www.noaa.gov/information-technology/data).
- **Potential future uses:** USGS elevation, hydrography, land cover; NOAA weather, climate, coastal and water-level observations.
- **Decision:** not required for a basic parks/trails/stops inventory. Introduce these only for a defined environmental/hazard question with dated source and validated method.
- **Limits:** observations have temporal coverage, resolution and uncertainty. Do not convert a general hazard layer or historical observation into a claim that a specific place is safe today.

## E. Community-mapped and secondary data

### E1. OpenStreetMap

- **Project:** [OpenStreetMap](https://www.openstreetmap.org/)
- **Copyright and license:** [OpenStreetMap Copyright and License](https://www.openstreetmap.org/copyright)
- **Use:** secondary completeness check for paths, crossings, entrances and facilities missing from official datasets; useful for identifying discrepancies to investigate.
- **License:** OSM data is under the Open Database License (ODbL). Attribution and share-alike obligations may apply to a database or derivative database; review the license for the intended distribution before combining it with other datasets.
- **QA:** record extract provider, extent, timestamp, query and attribution. OSM tags are community contributions, not official confirmation of ownership, current access, condition or accessibility. Do not silently blend OSM features into an “official County inventory.”

## F. Source acceptance matrix

| Candidate | Priority | What it can support | Hard limitation / gate |
| --- | --- | --- | --- |
| County park directory | High | County-listed park names, addresses and published park-specific information | Page freshness; bulk-reuse terms; verify access/conditions individually |
| County park locations/boundaries | High, pending rights | Mapped point/polygon candidates | Item-level license unresolved; verify IDs, fields, geometry and dates |
| County Trails Master Plan/maps | High for context | Planned/recognized network and trail types when legends support them | Planned does not mean built/open; verify status |
| New Smyrna Beach GIS | High if NSB selected | Municipal park/street/boundary cross-check | Item-level metadata and reuse terms required |
| NSB Parks Master Plan | Medium/context | Local priorities and proposed improvements | Older document; verify adoption/currentness; proposals are not facilities |
| VOTRAN current GTFS | High if transit included | Dated stop/route/schedule feed | Effective date and reuse terms; feed QA; not physical accessibility evidence |
| County VOTRAN layers (2023 source) | Low / compare only | Historical comparison/discrepancy discovery | Stale for current service claims |
| VOTRAN TDP/TDSP | Medium/context | Agency planning and documented needs | Plan/update status; proposed service differs from current feed |
| FDEP trails GIS | Medium/context | State/regional corridor opportunities and priorities | Opportunities are not necessarily built, open or accessible |
| FNAI FLMA | Optional | Managed conservation-land context | Includes private land; no access inference; citation and terms |
| FGDL parks 2024 | Secondary cross-check | Comparison against a dated statewide layer | Older vintage; metadata and terms |
| FDOT GIS | Defer | Transportation-network context | Road geometry does not establish pedestrian facilities or safety |
| TIGER/Line + ACS | Defer unless needed | Reproducible geography and aggregate context | Vintage mismatch, uncertainty, unnecessary demographic joins |
| USGS/NOAA | Defer unless required | Environmental/physical context | Resolution, time and uncertainty must match claim |
| OSM | Secondary QA only | Candidate paths/facilities and discrepancy discovery | ODbL implications and community-mapped accuracy limits |

## G. Collection record required before ingestion

For every candidate layer/feed, record:

- Source title, publisher/steward, stable catalog item ID and item URL.
- Service/layer URL and exact layer ID, or exact feed download URL.
- License, terms, attribution, redistribution/derivative restrictions, and evidence of written permission if applicable.
- Dataset date, metadata update date, feed effective period/version, and retrieval timestamp in UTC.
- Geometry type, spatial reference/WKID, units, schema, unique identifier, null semantics and coded-value domains.
- Query/download parameters, format, feature/record count, pagination, checksum and snapshot location.
- QA findings: duplicate keys, nulls, invalid geometry, coordinate outliers, stale/conflicting names, schema changes and field caveats.
- Transformation/join log, target CRS, units, software/version and deterministic reproduction steps.
- Claim-level mapping: which statement each source supports and what it does not support.
- Field-verification status/date and unresolved access, hours, entrance, amenity, route continuity or accessibility questions.
- Human license review, privacy review and approval before publication.

## H. Questions to resolve with data stewards

1. What are the item-level license and redistribution terms for County Park Locations, Park Boundaries, Trails and Cities Dissolved Weekly?
2. What do each park amenity flag and status/ownership field mean, including nulls and coded values?
3. What is the actual last-update date for each County layer, and how are retired features handled?
4. What exact reuse terms apply to the agency-listed VOTRAN GTFS download, and how often is it updated? Reconcile the agency page's October 4, 2026 effective-date label with the exact downloaded feed's feed_info.txt and service calendars.
5. If New Smyrna Beach is selected, which city GIS layers are downloadable, what are their item IDs and terms, and which organization is authoritative for each park?
6. Which trail-map categories mean existing, planned, proposed or funded, and what is the latest adopted plan/version?
7. Is there a current municipal parks inventory/master plan superseding the available New Smyrna Beach plan?
8. What field evidence is required for the intended claims about entrances, hours, amenities and accessible paths?

Until these questions are resolved, source discovery can continue, but republication and strong claims remain blocked.

## Related repository standards

- [Data source overview](data-sources.md)
- [Methods](methods.md)
- [Data product standard](product-standard.md)
- [Roadmap](roadmap.md)
