import base64
import copy
import io
import hashlib
import json
import sqlite3
import http.client
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1]))
from server import Store, make_server, validate_project
from prep import prepare_vector, export_gpkg

TOKEN = "test-only-" + "x" * 40

def feature(geometry=None):
    return {"type": "Feature", "id": "one", "geometry": geometry or {"type": "Point", "coordinates": [-71.4, 41.8]}, "properties": {"name": "Example"}}

def layer():
    return {"id": "layer", "name": "Example", "features": [feature()], "visible": True, "color": "#123456", "steps": [], "source": {"kind": "user", "name": "fixture", "importedAt": "2026-11-17T12:00:00Z", "sourceDate": None, "rights": "unreviewed", "note": "Synthetic test only"}}

def document():
    return {"schema_version": 1, "id": "test-project", "name": "Example", "publication_authorized": False, "layers": [layer()], "comments": [], "history": []}

def payload(name, data, **options):
    return {"filename": name, "content_base64": base64.b64encode(data).decode(), **options}

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.sqlite")
        static = Path(self.temp.name) / "dist"; static.mkdir(); (static / "index.html").write_text("test shell")
        self.server = make_server(("127.0.0.1", 0), TOKEN, self.store, static)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def call(self, path, body=None, method=None, token=TOKEN, headers=None):
        req = Request(self.url + path, data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None, method=method, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", **(headers or {})})
        try:
            with urlopen(req, timeout=5) as response: return response.status, response.read(), response.headers
        except HTTPError as e: return e.code, e.read(), e.headers
    def test_authentication_origin_static_and_traversal(self):
        self.assertEqual(self.call("/api/health", token="")[0], 401)
        self.assertEqual(self.call("/api/health", headers={"Origin": "https://foreign.example"})[0], 403)
        status, raw, headers = self.call("/api/health"); self.assertEqual(status, 200); self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertFalse(json.loads(raw)["publication_authorized"])
        self.assertEqual(self.call("/")[1], b"test shell")
        self.assertEqual(self.call("/missing.js")[0], 404)
        self.assertEqual(self.call("/%2e%2e/test.sqlite")[0], 404)
        with self.assertRaises(ValueError): make_server(("127.0.0.1", 0), "short", self.store, ".")
    def test_compare_and_swap_idempotency_and_delete_retained_versions(self):
        body = {"document": document(), "expected_revision": 0, "operation_id": "op-1"}
        first = self.call("/api/projects/test-project", body, "PUT"); self.assertEqual(first[0], 200)
        self.assertEqual(json.loads(first[1])["revision"], 1)
        self.assertEqual(self.call("/api/projects/test-project", body, "PUT")[1], first[1])
        body["document"]["name"] = "Changed"
        self.assertEqual(self.call("/api/projects/test-project", body, "PUT")[0], 400)
        body["operation_id"] = "op-2"
        conflict = self.call("/api/projects/test-project", body, "PUT"); self.assertEqual(conflict[0], 409)
        self.assertEqual(json.loads(conflict[1])["current"]["document"]["name"], "Example")
        body["expected_revision"] = 1
        self.assertEqual(self.call("/api/projects/test-project", body, "PUT")[0], 200)
        self.assertEqual(self.call("/api/projects/test-project", method="DELETE")[0], 200)
        self.assertEqual(self.call("/api/projects/test-project")[0], 404)
        with self.store.connect() as db:
            for table in ["versions", "operations"]: self.assertEqual(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
    def test_simultaneous_writers_accept_one_revision(self):
        barrier = threading.Barrier(2); results = []
        def write(number):
            doc = document(); doc["name"] = f"Writer {number}"; barrier.wait()
            results.append(self.store.put(doc["id"], 0, f"op-{number}", doc)[0])
        a = threading.Thread(target=write, args=(1,)); b = threading.Thread(target=write, args=(2,)); a.start(); b.start(); a.join(); b.join()
        self.assertEqual(sorted(results), [200, 409]); self.assertEqual(self.store.get("test-project")["revision"], 1)
    def test_validation_rejects_rights_claims_bad_coordinates_and_schema(self):
        for mutation in [lambda d: d.update(publication_authorized=True), lambda d: d["layers"][0]["source"].update(rights="approved"), lambda d: d["layers"][0]["features"][0]["geometry"].update(coordinates=[181, 0]), lambda d: d["layers"][0]["features"][0]["properties"].update({"__proto__": {}}), lambda d: d.update(fieldForm={"extraLabel": "", "extraRequired": True})]:
            doc = document(); mutation(doc)
            with self.assertRaises(ValueError): validate_project(doc)
        self.assertEqual(self.call("/api/projects/other", {"document": document(), "expected_revision": 0, "operation_id": "op"}, "PUT")[0], 400)
    def test_retention_is_bounded(self):
        for revision in range(23): self.store.put("test-project", revision, f"op-{revision}", document())
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM versions").fetchone()[0], 20)
            self.assertEqual(db.execute("SELECT count(*) FROM operations").fetchone()[0], 20)
    def test_unicode_projects_use_utf8_size_and_round_trip_over_http(self):
        doc = document(); doc["layers"][0]["features"][0]["properties"]["description"] = "界" * 1_400_000
        utf8 = json.dumps(doc, ensure_ascii=False).encode()
        self.assertLess(len(utf8), 8_000_000)
        self.assertGreater(len(json.dumps(doc).encode()), 8_000_000)
        body = {"document": doc, "expected_revision": 0, "operation_id": "unicode-save"}
        status, raw, _ = self.call("/api/projects/test-project", body, "PUT")
        self.assertEqual(status, 200); self.assertIn("界".encode(), raw)
        fetched = self.call("/api/projects/test-project")
        self.assertEqual(fetched[0], 200)
        saved = json.loads(fetched[1])["document"]
        self.assertEqual(hashlib.sha256(json.dumps(saved,sort_keys=True).encode()).hexdigest(),hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest())
        oversized = copy.deepcopy(doc); oversized["layers"][0]["features"][0]["properties"]["description"] = "界" * 2_700_000
        with self.assertRaises(ValueError): validate_project(oversized)
        # Send only oversized headers: early rejection need not drain an 8 MB body.
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            client.request("PUT", "/api/projects/test-project", headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json","Content-Length":"8100000"})
            response = client.getresponse(); self.assertEqual(response.status, 400); response.read()
        finally: client.close()
        self.assertEqual(self.store.get("test-project")["revision"], 1)

    def test_receipts_from_ascii_escaped_json_remain_valid_after_utf8_upgrade(self):
        doc = document(); doc["name"] = "Café 地図"
        self.store.put("test-project", 0, "legacy-retry", doc)
        legacy = json.dumps([0,doc],separators=(",",":"),sort_keys=True,allow_nan=False,ensure_ascii=True)
        with self.store.connect() as db:
            db.execute("UPDATE operations SET digest=? WHERE id=? AND operation=?",(hashlib.sha256(legacy.encode()).hexdigest(),"test-project","legacy-retry"))
        body = {"document":doc,"expected_revision":0,"operation_id":"legacy-retry"}
        result = self.call("/api/projects/test-project",body,"PUT")
        self.assertEqual(result[0],200);self.assertEqual(json.loads(result[1])["revision"],1)
        body["document"]["name"] = "Different"
        self.assertEqual(self.call("/api/projects/test-project",body,"PUT")[0],400)

    def test_unpaired_surrogates_round_trip_and_legacy_documents_remain_readable(self):
        doc = document()
        doc["layers"][0]["name"] = "a" * 109 + "\ud83d"
        doc["layers"][0]["features"][0]["properties"]["low_\udc00"] = "Café 😀"
        body = {"document":doc,"expected_revision":0,"operation_id":"surrogate-save"}
        request = Request(self.url + "/api/projects/test-project", data=json.dumps(body, ensure_ascii=True).encode(), method="PUT", headers={"Authorization":"Bearer " + TOKEN,"Content-Type":"application/json"})
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            raw = response.read()
        self.assertIn(b"\\ud83d", raw); self.assertIn(b"\\udc00", raw)
        self.assertIn("Café 😀".encode(), raw)
        self.assertEqual(json.loads(raw)["document"], doc)
        self.assertEqual(json.loads(self.call("/api/projects/test-project")[1])["document"], doc)
        # Documents persisted by the earlier ASCII serializer still load.
        with self.store.connect() as db:
            db.execute("UPDATE projects SET document=? WHERE id=?",(json.dumps(doc, ensure_ascii=True),"test-project"))
        status, raw, _ = self.call("/api/projects/test-project")
        self.assertEqual(status, 200); self.assertEqual(json.loads(raw)["document"], doc)
        with urlopen(request, timeout=5) as response:
            self.assertEqual(json.loads(response.read())["revision"], 1)

    def test_database_context_rolls_back_and_closes_its_handle(self):
        self.store.put("test-project",0,"initial",document())
        with self.assertRaises(RuntimeError):
            with self.store.connect() as db:
                db.execute("UPDATE projects SET revision=99 WHERE id='test-project'")
                raise RuntimeError("abort test transaction")
        self.assertEqual(self.store.get("test-project")["revision"],1)
        with self.assertRaises(sqlite3.ProgrammingError): db.execute("SELECT 1")

    def test_http_private_conversion_and_export(self):
        body = payload("points.geojson", json.dumps({"type": "FeatureCollection", "features": [feature()]}).encode(), source_crs="EPSG:4326")
        result = self.call("/api/prep", body, "POST"); self.assertEqual(result[0], 200, result[1])
        self.assertEqual(len(json.loads(result[1])["collection"]["features"]), 1)
        result = self.call("/api/export", {"layer": layer(), "target_crs": "EPSG:3857"}, "POST"); self.assertEqual(result[0], 200, result[1])
        self.assertTrue(base64.b64decode(json.loads(result[1])["content_base64"]).startswith(b"SQLite format 3"))

class GeospatialTests(unittest.TestCase):
    def test_known_crs_conversion_and_missing_source(self):
        point = feature({"type": "Point", "coordinates": [111319.49079327357, 111325.1428663851]})
        data = json.dumps({"type": "FeatureCollection", "features": [point]}).encode()
        with self.assertRaises(ValueError): prepare_vector(payload("point.geojson", data))
        result = prepare_vector(payload("point.geojson", data, source_crs="EPSG:3857"))
        x, y = result["collection"]["features"][0]["geometry"]["coordinates"]
        self.assertAlmostEqual(x, 1, places=7); self.assertAlmostEqual(y, 1, places=7)
        self.assertFalse(result["publication_authorized"])
    def test_geopackage_round_trip_preserves_polygon_hole_and_attributes(self):
        source = layer(); source["features"] = [feature({"type":"Polygon", "coordinates":[[[0,0],[2,0],[2,2],[0,2],[0,0]],[[.5,.5],[1,.5],[1,1],[.5,1],[.5,.5]]]})]
        exported = export_gpkg(source)
        result = prepare_vector({"filename": "roundtrip.gpkg", "content_base64": exported["content_base64"]})
        f = result["collection"]["features"][0]
        self.assertEqual(f["properties"]["name"], "Example"); self.assertEqual(len(f["geometry"]["coordinates"]), 2)
        self.assertEqual(result["source_crs"], "EPSG:4326")
    def test_invalid_topology_needs_explicit_repair_and_never_discards_parts(self):
        crossed = feature({"type":"Polygon", "coordinates":[[[0,0],[2,2],[0,2],[2,0],[0,0]]]})
        p = payload("crossed.geojson", json.dumps(crossed).encode(), source_crs="EPSG:4326")
        with self.assertRaises(ValueError): prepare_vector(p)
        repaired = prepare_vector({**p, "repair": True})
        self.assertEqual(repaired["collection"]["features"][0]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(len(repaired["collection"]["features"][0]["geometry"]["coordinates"]), 2)
    def test_shapefile_zip_and_gpx_kmz_conversion(self):
        import geopandas as gpd
        import pyogrio
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "points.shp"
            pyogrio.write_dataframe(gpd.GeoDataFrame.from_features([feature()], crs="EPSG:4326"), path, driver="ESRI Shapefile")
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as z:
                for item in Path(directory).iterdir(): z.write(item, item.name)
            result = prepare_vector(payload("points.zip", archive.getvalue()))
            self.assertEqual(result["collection"]["features"][0]["geometry"]["coordinates"], [-71.4,41.8])
        gpx = b'<gpx><wpt lon="1" lat="2"><name>GPS test</name></wpt></gpx>'
        self.assertEqual(prepare_vector(payload("point.gpx",gpx))["collection"]["features"][0]["geometry"]["coordinates"], [1,2])
        kmz = io.BytesIO()
        with zipfile.ZipFile(kmz, "w") as z: z.writestr("doc.kml", '<kml><Placemark><name>KML test</name><Point><coordinates>1,2</coordinates></Point></Placemark></kml>')
        self.assertEqual(prepare_vector(payload("point.kmz",kmz.getvalue()))["collection"]["features"][0]["properties"]["name"], "KML test")
    def test_unclosed_geojson_and_oversized_csv_do_not_get_silently_fixed(self):
        unclosed = feature({"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1]]]})
        p = payload("open.geojson", json.dumps(unclosed).encode(), source_crs="EPSG:4326")
        with self.assertRaises(ValueError): prepare_vector(p)
        fixed = prepare_vector({**p, "repair": True})
        self.assertEqual(len(fixed["collection"]["features"][0]["geometry"]["coordinates"][0]), 4)
        self.assertIn("Explicitly closed 1 polygon rings.", fixed["diagnostics"])
        csv = b"name,lon,lat\n" + b"invalid,bad,unknown\n" * 2001
        with self.assertRaises(ValueError): prepare_vector(payload("large.csv",csv,source_crs="EPSG:4326",drop_invalid=True))

    def test_unsafe_archives_xml_and_empty_subset_are_rejected(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z: z.writestr("../outside.kml", "<kml/>")
        with self.assertRaises(ValueError): prepare_vector(payload("unsafe.kmz",archive.getvalue()))
        with self.assertRaises(ValueError): prepare_vector(payload("entity.gpx",b'<!DOCTYPE a [<!ENTITY x "text">]><gpx/>'))
        with self.assertRaises(ValueError): prepare_vector(payload("empty.csv",b"lon,lat\nbad,unknown\n",source_crs="EPSG:4326",drop_invalid=True))
        with self.assertRaises(ValueError): prepare_vector(payload("invalid.csv",b"lon,lat\nbad,unknown\n",source_crs="EPSG:4326"))

if __name__ == "__main__": unittest.main()
