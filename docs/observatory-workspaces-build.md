# Observatory integrated-workspace build

The five application briefs are implemented as connected **prototype workspaces**
in [the Observatory app](../apps/map-explain/README.md), with a shared project model
and an optional [private service](../services/observatory/README.md). Publisher:
**ZQM Computing**. This does not change the Observatory's Stage 0 release status.

Input: *GIS Application Opportunities — Build-Out Specs*, seven-page user-supplied
PDF dated November 16, 2026. SHA-256:
`195ce3f2f9a247712f43832c13d40c2a4fb1cf3b12314e16345122b8ca4df364`.
The PDF is not copied into the public repository. Its descriptions are product
requirements, not evidence of market demand or authorization to publish data.
The [competitor and naming review](observatory-competitive-landscape.md) remains
the evidence record for positioning; MapExplain is a provisional feature name.

## Specification to implementation

| Brief | Implemented prototype | Deferred or bounded |
| --- | --- | --- |
| Conversational spatial intelligence | Project-aware layer questions, display, nearest/farthest, within/beyond, Polygon counts, complete record exports, source/method lineage | Deterministic exact patterns, not general AI; voice, live catalogs, arbitrary SQL/joins and public sharing deferred |
| Data preparation and interoperability | CSV/GeoJSON structural QA, schema normalization/completeness, explicit ring closure/drop/empty-field fixes, browser EPSG:4326/3857; private GEOS repair, EPSG conversion, Shapefile ZIP/GPKG/KML/KMZ/GPX; GeoJSON/CSV/GPKG exports | Small bounded files; no raster, broad ETL pipeline, perfect format round-trip, full cartographic preservation or automatic source-rights clearance |
| Offline field collection | Configurable reference field/required flag, urgent skip rule, manual/GPS point capture with accuracy, bounded re-encoded photo, IndexedDB, review queue, queued manual revision sync; shared point/line/polygon drawing | A narrow form builder; no repeatable groups, offline basemap packages, background sync, sensor tests or device certification |
| Coverage and gap analysis | Supply/demand point layers, straight-line thresholds, optional demand field, distance/demand scoring weights, full ranked outputs, drawn scenario sites, saved results and reports via exports | Not road routing, isochrones, optimized facility placement or validated operational suitability; nonpoint features excluded explicitly |
| Everyday map workspace | Layer visibility/color, display filter, attribute edits, point/line/polygon drawing, review notes, local history/restore, portable bundles, private ID links, three-way revision merge | Manual collaboration; real-time cursors, WYSIWYG vertex editing, enterprise roles, public publishing and full GIS cartography deferred |

## Shared foundation

One schema-1 project stores layers, geometry, attributes, sources, processing
steps, collection-form settings, notes, and a bounded change history. Drafts keep
`publication_authorized: false`; rights stay `unreviewed`. Derived layers include
input-source snapshots and their prior processing steps. Export metadata does
not convert an unknown source permission into a granted right.

Device persistence uses one IndexedDB read/compare/write transaction per save.
The save status changes only after transaction completion. A stale second tab
receives an explicit conflict and retains its unsubmitted form value. Up to five
prior documents allow local restoration while preserving change-log entries.
The queued list records local edits; it is not a background task or durable
server acknowledgement until a push succeeds.

The private service uses authenticated same-origin HTTP and SQLite compare-and-swap
transactions. It retains twenty revisions and receipts, enforces idempotent
retries within that window, and returns current state on a conflict. A client
three-way merge combines independent stable-ID edits and requires explicit
local/shared choices for conflicting values. Geometry arrays remain atomic.
Applying a merge does not publish or push it automatically.

Production builds precache only the app shell and its own assets. IndexedDB
holds saved records separately. The service worker excludes APIs and external
origins and does not cache private response bodies, photos, or tokens.

## Acceptance and evidence

[QA evidence](../apps/map-explain/QA.md) distinguishes automated coverage,
observed desktop behavior, offline checks, and remaining device/private-sync UI
checks. Every implemented workflow is reachable from the same five-tab shell;
this build is working code rather than a set of product landing pages.

No deployment, paid service, real-source acquisition, or data publication was
performed. Before a real customer pilot, complete the existing security/privacy
and release gates, individual access controls where required, production hosting,
mobile/GPS checks, operator backup/recovery rehearsal, and a permitted source
review for that exact workflow. A code PR cannot approve those outcomes.
