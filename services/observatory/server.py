"""Private, same-origin Observatory prototype. Local bind; no anonymous data API."""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

MAX_BODY = 8_000_000
IDENTITY = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def canonical(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False)


def safe_json(value, depth=0):
    if depth > 12:
        raise ValueError("JSON nesting exceeds 12 levels.")
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"__proto__", "constructor", "prototype"}:
                raise ValueError("Reserved JSON key.")
            safe_json(v, depth + 1)
    elif isinstance(value, list):
        for v in value:
            safe_json(v, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON number.")


def geometry(value):
    if not isinstance(value, dict):
        raise ValueError("Missing geometry.")
    count = 0
    def point(p):
        nonlocal count
        count += 1
        return isinstance(p, list) and 2 <= len(p) <= 3 and all(type(n) in {float, int} and math.isfinite(n) for n in p) and abs(p[0]) <= 180 and abs(p[1]) <= 90
    def line(v):
        return isinstance(v, list) and len(v) >= 2 and all(point(p) for p in v)
    def ring(v):
        return line(v) and len(v) >= 4 and v[0] == v[-1] and len({tuple(p) for p in v}) >= 3
    def many(v, check):
        return isinstance(v, list) and len(v) > 0 and all(check(p) for p in v)
    checks = {"Point": point, "MultiPoint": lambda v: many(v, point), "LineString": line, "MultiLineString": lambda v: many(v, line), "Polygon": lambda v: many(v, ring), "MultiPolygon": lambda v: many(v, lambda p: many(p, ring))}
    check = checks.get(value.get("type"))
    if check is None or not check(value.get("coordinates")) or count > 20000:
        raise ValueError("Unsupported, invalid, or oversized WGS84 geometry.")
    return count


def validate_layer(layer):
    if not isinstance(layer, dict) or not isinstance(layer.get("id"), str) or not layer["id"] or not isinstance(layer.get("name"), str) or not 1 <= len(layer["name"].strip()) <= 120:
        raise ValueError("Invalid layer identity.")
    if type(layer.get("visible")) is not bool or not re.fullmatch(r"#[a-fA-F0-9]{6}", str(layer.get("color", ""))):
        raise ValueError("Invalid layer appearance.")
    source = layer.get("source", {})
    if not isinstance(source, dict) or source.get("rights") != "unreviewed" or source.get("kind") not in {"user", "derived", "synthetic", "field"} or any(not isinstance(source.get(k), str) for k in ["name", "importedAt", "note"]) or not (source.get("sourceDate") is None or isinstance(source["sourceDate"], str)):
        raise ValueError("Source metadata and unreviewed rights are required.")
    steps = layer.get("steps")
    if not isinstance(steps, list) or len(steps) > 100 or any(not isinstance(s, dict) or any(not isinstance(s.get(k), str) for k in ["operation", "detail", "at"]) for s in steps):
        raise ValueError("Invalid processing history.")
    features = layer.get("features")
    if not isinstance(features, list) or len(features) > 2000:
        raise ValueError("Layer limit is 2,000 features.")
    ids, coordinates = set(), 0
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature" or not isinstance(feature.get("id"), str) or not feature["id"] or feature["id"] in ids or not isinstance(feature.get("properties"), dict):
            raise ValueError("Invalid feature or duplicate identity.")
        ids.add(feature["id"])
        coordinates += geometry(feature.get("geometry"))
    if coordinates > 40000:
        raise ValueError("Layer limit is 40,000 coordinates.")


def validate_project(doc):
    safe_json(doc)
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or doc.get("publication_authorized") is not False or not IDENTITY.fullmatch(str(doc.get("id", ""))) or not isinstance(doc.get("name"), str) or not 1 <= len(doc["name"].strip()) <= 120:
        raise ValueError("Expected a draft Observatory schema-1 project.")
    if len(canonical(doc).encode()) > MAX_BODY:
        raise ValueError("Project exceeds 8 MB.")
    form = doc.get("fieldForm")
    if form is not None and (not isinstance(form, dict) or not isinstance(form.get("extraLabel"), str) or not 1 <= len(form["extraLabel"].strip()) <= 80 or type(form.get("extraRequired")) is not bool):
        raise ValueError("Invalid collection form.")
    for key, maximum in [("layers", 30), ("comments", 500), ("history", 100)]:
        if not isinstance(doc.get(key), list) or len(doc[key]) > maximum:
            raise ValueError("Invalid project collections.")
    ids, names = set(), set()
    for layer in doc["layers"]:
        validate_layer(layer)
        if layer["id"] in ids or layer["name"].strip().lower() in names:
            raise ValueError("Layer names and identities must be unique.")
        ids.add(layer["id"]); names.add(layer["name"].strip().lower())
    for c in doc["comments"]:
        if not isinstance(c, dict) or any(not isinstance(c.get(k), str) for k in ["id", "text", "author", "at"]) or len(c["text"]) > 4000 or len(c["author"]) > 100 or not (c.get("featureId") is None or isinstance(c["featureId"], str)):
            raise ValueError("Invalid comment.")
    for h in doc["history"]:
        if not isinstance(h, dict) or any(not isinstance(h.get(k), str) for k in ["id", "at", "summary"]):
            raise ValueError("Invalid history entry.")


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions (id TEXT, revision INTEGER, document TEXT, PRIMARY KEY(id,revision));
            CREATE TABLE IF NOT EXISTS operations (id TEXT, operation TEXT, digest TEXT, revision INTEGER, document TEXT, PRIMARY KEY(id,operation));
            """)
    def connect(self):
        return sqlite3.connect(self.path, timeout=10)
    def get(self, project_id):
        with self.connect() as db:
            row = db.execute("SELECT revision,document FROM projects WHERE id=?", (project_id,)).fetchone()
            return {"revision": row[0], "document": json.loads(row[1])} if row else None
    def put(self, project_id, expected, operation, document):
        validate_project(document)
        if document["id"] != project_id or type(expected) is not int or expected < 0 or not isinstance(operation, str) or not IDENTITY.fullmatch(operation):
            raise ValueError("Invalid revision, operation, or project identity.")
        serialized = canonical(document)
        digest = hashlib.sha256(canonical([expected, document]).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT digest,revision,document FROM operations WHERE id=? AND operation=?", (project_id, operation)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise ValueError("An operation ID cannot be reused for different content.")
                return 200, {"revision": prior[1], "document": json.loads(prior[2])}
            current = db.execute("SELECT revision,document FROM projects WHERE id=?", (project_id,)).fetchone()
            if (current[0] if current else 0) != expected:
                return 409, {"error": "Revision conflict; review changes before retrying.", "current": {"revision": current[0], "document": json.loads(current[1])} if current else None}
            revision = expected + 1
            db.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)", (project_id, revision, serialized))
            db.execute("INSERT INTO versions VALUES (?,?,?)", (project_id, revision, serialized))
            db.execute("INSERT INTO operations VALUES (?,?,?,?,?)", (project_id, operation, digest, revision, serialized))
            db.execute("DELETE FROM versions WHERE id=? AND revision<=?", (project_id, revision - 20))
            db.execute("DELETE FROM operations WHERE id=? AND revision<=?", (project_id, revision - 20))
            return 200, {"revision": revision, "document": document}
    def delete(self, project_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for table in ["projects", "versions", "operations"]:
                db.execute(f"DELETE FROM {table} WHERE id=?", (project_id,))


def make_server(address, token, store, static):
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("OBSERVATORY_TOKEN must contain at least 32 characters.")
    static = Path(static).resolve()
    conversion = threading.BoundedSemaphore(1)
    class Handler(BaseHTTPRequestHandler):
        server_version = "ObservatoryPrivate/0.1"
        def log_message(self, fmt, *args):
            pass  # Do not log project paths, tokens, or data.
        def json(self, status, value):
            raw = canonical(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers(); self.wfile.write(raw)
        def read_json(self):
            if self.headers.get("Transfer-Encoding") or self.headers.get_content_type() != "application/json":
                raise ValueError("Use a bounded application/json request.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("Request must contain 1–8,000,000 bytes.")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete request.")
            def pairs(values):
                out = {}
                for key, value in values:
                    if key in out:
                        raise ValueError("Duplicate JSON key.")
                    out[key] = value
                return out
            value = json.loads(raw, object_pairs_hook=pairs)
            safe_json(value)
            if not isinstance(value, dict):
                raise ValueError("Expected a JSON object.")
            return value
        def route(self, method):
            self.connection.settimeout(15)
            path = urlsplit(self.path).path
            if not path.startswith("/api/"):
                if method != "GET":
                    self.json(405, {"error": "Method not allowed."}); return
                target = (static / unquote(path).lstrip("/")).resolve()
                if path == "/": target = static / "index.html"
                if not target.is_relative_to(static) or not target.is_file():
                    self.json(404, {"error": "File not found."}); return
                raw = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers(); self.wfile.write(raw); return
            self.close_connection = True
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
                self.json(401, {"error": "Private workspace token required."}); return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if origin and (urlsplit(origin).netloc != host or urlsplit(origin).scheme not in {"http", "https"}):
                self.json(403, {"error": "Cross-origin requests are not accepted."}); return
            if path == "/api/health" and method == "GET":
                self.json(200, {"status": "ready", "publication_authorized": False}); return
            match = re.fullmatch(r"/api/projects/([a-zA-Z0-9_-]{1,80})", path)
            if match:
                key = match[1]
                if method == "GET":
                    value = store.get(key); self.json(200 if value else 404, value or {"error": "Project not found."}); return
                if method == "PUT":
                    body = self.read_json()
                    status, value = store.put(key, body.get("expected_revision"), body.get("operation_id"), body.get("document"))
                    self.json(status, value); return
                if method == "DELETE":
                    store.delete(key); self.json(200, {"deleted": True}); return
            if path in {"/api/prep", "/api/export"} and method == "POST":
                body = self.read_json()
                if not conversion.acquire(blocking=False):
                    self.json(429, {"error": "A conversion is running. Retry when it finishes."}); return
                try:
                    from prep import prepare_vector, export_gpkg
                    if path.endswith("prep"):
                        result = prepare_vector(body)
                    else:
                        layer = body.get("layer"); validate_layer(layer)
                        if not layer["features"]: raise ValueError("Cannot export an empty GeoPackage.")
                        result = export_gpkg(layer, body.get("target_crs", "EPSG:4326"))
                    self.json(200, result)
                except (ImportError, ModuleNotFoundError):
                    self.json(503, {"error": "Install the locked private geospatial dependencies first."})
                except Exception:
                    # Native drivers sometimes include server paths in exceptions.
                    self.json(400, {"error": "Conversion failed. Check format, layer, source CRS, geometry, and explicit repair/drop options."})
                finally:
                    conversion.release()
                return
            self.json(404, {"error": "Endpoint not found."})
        def run_route(self, method):
            try: self.route(method)
            except (ValueError, KeyError, TypeError, OverflowError):
                self.close_connection = True; self.json(400, {"error": "Invalid or oversized request; check the project schema and selected options."})
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                self.close_connection = True
            except Exception:
                self.close_connection = True; self.json(500, {"error": "Private service error; no success was recorded by the client."})
        def do_GET(self): self.run_route("GET")
        def do_PUT(self): self.run_route("PUT")
        def do_POST(self): self.run_route("POST")
        def do_DELETE(self): self.run_route("DELETE")
    return ThreadingHTTPServer(address, Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8789)
    parser.add_argument("--db", default=str(Path(__file__).parent / "runtime" / "observatory.sqlite"))
    parser.add_argument("--static", default=str(Path(__file__).parents[2] / "apps" / "map-explain" / "dist"))
    args = parser.parse_args()
    token = os.environ.get("OBSERVATORY_TOKEN", "")
    if len(token) < 32: parser.error("Set OBSERVATORY_TOKEN to a random secret of at least 32 characters.")
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    server = make_server((args.host, args.port), token, Store(args.db), args.static)
    print(f"Observatory private service listening on {args.host}:{server.server_port}; no public deployment configured.", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
