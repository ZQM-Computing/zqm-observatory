# Volusia trail evidence matrix and collection gate

**Research date:** 2026-10-25  
**Status:** desk research; no feature records downloaded, sampled, field-checked, or republished.  
**Decision:** use County Trails (layer 32) as the primary candidate geometry for further investigation; do not publish a trail inventory until source rights, record semantics, status, and field validation are resolved.

## Why this source needs more than a name-based check

The County Open_Data_4 service exposes a polyline layer named **Trails (32)** with fields for names, use type, subtype, surface, width, segment miles, managing party, owner, and shape length. Its metadata has a blank description and blank copyright text. A separate point layer named **Trail Features (30)** is described as “County and City parks within Volusia County.” It should not be treated as trailheads or trail features without record-level evidence. The service reports WKID 2881 and feet; preserve that source CRS and document any transformation.

- County layer catalog: [FeatureServer layers](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/layers)
- Trails layer 32: [FeatureServer layer 32](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/32)
- Trail Features layer 30: [FeatureServer layer 30](https://maps5.vcgov.org/arcgis/rest/services/Open_Data/Open_Data_4/FeatureServer/30)
- County legacy existing-trails catalog: [Existing Trails catalog](https://maps.vcgov.org/gis/data/ExistingTrails.htm)
- County Trails Master Plan page: [Trails and Trails Master Plan](https://www.volusia.org/services/community-services/parks-recreation-and-culture/parks-and-trails/trails/)

## Evidence matrix

| Evidence source | What it can support | What it cannot establish alone | Required handling |
| --- | --- | --- | --- |
| County Trails layer 32 | County-published line geometry and attributes as observed on a dated capture | Current open status, continuous usable route, public access, ownership, maintenance responsibility, accessibility, or reuse permission | Capture item/service metadata, terms, query parameters, UTC retrieval time, response status, byte count, SHA-256; profile every field and domain; preserve source rows unchanged |
| County Trail Features layer 30 | County-published point features; metadata currently describes County and City parks | That points are trailheads, trail access points, or trail amenities | Keep out of trailhead layer until sampled attributes and linked references demonstrate meaning; compare with Park Locations (4) and Park Boundaries (2) |
| Legacy ExistingTrails catalog | A separate County-described existing-trails layer; catalog lists line geometry and a last-update date of April 26, 2021 | Current completeness or present-day operating status | Treat as a stale cross-check; retain field/status differences and do not overwrite newer source values |
| County Trails Master Plan catalog and plan | Network vision, trail categories, planning attributes and proposed connectivity | That every planned segment is built, open, funded, or connected today | Preserve status distinctions; map proposed/planned separately from observed existing segments |
| Florida DEP Online Trail Guide / statewide existing-trails service | Statewide discovery and discrepancy leads | Complete or authoritative local inventory; current condition; unrestricted derivative rights | DEP describes the statewide dataset as an October 2023 snapshot and work in progress; use as a secondary lead only |
| FDOT SUN Trail mapping and PDFs | Dated regional-network context, project status categories, and identified gaps | Universal trail access, current field condition, or compatibility with every user mode | Capture the exact data/map vintage; distinguish existing/open from construction phases, unfunded gaps, and other planned segments |
| Local municipal park/trail pages and field notes | Local corroboration of a named site, posted access information, and observations at a stated time | Countywide completeness or permanent access/condition | Attribute each claim to its source and observation date; field observations are time-bounded and should not be generalized |

## New research finding: FDOT status is not the same as open trail

FDOT's SUN Trail Mapping Information page states that its data may lag administrative changes and recent Office of Greenways and Trails actions. Its status values reflect investment/status conditions and do not by themselves determine user modes or community need. FDOT publishes a St. Johns Loop “At-A-Glance” map updated August 2026 and a “Connecting the Gaps” map updated September 2026. These are stronger, dated regional cross-checks than undated screenshots, but still planning/network evidence rather than a local condition audit.

- FDOT mapping guidance and current map dates: [SUN Trail Mapping Information](https://www.fdot.gov/planning/systems/systems-management/SUNTrail/maps.shtm)
- Example regional project record: [US 1 St. Johns Loop project](https://www.cflroads.com/project/439865-1) (approximately 18-mile PD&E study intended to address a trail gap; last updated August 6, 2026).

Do not collapse “existing,” “programmed,” “partially programmed,” “gap/unknown,” “under construction,” and “planned” into one Boolean field. Store source-native status and a separate Observatory interpretation with rationale and evidence citation.

## Required next collection run

1. **Rights gate first.** Identify the exact County portal item and data steward for layer 32; preserve the displayed terms/license and timestamp. Blank copyright metadata and public accessibility are not a license grant. If redistribution and derivative-use terms remain unclear, keep use internal and request written clarification.
2. **Capture metadata.** Save the complete layer JSON and service JSON; record final URL, UTC time, HTTP status, content type, byte count, SHA-256, service/layer IDs, spatial reference, maximum record count, fields, domains, edit timestamps, and source attribution.
3. **Inspect representative records.** Query a bounded, reproducible sample ordered by object ID and a full attribute-only export if terms permit. Record total count and pagination strategy. Include populated and null values, every distinct status/type/surface value, duplicates, and records with conflicting ownership/management.
4. **Test geometry and attributes.** Validate null/empty geometries, geometry type, coordinate ranges, duplicate or near-duplicate segments, self-intersections where relevant, length in source units versus Shape__Length, miles, and Seg_Miles, and name/ID consistency. Document tolerance and CRS transformation.
5. **Reconcile without silently overwriting.** Compare layer 32 to the legacy ExistingTrails catalog, the County master-plan map, current FDOT SUN Trail data/maps, DEP as a secondary lead, and municipal sources. Keep source-specific status, date, and attribution columns. Investigate conflicts rather than selecting a winner automatically.
6. **Do not infer access from geometry.** A mapped line does not prove a public right-of-way, entrance, legal access, open hours, maintenance, surface condition, continuity, lighting, safety, or accessibility. Use dated agency statements for published claims and field verification for condition claims.
7. **Review privacy and publication.** Use public-place aggregates only; do not add individual movement data, user traces, or games telemetry. Publish only after license review, reproducible QA, source citations, caveats, and a correction process are in place.

## Minimum per-feature provenance fields for a future derived inventory

- source_name, source_url, source_item_id, source_layer_id
- source_object_id or stable source identifier, without pretending object IDs are stable across refreshes
- source_retrieved_at_utc, source_updated_at (nullable), source_sha256
- source_status_raw, observatory_status, status_rationale
- license_or_terms_url, rights_review_status, attribution_text
- geometry_validation_status, attribute_validation_status, field_check_status, field_checked_at
- known_limitations, reviewed_at_utc

Keep raw source fields immutable in the capture. Store normalization and interpretation in separate fields or derived tables.

## Publication gate

A public release is blocked until all are true:

- [ ] Source-specific rights/terms reviewed and redistribution/derivative permissions documented.
- [ ] A reproducible source capture exists with checksum and retrieval metadata.
- [ ] Schema, domains, record counts, geometry, CRS, and length calculations have documented QA results.
- [ ] Planned/funded/in-progress segments are distinguished from evidence-supported existing/open segments.
- [ ] Material conflicts with County, municipal, FDOT, and statewide sources are documented.
- [ ] Public access, current conditions, and accessibility claims are supported by appropriate evidence, not inferred from geometry.
- [ ] Attribution, limitations, freshness date, and correction/contact process are published with the product.

**Current gate state:** blocked. This document is desk research and does not assert that source rights, feature samples, or field conditions have been validated.
