# Item-level source audit: Volusia parks, trails, and transit

**Audit date:** 2026-10-25  
**Evidence class:** public documentation and ArcGIS layer metadata only. No feature records, full feeds, or bulk datasets were downloaded or sampled for this audit.  
**Release decision:** all candidate data remain blocked for public redistribution pending item-specific rights review. This document is not a license determination.

## Executive findings

The five candidates in issue #18 are not equivalent:

- **Park Locations (4):** useful point-index candidate; attribute semantics and source terms are undocumented in layer metadata.
- **Park Boundaries (2):** useful polygon candidate; includes owner/maintenance fields and edit timestamps, but a mapped boundary is not a legal parcel boundary or proof of public access.
- **Trails (32):** best candidate for trail geometry, but its metadata has no description or copyright text; current status, provenance, and access semantics remain unverified.
- **VOTRAN Bus Stops (33):** expressly says downloaded in February 2023. It is stale for a current transit product and must not be presented as current stops.
- **VOTRAN Bus Routes (37):** likewise says downloaded in February 2023 and generated using ESRI Streets plus the GTFS tool in ArcGIS Pro. This is derived route geometry, not evidence of current schedule/service or necessarily the exact route path.
- **Trail Features (30):** point geometry with description “County and City parks within Volusia County.” Exclude from trailheads/trail features unless record-level evidence resolves the mismatch.

The County's current public VOTRAN document index lists a GTFS feed effective **October 4, 2026**. This reinforces that the County's February 2023-derived transit layers are too old for current-service claims. The current agency listing does not settle GTFS reuse rights.

## Item-by-item decision matrix

| Item | Observed metadata | Main quality / semantic risks | Rights state and decision |
|---|---|---|---|
| Park Locations (layer 4) | Point geometry; display field Name. Fields include REF, Name, Address, CityName, Zip, Phone, Type, URL, Status, Acres, and amenity fields Restrooms, Playground, Fields, Courts, Trails, Sidewalk, PicnicFac, SkatePark, DogPark, Pier, BoatRamp, Canoe, DiscGolf, SplashPad, Parking, Concession, Shed, NoBenches, and NoTrashRec. Description and copyright fields are blank. | Amenity indicators are strings, not typed booleans; distinct values and null/empty conventions are unknown. Status semantics and stewardship scope are undocumented. A point is not an entrance. A GIS listing does not prove current hours, availability, accessibility, or ownership. | BLOCKED_PENDING_REVIEW. Candidate only. After rights permit inspection, profile distinct values, nulls, duplicate names/REFs, coordinate offsets, and directory discrepancies. |
| Park Boundaries (layer 2) | Polygon geometry; fields include Name, Address, CityName, Zip, Type, REF, Owner, MaintAuth, URL, Acres, Acreage, ParkID, created_date, last_edited_date, Shape__Area, and Shape__Length. Description and copyright fields are blank. | A park boundary is not a cadastral/legal boundary, property title, public easement, or access authorization. Acres and Acreage may disagree; independently calculate area in a suitable projected CRS. Test multipart/invalid polygons, overlaps, slivers, duplicate ParkID, and point-in-polygon mismatch. Owner and maintenance authority are distinct concepts. | BLOCKED_PENDING_REVIEW. Candidate only. Preserve source area fields and add independent QA fields; never label as legal property boundaries. |
| Trails (layer 32) | Polyline geometry; fields include OBJECTID_1, Name, Name2, Name3, Type, SubType, Surface, Width_Ft, Seg_Miles, URL, TrailName, REF, miles, MaintainedBy, Owner, and Shape__Length. Description and copyright are blank; max record count is 2,000 and pagination is supported. | Record samples have not established the meaning of type/subtype values. Seg_Miles, miles, and Shape__Length may reflect different calculations/units and require reconciliation. Geometry does not prove public access, continuity, construction, maintenance, open status, safety, or accessibility. Object IDs are not stable cross-version identifiers. | BLOCKED_PENDING_REVIEW. Highest-priority candidate for future technical QA, but no collection for publication until terms are resolved. |
| VOTRAN Bus Stops (layer 33) | Point geometry. Description says “Votran Bus Stops downloaded 02/2023 and created using ESRI Streets and the GTFS tool in ArcGIS Pro.” Copyright text says VOTRAN. Fields include shape_id, sequence, stop_id, stop_code, stop_name, stop_desc, stop_lat, stop_lon, stop_url, location_type, parent_station, and wheelchair_boarding. | Explicit February 2023 vintage is stale for current service. wheelchair_boarding is typed as a string and needs GTFS-spec interpretation. Reconcile stop IDs, coordinates, parent stations, inactive/relocated stops, and name changes. A stop point does not establish safe crossings, shelter, sidewalk, boarding conditions, or an accessible path. | BLOCKED_PENDING_REVIEW. Do not use as current stops. Prefer a newly captured official GTFS version after rights are confirmed and the feed validates. |
| VOTRAN Bus Routes (layer 37) | Polyline geometry. Description says routes were downloaded 02/2023 and created using ESRI Streets plus the GTFS tool in ArcGIS Pro. Copyright text says VOTRAN. Fields include shape_id, route_id, agency_id, route_short_name, route_long_name, route_desc, route_type, route_url, route_color, route_text_color, route_sort_order, and route_type_text. | February 2023 vintage. Derived street geometry method and source version are not fully recorded. Geometry alone does not establish active trips, time of day, direction, calendar, stop sequence, or current service. Route IDs and shapes may change. | BLOCKED_PENDING_REVIEW. Do not use for current route/service claims. Prefer a rights-cleared current GTFS feed and keep schedule validity separate from geometry validation. |
| Trail Features (layer 30; related candidate) | Point geometry; description states “County and City parks within Volusia County”; fields include LastEdit, EditBy, X_Coord, Y_Coord, REF, Trail_Ref, Trail_Ref2, Trail_Ref3. Copyright is blank. | Name suggests trails, but description and fields suggest park locations/references. Do not call these trailheads or access points based on name alone. Compare with Park Locations before considering use. | BLOCKED_PENDING_REVIEW. Exclude from trail inventory pending semantic and rights evidence. |

## Rights and authority review

### Volusia County layers

The public ArcGIS REST metadata exposes candidate layers, but descriptions and copyright fields are blank for Park Locations, Park Boundaries, and Trails. VOTRAN-derived layers display “VOTRAN” as copyright text; that is attribution metadata, **not** a grant of redistribution rights. The County GIS information page's “as is” disclaimer addresses warranty, not necessarily reuse permissions. This desk audit did not verify an explicit item-level license or grant covering the intended transformation and redistribution.

Required evidence for each layer: authoritative portal item ID, data steward, displayed license/terms, retrieval timestamp, exact permitted uses (automated capture, transformation, spatial join, public display, raw redistribution, derived redistribution), required attribution, and a scoped decision. If terms remain ambiguous, obtain written clarification before collecting for publication.

### Current VOTRAN GTFS

The [official VOTRAN Documents & Data page](https://www.votran.org/documents-data/) lists “VoTran GTFS Data (Effective October 4, 2026)” and an earlier June 28, 2026 feed. This is the best current discovery path. Transitland can help compare versions and counts, but it is not the licensor and cannot substitute for agency terms.

Before using GTFS, record the exact official link and retrieval timestamp; inspect feed_info.txt, agency.txt, routes.txt, trips.txt, shapes.txt, stops.txt, stop_times.txt, calendar.txt, and calendar_dates.txt where present; validate date coverage and referential integrity; calculate a local SHA-256; and preserve the original ZIP unchanged. Do not treat the County's 2023 derived layers as a proxy for the October 2026 feed.

### Municipal and secondary sources

The [City of New Smyrna Beach Maps & GIS Data page](https://cityofnsb.com/236/Maps-GIS-Data) lists a Parks map and identifies a GIS contact for data questions. It is a useful municipal source if NSB is selected as the pilot, but this review did not verify a city data license or download a municipal dataset.

Florida DEP trail layers, FDOT SUN Trail maps, County master-plan documents, and municipal pages can corroborate planning context or identify conflicts. Retain their own dates, status vocabularies, attribution, and reuse review; none should be treated as a universal source of current access or condition.

## Required next steps in order

1. **Resolve rights before bulk collection.** Complete a separate rights record for each County layer and the current VOTRAN GTFS feed. If an authoritative license is not discoverable, ask the steward for written clarification; no message has been sent by this audit.
2. **Capture metadata only after scope is allowed.** Save service and layer JSON, exact URLs, UTC retrieval time, HTTP status, content type, byte count, SHA-256, fields/domains, max record count, edit-date fields, spatial reference, and units.
3. **Profile records reproducibly.** Record total count, pagination, sample query/order, null rates, distinct coded/string values, duplicate IDs/names, outliers, geometry validity, and before/after counts. Keep raw captures immutable.
4. **Reconcile parks.** Compare layer 4 points to layer 2 polygons and official County/municipal park pages; investigate duplicates, missing counterparts, mismatched names, Owner vs MaintAuth, amenity flags, and area discrepancies.
5. **Reconcile trails.** Compare layer 32 to the legacy trail catalog and planning layers. Keep raw source status distinct from any derived interpretation; do not merge planned/funded segments into an existing/open inventory.
6. **Replace stale transit layers for current claims.** Use a rights-cleared current GTFS snapshot. Compare stops by stop ID/coordinates and routes by route/trip/shape/calendar relationships. Report feed effective dates and known gaps.
7. **Separate geometry from user-facing claims.** Public access, hours, entrances, route continuity, current conditions, safety, and accessibility require appropriate current evidence; field-condition claims require dated field verification.
8. **Re-review rights at release.** Recheck the exact source version, intended output, attribution, and output-license compatibility. Keep publication blocked until all gates pass.

## Source evidence reviewed

- [County Open_Data/Open_Data_4 FeatureServer layer catalog](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/layers)
- [Park Boundaries, layer 2](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/2)
- [Park Locations, layer 4](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/4)
- [Trails, layer 32](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/32)
- [VOTRAN Bus Stops, layer 33](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/33)
- [VOTRAN Bus Routes, layer 37](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/37)
- [Trail Features, layer 30](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/30)
- [Volusia County GIS information](https://www.volusia.org/services/financial-and-administrative-services/finance-department/information-technology/geographic-information-services/)
- [VOTRAN official documents and GTFS index](https://www.votran.org/documents-data/)
- [City of New Smyrna Beach Maps & GIS Data](https://cityofnsb.com/236/Maps-GIS-Data)

**Audit conclusion:** the next engineering step is a rights-aware, metadata-first capture/QA utility, not a public data product. It should fail closed when a source has not been approved for the exact intended operation and should not download feature records by default.
