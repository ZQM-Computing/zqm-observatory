import { test } from "node:test";
import assert from "node:assert/strict";
import { clinics, customers, neighborhoods } from "../src/lib/askfield/data.js";
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

test("threshold exports retain every matching uploaded point", () => {
  const upload = Array.from({ length: 20 }, (_, i) => ({
    id: `upload-${i}`, name: `Site ${i}`, lon: clinics[0].lon, lat: clinics[0].lat, props: {},
  }));
  for (const [question, expected] of [
    ["Show my points within 1 km of clinics", 20],
    ["Show my points more than 1 km from clinics", 0],
  ] as const) {
    const result = tryAnswer(question, { upload })!;
    assert.equal(result.rows.length, expected);
    const ids = result.rows.map((r) => r.id).sort();
    assert.deepEqual(JSON.parse(resultGeoJSON(result, question)).features.map((f: { id: string }) => f.id).sort(), ids);
    const csv = resultCSV(result, question);
    for (const point of upload) assert.equal(csv.includes(`${point.id},`), expected > 0);
  }
});

test("explicit small percentages use percent units while bare fractions remain fractions", () => {
  for (const marker of ["%", " percent"]) {
    for (const value of [0, 0.5, 1, 20]) {
      const q = `Which neighborhoods have a share of children under ${value}${marker}?`;
      assert.deepEqual(interpret(q), { kind: "neighborhoods_where", field: "shareChildren", op: "lt", value: value / 100 });
      assert.equal(tryAnswer(q, { upload: [] })!.rows.length, neighborhoods.filter((n) => n.shareChildren < value / 100).length);
    }
  }
  assert.deepEqual(interpret("Which neighborhoods have a share of children under 0.5?"), { kind: "neighborhoods_where", field: "shareChildren", op: "lt", value: 0.5 });
  assert.equal(tryAnswer("Which neighborhoods have broadband under 1%?", { upload: [] })!.rows.length, 0);
});

test("nearest and farthest rankings preserve subject and target roles", () => {
  for (const [word, dir] of [["nearest to", "asc"], ["closest to", "asc"], ["farthest from", "desc"], ["furthest from", "desc"]] as const) {
    for (const [subject, target] of [["customers", "parks"], ["parks", "customers"], ["warehouse", "customers"], ["clinics", "upload"]] as const) {
      const noun = (kind: string) => kind === "upload" ? "my points" : kind;
      assert.deepEqual(interpret(`Show ${noun(subject)} ${word} ${noun(target)}`), { kind: "distance_rank", subject, target, dir });
    }
  }
  assert.equal(interpret("Show nearest parks customers"), null);
  const result = tryAnswer("Show customers nearest to parks", { upload: [] })!;
  assert.ok(result.rows.every((row) => customers.some((c) => c.id === row.id)));
});

test("neighborhood distance thresholds decline instead of returning unfiltered ranks", () => {
  for (const meters of ["1", "100"]) {
    for (const relation of ["more than", "within", "less than"]) {
      assert.equal(interpret(`Show neighborhoods ${relation} ${meters} km from clinics`), null);
    }
  }
  assert.deepEqual(interpret("Show neighborhoods nearest to clinics"), { kind: "zone_distance", target: "clinics", dir: "asc" });
});

test("overlapping zone counts do not hide unmatched uploaded points", () => {
  const overlap = { id: "upload-overlap", name: "Overlap", lon: -71.4205, lat: 41.8225, props: {} };
  const outside = { id: "upload-outside", name: "Outside", lon: 0, lat: 0, props: {} };
  const zones = neighborhoods.filter((n) => pointInRing([overlap.lon, overlap.lat], n.ring));
  assert.ok(zones.length >= 2);
  const result = tryAnswer("Count my points by neighborhood", { upload: [overlap, outside] })!;
  assert.match(result.summary, /1 fall outside every neighborhood outline/);
  for (const zone of zones) assert.equal(result.rows.find((r) => r.id === zone.id)!.primary, "1");
  assert.match(tryAnswer("Count my points by neighborhood", { upload: [overlap] })!.summary, /Every point falls inside/);
});

test("location guards validate complete phrases and preserve supported locations", () => {
  for (const q of ["Show clinics in Downtown Boston", "Show clinics near Boston", "Show clinics in Providence Boston", "Show clinics in Downtown near Boston", "Show clinics near Downtown Boston"]) {
    assert.equal(interpret(q), null, q);
  }
  for (const q of ["Show clinics in Downtown", "Show clinics in Providence", "Show clinics near the warehouse", "Show customers within 1 km of clinics"]) {
    assert.ok(interpret(q), q);
  }
});

test("park gaps export only matches, including empty results", () => {
  for (const radiusM of [50, 800, 100000]) {
    const result = run({ kind: "park_child_gap", radiusM }, { upload: [] });
    if (radiusM === 100000) assert.equal(result.rows.length, 0);
    assert.equal(JSON.parse(resultGeoJSON(result, "Park gaps")).features.length, result.rows.length);
  }
});

test("polygon exports retain all matching uploaded points", () => {
  const zone = neighborhoods.find((n) => pointInRing([-71.4205, 41.8225], n.ring))!;
  const upload = Array.from({ length: 20 }, (_, i) => ({ id: `upload-${i}`, name: `Point ${i}`, lon: -71.4205, lat: 41.8225, props: {} }));
  const result = run({ kind: "points_in_zone", subject: "upload", zoneId: zone.id }, { upload });
  assert.equal(result.rows.length, 20);
  assert.equal(JSON.parse(resultGeoJSON(result, "Points in zone")).features.length, 20);
  for (const point of upload) assert.ok(resultCSV(result, "Points in zone").includes(`${point.id},`));
});

test("meter abbreviations and invalid distances retain threshold semantics", () => {
  assert.deepEqual(interpret("Show customers within 500 m of the warehouse"), { kind: "customers_near_warehouse", meters: 500, note: null });
  for (const unit of ["m", "km", "meters", "mi"]) {
    for (const amount of ["0", "-1", "0.001"]) assert.equal(interpret(`Show customers within ${amount} ${unit} of the warehouse`), null);
  }
  assert.equal(interpret("Clinics at most 500 m from the warehouse"), null);
});

test("population threshold prefixes do not become age tokens", () => {
  assert.deepEqual(interpret("Which neighborhoods have population over 6500?"), { kind: "neighborhoods_where", field: "pop", op: "gt", value: 6500 });
  assert.equal(tryAnswer("Which neighborhoods have population over 6500?", { upload: [] })!.rows.length, neighborhoods.filter((n) => n.pop > 6500).length);
  assert.deepEqual(interpret("Rank neighborhoods by residents over 65"), { kind: "rank_neighborhoods", field: "pop65", dir: "desc" });
});

test("senior proximity requests decline instead of reversing the comparison", () => {
  for (const relation of ["within", "less than", "closer than"]) assert.equal(interpret(`Which neighborhoods have the highest senior share ${relation} 1 km of the nearest clinic?`), null);
  assert.equal(interpret(EXAMPLES[0].question)!.kind, "senior_clinic_gap");
});

test("terminal punctuation preserves locations and decimal distances", () => {
  assert.deepEqual(interpret("Show clinics in Downtown."), interpret("Show clinics in Downtown"));
  assert.ok(interpret("Show clinics in Downtown."));
  assert.equal(interpret("Show clinics in Downtown Boston."), null);
  assert.deepEqual(interpret("Show customers within 1.5 km of the warehouse."), { kind: "customers_near_warehouse", meters: 1500, note: null });
});

test("near neighborhoods rank closest first", () => {
  assert.deepEqual(interpret("Show neighborhoods near the warehouse"), { kind: "zone_distance", target: "warehouse", dir: "asc" });
  assert.deepEqual(tryAnswer("Show neighborhoods near the warehouse", { upload: [] }), tryAnswer("Show neighborhoods nearest to the warehouse", { upload: [] }));
});
