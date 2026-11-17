# ZQM Observatory workspaces

**Prepare data. Ask about places. Capture observations. Compare coverage. Work on one map.**

The five integrated workspaces belong to **ZQM Observatory**, by **ZQM Computing**.
MapExplain remains the provisional name for traceable location questions. This is
an engineering prototype at Stage 0, not a deployed service or an approved data
product. Starter Providence records and boundaries are invented. ZQM Labs is a
separate organization and is not integrated here.

## Run locally

Requires Node.js 22.12+ and npm. From this directory:

```sh
npm ci --ignore-scripts
npm test
npm run build
npm run dev
```

For the optional client/service integration check, install Python 3.11+ and run
`npm run test:sync-service`. `OBSERVATORY_TEST_PYTHON` can select its interpreter.
This check starts its own loopback server and temporary SQLite database using
synthetic fixtures; no GIS wheels, live credentials, or running private service
are required. It simulates a lost reply and verifies retry/reload behavior and
an 8 MB project upload.

The browser workflows work without paid APIs, an external basemap, or a server.
The Vite development server proxies `/api` to the optional private service on
port 8789. See the [private service setup](../../services/observatory/README.md)
for format conversion and shared-project sync. `npm run preview` serves the
production bundle; its static preview has no private API proxy.

## Five connected workspaces

| Workspace | Working behavior |
| --- | --- |
| MapExplain | Exact layer-name questions: show a layer, within/beyond distance, nearest/farthest ranking, Point counts in Polygon zones; calculated records, map, methods, and exports |
| Data Prep | Local CSV, GeoJSON, basic KML and GPX; schema/geometry preview, explicit normalization, ring closure and rejected-record handling; EPSG:4326/3857 conversion |
| Field Collection | Required and configurable reference fields, conditional urgent follow-up, manual/GPS point capture, device-reported accuracy, resized photos, local save and review queue |
| Coverage Analysis | Demand/supply layers, radius, demand weights, configurable scoring weights, complete ranked output, saved supply scenarios and transparent formula |
| Map Workspace | Layer visibility/color, attribute text display filter, point/line/polygon drawing, attribute edits, review notes, deletion with local restoration, CSV/GeoJSON exports |

Attribute drafts are bound to the selected layer and feature. Switching features
requires loading or entering that feature’s attributes before saving.

All five use the same project layers. Prepared data and field observations can
feed questions and coverage. Drawn sites can form a new supply scenario. Saving
an analysis turns it into another project layer with input-source lineage.

Project & Sync provides portable JSON bundles, local history/restoration, private
project links, explicit push/pull, queued local changes, and three-way conflict
review. Sync is manual; there is no background upload or live multiplayer channel.
Opening another project also saves a local recovery copy before replacing it.

## Question patterns

Replace these example names with exact names from your project:

```text
Show Demand points
Show Demand points beyond 1000 m of Facilities
Show Demand points within 1.5 km of Facilities
Rank Demand points nearest to Facilities
Rank Demand points farthest from Facilities
Count Demand points in Neighborhoods
```

Subject and target follow their order in the question. Unsupported or compound
requests are rejected. The local parser is deterministic; it does not call an
LLM, infer additional filters, or claim general natural-language understanding.
Distances use spherical straight-line haversine calculations, not network travel
time. Counts use the first named layer’s Point features and the second named layer’s
Polygon features, including holes. Other geometries are excluded explicitly;
MultiPolygon counts are not implemented.
Thresholds, units, and ranking direction come from the matched question grammar;
words or distances inside a layer name do not change the operation. Demand scores
normalize against the actual maximum, including fractional weights; all-zero
demand contributes zero. Coverage uses actual Point geometries, never invented centroids. Overlapping
zones may count points more than once; boundary semantics require review.

## Data limits and lineage

- Browser preparation: 2 MB; private source files: 4 MB; 2,000 input features.
  Prepared private GeoJSON may use the project’s 8 MB budget; adding it must still
  fit the full project. Larger conversion results are rejected, not truncated.
  Over-limit sources are rejected rather than truncated.
- Project: 8 MB, 30 layers, 2,000 features and 40,000 coordinates per layer.
  One geometry is limited to 20,000 coordinates.
- Supported project geometry: Point, LineString, Polygon, and Multi variants.
  Browser checks cover structure, finite values, ranges, and closed rings.
  GEOS topology checks and other EPSG transformations require private prep.
- Coordinate CSV requires explicit latitude/longitude columns. Projected CSV
  needs private prep and its actual source CRS. No geocoding is performed.
- Private prep also accepts one zipped Shapefile dataset, GeoPackage (explicit
  layer choice when needed), KML/KMZ and GPX. Unknown CRS is not guessed;
  mismatches with declared CRS are rejected. Conversion can flatten schemas,
  generate feature IDs and omit file styling; diagnostics record those limits.
- Null/empty data and invalid coordinates require explicit rejection handling.
  Geometry repair requires an explicit option; multipart repair results are
  retained, and GeometryCollections are rejected for separate review.
- CSV escapes formula-like cells. Attribute column names are prefixed to avoid
  colliding with export metadata. CSV/GeoJSON/GPKG and project bundles preserve
  source/processing notes and blocked publication status.

## Device storage and offline behavior

Saved documents, up to five previous local documents, and the pending-sync list
live in IndexedDB for this origin. Records and optional photos persist across
reloads until replaced, cleared by the user, evicted by the browser, or removed
with browser site data. Unsaved form fields and analysis previews are not durable.
Project bundles use compact JSON so an accepted project stays within the same
8 MB restore limit. Export a project bundle for backup. A successful save is reported only after the
IndexedDB transaction completes; another tab cannot silently overwrite a newer
local revision.

**Local recovery copies:** opening a bundle, shared project, or recovered copy
retains the replaced document in the same transaction. If storage fails, neither
replacement nor recovery is committed. Project & Sync lists up to three copies
within a combined 12 MB UTF-8 budget, newest first; older copies are pruned as
needed. Copies include saved photos and source notes, without undo/sync queues or
the workspace token. They are unencrypted and remain subject to browser eviction.

Export any recovery copy as a normal project bundle, or review and open it with a
fresh project ID, no shared revision, and no automatic upload. The original server
copy is separate. At the 8 MB ceiling, if a longer new ID cannot fit, export/import
the recovery file to preserve its original identity. Deleting recovery copies
keeps the active project. Replacing device data with synthetic examples removes
the active document, undo history, photos, and every retained recovery copy after
confirmation. Exported files and server copies are separate.

The production build installs a service worker that caches its own app shell
and bundled assets. After a successful online visit, the shell can load with the
origin unavailable. API responses, records, photos, tokens, and external sources
are never cached by the service worker. Local records remain in IndexedDB.
Private sync requires connectivity and an explicit push. GPS and photo capture
must be initiated by the user; device support and permission affect availability.
Photos are re-encoded as bounded JPEGs without copying input metadata.

## Private sharing and review

A private link contains only a project ID. Recipients also need the separately
supplied workspace token and the same private server. Tokens stay in React memory,
not URLs, project bundles or device storage. Reloading clears the token. This
prototype has one workspace-wide token; it does not provide individual accounts,
roles, per-project grants, encrypted local storage, or authoritative audit signing.

Conflicting server revisions produce a review step. Independent entity edits
merge by ID; geometry arrays stay atomic. Local/shared choices are required for
conflicting values. Independent same-name layers produce a naming conflict: choose
which side keeps the original name; both datasets remain and the other name gets
a numbered suffix. Applying a merge saves locally; a later push confirms a new
shared revision. Local save conflicts require reloading; unsubmitted form values
remain visible so they can be copied before reload.

Before an upload starts, its exact project snapshot, base revision, operation ID,
and sent-operation list are saved in IndexedDB. If the reply is lost or the local
acknowledgement cannot be saved, **Retry unconfirmed upload** reuses those values,
including after reload. Re-enter the workspace token; it is never part of the
saved retry. Newer edits stay queued until the earlier upload is confirmed, then
need a separate push. Fetching a shared project is disabled while a retry is
unconfirmed. No upload runs automatically in the background.

The service check also requires a valid authenticated readiness response; an
HTML fallback or error object cannot be reported as a ready private service.

Only an acknowledgement for the requested project, exact submitted JSON content,
and next server revision clears the sent operations. Object member ordering does
not affect acknowledgement or merge equality; coordinate/array order still
matters. Invalid or unrelated responses keep the retry and local edits intact.
A validated revision conflict ends the retry and enters explicit review.

Opening a different project, applying a reviewed merge, deleting the server copy,
or resetting device data clears the relevant retry. The incoming-project review
warns before stopping an unconfirmed upload: it may already exist on the server.
Recovery copies and exported project bundles preserve documents, without sync
receipts or tokens. Browser eviction/site-data removal can erase retry data; server
receipts retain only the latest 20 revisions. A lost or expired receipt may require
explicit shared-copy review rather than confirmation.

## Evidence and release boundary

See [verification](QA.md), the [specification mapping](../../docs/observatory-workspaces-build.md),
and [competitor/naming research](../../docs/observatory-competitive-landscape.md).
MapExplain is a provisional name without trademark, domain, or handle clearance.
No new recurring service is required or purchased.

Imports remain unverified and source rights remain unreviewed. All project and
export drafts record `publication_authorized: false`. Conversion, a review badge,
or passing tests do not establish real-world facts, source permission, privacy
safety, or publication approval. The Observatory's existing release gates apply.
Voice, general AI questions, network routing, live feeds, enterprise permissions,
public anonymous sharing, real-time collaboration and production hosting are
not implemented by this build.
