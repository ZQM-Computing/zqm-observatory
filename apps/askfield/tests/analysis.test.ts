import { test } from "node:test";
import assert from "node:assert/strict";
import { EXAMPLES, interpret } from "../src/lib/askfield/intent.js";
import { run, tryAnswer, type UploadPoint } from "../src/lib/askfield/engine.js";
import { distanceMeters, pointInRing } from "../src/lib/askfield/geo.js";
import { resultCSV, resultGeoJSON, resultSummary, csvCell } from "../src/lib/askfield/export.js";

test("geodesic distance has known equatorial scale and is symmetric", () => {
  assert.equal(distanceMeters([0, 0], [0, 0]), 0);
  assert.ok(Math.abs(distanceMeters([0, 0], [1, 0]) - 111195.08) < 0.1);
  assert.equal(distanceMeters([-71, 42], [-72, 43]), distanceMeters([-72, 43], [-71, 42]));
  assert.ok(Math.abs(distanceMeters([179.9, 0], [-179.9, 0]) - 22239.016) < 0.1);
});

test("point-in-ring includes interior and excludes exterior", () => {
  const ring: [number, number][] = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]];
  assert.equal(pointInRing([1, 1], ring), true);
  assert.equal(pointInRing([3, 1], ring), false);
});

test("all visible examples run deterministically with coherent map/list IDs", () => {
  for (const example of EXAMPLES) {
    const a = tryAnswer(example.question, { upload: [] });
    assert.ok(a, example.question);
    assert.deepEqual(a, tryAnswer(example.question, { upload: [] }));
    const ids = new Set([...a.points, ...a.neighborhoods].map((p) => p.id));
    assert.ok(a.rows.every((row) => ids.has(row.id)));
    assert.ok(a.rows.every((row) => Number.isFinite(row.bar) && row.bar >= 0 && row.bar <= 1));
    assert.ok(a.steps.length && a.sources.length);
  }
});

test("decimal and comma-separated thresholds retain their actual values", () => {
  assert.deepEqual(interpret("Show customers within 1.5 km of the warehouse and color them by order volume."), { kind: "customers_near_warehouse", meters: 1500, note: null });
  assert.deepEqual(interpret("Show customers within 0.5 miles of the warehouse"), { kind: "customers_near_warehouse", meters: 804.672, note: null });
  assert.deepEqual(interpret("Which neighborhoods have income under 50,000?"), { kind: "neighborhoods_where", field: "medianIncome", op: "lt", value: 50000 });
  assert.equal(tryAnswer("Which neighborhoods have broadband under 80%?", { upload: [] })?.rows.length, 5);
});

test("inclusive attribute thresholds and beyond-distance semantics are respected", () => {
  assert.equal(tryAnswer("Which neighborhoods have broadband at most 80%?", { upload: [] })?.rows.length, 6);
  assert.equal(tryAnswer("Which neighborhoods have broadband at least 80%?", { upload: [] })?.rows.length, 7);
  const inside = tryAnswer("Show customers within 1.5 km of the warehouse", { upload: [] })!;
  const beyond = tryAnswer("Show customers more than 1.5 km from the warehouse", { upload: [] })!;
  assert.equal(inside.rows.length + beyond.rows.length, 28);
  const ids = new Set(inside.rows.map((p) => p.id));
  assert.ok(beyond.rows.every((p) => !ids.has(p.id)));
});

test("unsupported operations, other geographies, compound filters, and out-of-range distances decline", () => {
  for (const q of ["Clinics within 20 minutes of customers", "Show live clinics", "Show clinics in Volusia", "Show clinics in Florida", "Show clinics within 200 km of the warehouse", "Show clinics within -1 km of the warehouse", "Show clinics within 0.001 km of the warehouse", "Which neighborhoods have broadband under 80% and income under 50k?", "Show accessible parks", "Rank neighborhoods by population density", "Show census tracts near clinics", "Clinics at most 1 km from the warehouse"]) {
    assert.equal(interpret(q), null, q);
  }
});

test("replacing uploaded coordinates changes the query identity and computed output", () => {
  const intent = { kind: "upload_near" as const, target: "clinics" as const, mode: "within" as const, meters: 1000, note: null };
  const point: UploadPoint = { id: "upload-1", name: "Demo", lon: -71.427, lat: 41.822, props: {} };
  const a = run(intent, { upload: [point] });
  const b = run(intent, { upload: [{ ...point, lon: 0, lat: 0 }] });
  assert.equal(a.rows.length, 1);
  assert.equal(b.rows.length, 0);
  assert.notEqual(a.queryId, b.queryId);
  assert.equal(run(intent, { upload: [] }).rows.length, 0);
});

test("exports preserve IDs, question, method, limitations, and blocked publication", () => {
  const q = "Show customers within 1.5 km of the warehouse";
  const result = tryAnswer(q, { upload: [] })!;
  const exported = JSON.parse(resultGeoJSON(result, q));
  assert.equal(exported.zqm_observatory.publication_authorized, false);
  assert.equal(exported.zqm_observatory.question, q);
  assert.deepEqual(exported.zqm_observatory.method, result.steps);
  assert.deepEqual(exported.features.map((f: { id: string }) => f.id).sort(), result.rows.map((r) => r.id).sort());
  assert.ok(exported.features.every((f: { properties: { publication_authorized: boolean } }) => f.properties.publication_authorized === false));
  assert.match(resultCSV(result, q), /unverified_demo,false/);
  assert.match(resultSummary(result, q), /Publication is not authorized/);
});

test("spreadsheet formula payloads and embedded CSV quotes are escaped", () => {
  for (const input of ["=HYPERLINK(1)", "+1", "-1", "@SUM(1)", " \t=1", "\tcommand", "\r=1"]) assert.ok(csvCell(input).includes("'"), input);
  assert.equal(csvCell('Name, "A"'), '"Name, ""A"""');
  assert.equal(csvCell("ordinary"), "ordinary");
});

test("show operations list every requested feature and label uploaded provenance", () => {
  const sample = run({ kind: "show", layers: ["customers", "warehouse"] }, { upload: [] });
  assert.equal(sample.rows.length, 29);
  assert.equal(new Set(sample.rows.map((r) => r.id)).size, 29);
  const zones = run({ kind: "show", layers: ["neighborhoods"] }, { upload: [] });
  assert.equal(zones.rows.length, 12);
  assert.ok(zones.rows.every((row) => zones.neighborhoods.some((n) => n.id === row.id)));
  const upload = [{ id: "upload-1", name: "Synthetic site", lon: 1, lat: 2, props: {} }];
  const result = run({ kind: "show", layers: ["upload"] }, { upload });
  assert.equal(result.rows.length, 1);
  assert.match(result.title, /unverified/);
  assert.ok(result.sources.some((s) => s.name === "User-supplied points"));
  assert.ok(result.legend.some((s) => s.label === "Unverified uploaded point"));
  assert.equal(JSON.parse(resultGeoJSON(result, "Show my points")).features[0].properties.source_class, "user_supplied_unverified");
});
