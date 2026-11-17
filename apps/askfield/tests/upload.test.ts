import { test } from "node:test";
import assert from "node:assert/strict";
import { MAX_POINTS, parseUpload } from "../src/lib/askfield/upload.js";

const feature = (coordinates: unknown, properties: unknown = {}) => ({ type: "Feature", geometry: { type: "Point", coordinates }, properties });
const read = (features: unknown[]) => parseUpload(JSON.stringify({ type: "FeatureCollection", features }), "points.geojson");

test("CSV drops missing, nonfinite, projected, and out-of-range coordinates; zero remains valid", () => {
  const result = parseUpload("name,lat,lon\nzero,0,0\nblank,,\npartial,41,\nnull,null,-71\ninf,Infinity,-71\nprojected,900000,500000\nbounds,91,-71\nvalid,41.82,-71.42", "demo.csv");
  assert.deepEqual(result.points.map((p) => p.name), ["zero", "valid"]);
  assert.match(result.diagnostics.at(-1)!.text, /Dropped 6/);
});

test("CSV supports BOM, CRLF, quoted commas, escaped quotes, and embedded newlines", () => {
  const result = parseUpload('\uFEFFname,latitude,longitude\r\n"Demo, ""A""\nSite",41.82,-71.42\r\n', "demo.csv");
  assert.equal(result.points.length, 1);
  assert.equal(result.points[0].name, 'Demo, "A"\nSite');
});

test("ambiguous headers, malformed quoting, and short rows fail without a crash", () => {
  for (const text of ['name,lat,latitude,lon\nA,1,1,2', 'lat,lon,lon\n1,2,2', 'name,lat,lon\n"A,1,2', 'name,lat,lon\nA"B,1,2', 'name,lat,lon\nA,1']) assert.equal(parseUpload(text, "demo.csv").points.length, 0, text);
});

test("GeoJSON safely handles null and malformed structures", () => {
  for (const root of ["null", "[]", "42", '{"type":"FeatureCollection","features":[null,1,{},[]]}', '{"type":"Feature","geometry":null}', '{"type":"Feature","geometry":{"type":"Point","coordinates":[null,0]}}']) assert.equal(parseUpload(root, "points.geojson").points.length, 0, root);
  assert.equal(read([feature(["1", "2"]), feature([true, false]), feature([1, 2], [])]).points.length, 0);
});

test("GeoJSON rejects legacy CRSs and nonpoint geometry instead of inventing a centroid", () => {
  assert.equal(parseUpload(JSON.stringify({ type: "FeatureCollection", crs: { name: "EPSG:3857" }, features: [feature([1, 2])] }), "p.geojson").points.length, 0);
  const result = read([{ type: "Feature", geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [0, 0]]] } }, feature([1, 2])]);
  assert.equal(result.points.length, 1);
  assert.match(result.diagnostics.at(-1)!.text, /non-Point geometry/);
});

test("point limit and byte limit are enforced with explicit diagnostics", () => {
  const text = "name,lat,lon\n" + Array.from({ length: MAX_POINTS + 2 }, (_, i) => `Point ${i},41,-71`).join("\n");
  const result = parseUpload(text, "many.csv");
  assert.equal(result.points.length, MAX_POINTS);
  assert.match(result.diagnostics.at(-1)!.text, /2,000 valid points/);
  assert.equal(parseUpload("x".repeat(2_000_001), "large.csv").points.length, 0);
  assert.equal(parseUpload("é".repeat(1_000_001), "large.csv").points.length, 0);
});

test("untrusted properties do not mutate prototypes and are kept local", () => {
  const raw = '{"type":"Feature","geometry":{"type":"Point","coordinates":[1,2]},"properties":{"name":"Demo","__proto__":"safe","volume":3}}';
  const result = parseUpload(raw, "demo.geojson");
  assert.equal(result.points.length, 1);
  assert.equal(Object.getPrototypeOf(result.points[0].props), null);
  assert.equal(result.points[0].props.__proto__, "safe");
});
