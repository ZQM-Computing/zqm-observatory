# Observatory private service

This optional Python service supplies authenticated vector conversion and
revision-aware shared projects for the [Observatory workspaces](../../apps/map-explain/README.md).
It serves the production frontend and `/api` on the same origin. No external
AI, geocoding, map tiles, hosted database, or paid service is required.

## Setup

Requires Python 3.11+ with binary wheels for the locked geospatial dependencies.
Build the frontend first. From this directory on Linux/macOS:

```sh
python -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.lock.txt
.venv/bin/python -m unittest discover -s tests -v
```

On Windows use `.venv/Scripts/python.exe` instead. `requirements.txt` records the
four direct GIS dependencies; `requirements.lock.txt` pins the tested complete
resolution. Dependency upgrades require fresh conversion and regression checks.

Set `OBSERVATORY_TOKEN` to a randomly generated secret of at least 32 characters
through your local process/secret manager, then start:

```sh
.venv/bin/python server.py
```

The service defaults to `127.0.0.1:8789`, SQLite at
`runtime/observatory.sqlite`, and the frontend at `../../apps/map-explain/dist`.
`--host`, `--port`, `--db`, and `--static` override these paths/settings. The token
is not printed. Runtime files and virtual environments are ignored by Git.
Open the service origin for production-build offline support, or use the Vite
frontend during development (its same-origin `/api` proxy targets port 8789).

## API contract

All `/api` calls require `Authorization: Bearer <token>`. Requests from a different
Origin are rejected. API responses use `Cache-Control: no-store`; tokens and
payloads are not logged. JSON has bounded size/depth and duplicate/reserved keys
are rejected. Authentication is checked before body processing.

| Endpoint | Contract |
| --- | --- |
| `GET /api/health` | Authenticated readiness response; no records |
| `GET /api/projects/{id}` | Current validated project and server revision |
| `PUT /api/projects/{id}` | `document`, integer `expected_revision`, unique `operation_id`; 409 returns current document on revision mismatch |
| `DELETE /api/projects/{id}` | Deletes current document, retained versions, and operation receipts |
| `POST /api/prep` | `filename`, `content_base64`, optional `source_crs`, `layer`, explicit `repair` and `drop_invalid`; returns diagnostics and WGS84 FeatureCollection or layer choices |
| `POST /api/export` | Validated project `layer` and EPSG `target_crs`; returns a draft GeoPackage as base64 with source/method metadata |

SQLite read/compare/write uses `BEGIN IMMEDIATE`. Only one writer can advance a
revision. Within the latest 20 revisions, repeating the same operation/body
returns its original receipt; reusing its ID for another body fails. Older
receipts expire, but a stale expected revision still fails. Twenty server
versions are retained for operational recovery; there is no version-selection
API yet. Deletion removes these versions too.

Private prep allows files up to 4 MB, 2,000 input features, and 40,000 output
coordinates. ZIPs are limited to 100 members and 40 MB expanded, with traversal
and symlink rejection. Only the required same-dataset Shapefile companions are
extracted into a temporary directory. XML DTDs/entities and source URL ingestion
are rejected. PROJ network access is disabled. One conversion runs at a time;
concurrent conversion requests return 429. Native driver errors are returned as
a bounded diagnostic without exposing filesystem paths. Project geometry and
source metadata are independently validated on each save.

## Operational limits

Keep the default loopback bind for local review. This standard-library server is
a private prototype, not an Internet-facing production gateway. Before remote
use, deploy behind managed TLS and network access controls, define individual
identity/authorization, resource/process isolation for native file parsers,
monitoring, encryption and backup retention. No such deployment is included.
One token currently covers all projects in the instance; it provides no user
attribution, project-specific permission, quotas per user, or access revocation
for an individual recipient. Use only synthetic/permitted nonsensitive data in
this review environment.

SQLite and photos are stored unencrypted. Restrict operating-system access to
the runtime directory. Back up SQLite with its online backup API while live, or
stop the service and copy the database consistently; do not copy only the main
file while WAL writes are active. A rollback consists of stopping the service,
restoring a consistent database backup, and rebuilding the prior frontend commit.
The only schema is version 1; no migration of an existing production service is
performed. Keep rollback/export evidence before deleting or replacing records.

All documents and exports remain drafts with publication blocked. The service
cannot grant source rights or approve an Observatory data product.
