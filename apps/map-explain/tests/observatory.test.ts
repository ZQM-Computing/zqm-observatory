import assert from "node:assert/strict";
import test from "node:test";
import {
  acknowledge,
  change,
  clone,
  demoState,
  geometryErrors,
  makeLayer,
  validateProject,
  type Feature,
} from "../src/lib/observatory/model.js";
import { answerProject, coverage } from "../src/lib/observatory/analysis.js";
import {
  DEFAULT_PREP,
  prepare,
  reprojectGeometry,
} from "../src/lib/observatory/prep.js";
import { mergeProjects } from "../src/lib/observatory/merge.js";
import { layerCSV, projectBundle } from "../src/lib/observatory/export.js";
const point = (id: string, x: number, y: number, demand = 1): Feature => ({
  type: "Feature",
  id,
  geometry: { type: "Point", coordinates: [x, y] },
  properties: { name: id, demand },
});
const demand = makeLayer("Demand [A]", [
  point("here", 0, 0, 1),
  point("far", 0.02, 0, 10),
]);
const supply = makeLayer("Supply", [point("site", 0, 0)]);

test("coverage keeps every demand point, reports a real distance and reproducible weighted score", () => {
  const result = coverage(demand, supply, 1000, "demand", 1, 1);
  assert.equal(result.layer.features.length, 2);
  const far = result.layer.features.find((f) => f.id === "far")!;
  assert.ok(Math.abs(Number(far.properties.nearest_m) - 2223.9) < 1);
  assert.equal(far.properties.gap, true);
  assert.ok(Math.abs(Number(far.properties.score) - 87.065) < 0.1);
  assert.equal(
    result.layer.features.find((f) => f.id === "here")!.properties.score,
    0,
  );
  assert.throws(() => coverage(demand, supply, -1, "", 1, 1));
  assert.throws(() => coverage(demand, supply, 1000, "absent", 1, 1));
  assert.throws(() => coverage(demand, supply, 1000, "", 0, 0));
});

test("strict questions escape layer names and reject compound constraints instead of dropping them", () => {
  const layers = [demand, supply];
  assert.equal(
    answerProject("Show Demand [A] beyond 1000 m of Supply", layers).rows
      .length,
    1,
  );
  assert.equal(
    answerProject("Rank Demand [A] nearest to Supply", layers).rows[0].id,
    "here",
  );
  for (const q of [
    "Show Demand [A] within -10 m of Supply",
    "Show Demand [A] within 1 km of Supply and only urgent",
    "Rank Demand [A] nearest to Supply in Boston",
    "Count Demand [A] in Supply",
    "Drive to Supply",
  ])
    assert.throws(() => answerProject(q, layers));
  const derived = makeLayer("Demand [A] coverage", [point("copy", 1, 1)]);
  assert.equal(
    answerProject("Show Demand [A] coverage", [...layers, derived]).layer.id,
    derived.id,
  );
});

test("polygon count excludes a point in a hole and retains the polygon geometry", () => {
  const zones = makeLayer("Zones", [
    {
      type: "Feature",
      id: "zone",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-1, -1],
            [1, -1],
            [1, 1],
            [-1, 1],
            [-1, -1],
          ],
          [
            [-0.1, -0.1],
            [0.1, -0.1],
            [0.1, 0.1],
            [-0.1, 0.1],
            [-0.1, -0.1],
          ],
        ],
      },
    },
  ]);
  const result = answerProject("Count People in Zones", [
    makeLayer("People", [
      point("hole", 0, 0),
      point("inside", 0.5, 0.5),
      point("outside", 2, 2),
    ]),
    zones,
  ]);
  assert.equal(result.rows[0].value, 1);
  assert.deepEqual(
    result.layer.features[0].geometry,
    zones.features[0].geometry,
  );
});

test("prep transforms known Web Mercator coordinates and records explicit fixes", () => {
  const transformed = reprojectGeometry(
    { type: "Point", coordinates: [111319.49079327357, 111325.1428663851] },
    "EPSG:3857",
  );
  const [x, y] = transformed.coordinates as number[];
  assert.ok(Math.abs(x - 1) < 1e-9 && Math.abs(y - 1) < 1e-9);
  const source = JSON.stringify({
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { "Site Name": "Test", empty: null },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [0, 0],
              [1, 0],
              [1, 1],
            ],
          ],
        },
      },
    ],
  });
  assert.equal(prepare(source, "open.geojson").layer, null);
  const result = prepare(source, "open.geojson", {
    ...DEFAULT_PREP,
    closeRings: true,
    dropEmpty: true,
  });
  assert.equal(result.layer?.features[0].properties.site_name, "Test");
  assert.equal(
    Object.hasOwn(result.layer!.features[0].properties, "empty"),
    false,
  );
  assert.equal(geometryErrors(result.layer!.features[0].geometry).length, 0);
  assert.match(result.layer!.steps[0].detail, /close rings=true/);
});

test("prep does not silently keep valid subsets or normalized field collisions", () => {
  const text = JSON.stringify({
    type: "FeatureCollection",
    features: [point("valid", 0, 0), point("bad", 200, 0)],
  });
  assert.equal(prepare(text, "input.geojson").layer, null);
  const accepted = prepare(text, "input.geojson", {
    ...DEFAULT_PREP,
    dropInvalid: true,
  });
  assert.equal(accepted.layer?.features.length, 1);
  assert.equal(accepted.rejected, 1);
  const collision = point("collision", 0, 0);
  collision.properties = { "Site Name": "a", site_name: "b" };
  assert.equal(
    prepare(JSON.stringify(collision), "collision.geojson").layer,
    null,
  );
  assert.throws(() =>
    reprojectGeometry({ type: "Point", coordinates: [0, 0] }, "EPSG:27700"),
  );
});

test("shared project validation bounds geometry, source rights, duplicate layer names, and form configuration", () => {
  const doc = demoState().project;
  validateProject(doc);
  const bad = clone(doc);
  bad.layers.push({ ...clone(bad.layers[0]), id: "different" });
  assert.throws(() => validateProject(bad));
  const badRights = clone(doc);
  (badRights.layers[0].source as { rights: string }).rights = "approved";
  assert.throws(() => validateProject(badRights));
  assert.deepEqual(geometryErrors({ type: "Point", coordinates: [NaN, 1] }), [
    "Invalid, unclosed, nonfinite, or out-of-range geometry coordinates.",
  ]);
  const badForm = clone(doc);
  badForm.fieldForm = { extraLabel: "", extraRequired: true };
  assert.throws(() => validateProject(badForm));
  const roundTrip: unknown = JSON.parse(projectBundle(doc));
  validateProject(roundTrip);
});

test("three-way merge keeps independent feature edits and makes same-value conflicts explicit", () => {
  const base = demoState().project,
    local = clone(base),
    remote = clone(base);
  local.layers[0].features[0].properties.local_note = "local";
  remote.layers[0].features[1].properties.shared_note = "remote";
  const combined = mergeProjects(base, local, remote);
  assert.equal(combined.conflicts.length, 0);
  assert.equal(
    combined.project.layers[0].features.find(
      (f) => f.id === local.layers[0].features[0].id,
    )?.properties.local_note,
    "local",
  );
  assert.equal(
    combined.project.layers[0].features.find(
      (f) => f.id === remote.layers[0].features[1].id,
    )?.properties.shared_note,
    "remote",
  );
  local.name = "Local name";
  remote.name = "Shared name";
  const conflict = mergeProjects(base, local, remote);
  assert.equal(conflict.conflicts.length, 1);
  assert.equal(conflict.conflicts[0].path, "project/name");
  const resolved = mergeProjects(base, local, remote, {
    "project/name": "remote",
  });
  assert.equal(resolved.project.name, "Shared name");
  assert.equal(resolved.conflicts.length, 0);
});

test("merge handles deletion against edits and treats geometry arrays atomically", () => {
  const base = demoState().project,
    local = clone(base),
    remote = clone(base);
  const deleted = local.layers[0].features.shift()!;
  remote.layers[0].features[0].properties.name = "Remote edit";
  const conflict = mergeProjects(base, local, remote);
  assert.equal(conflict.conflicts.length, 1);
  assert.ok(
    conflict.conflicts[0].path.endsWith(encodeURIComponent(deleted.id)),
  );
  const chosen = mergeProjects(base, local, remote, {
    [conflict.conflicts[0].path]: "remote",
  });
  assert.equal(
    chosen.project.layers[0].features.find((f) => f.id === deleted.id)
      ?.properties.name,
    "Remote edit",
  );
  const a = clone(base),
    b = clone(base);
  a.layers[0].features[0].geometry.coordinates = [1, 2];
  b.layers[0].features[0].geometry.coordinates = [3, 4];
  assert.ok(
    mergeProjects(base, a, b).conflicts[0].path.endsWith("coordinates"),
  );
});

test("server acknowledgement removes only sent operations and retains edits made afterwards", () => {
  const initial = demoState(),
    sent = change(initial, "first", (p) => {
      p.name = "First";
    }),
    later = change(sent, "later", (p) => {
      p.name = "Later";
    });
  const ack = acknowledge(
    later,
    sent.revision,
    sent.outbox.map((o) => o.id),
    1,
    sent.project,
  );
  assert.equal(ack.project.name, "Later");
  assert.equal(ack.base?.name, "First");
  assert.equal(ack.outbox.length, 1);
  assert.equal(ack.outbox[0].summary, "later");
  assert.throws(() =>
    acknowledge({ ...ack, remoteRevision: 2 }, 1, [], 1, sent.project),
  );
});

test("CSV preserves lineage and neutralizes formula-like attribute values", () => {
  const layer = makeLayer("Example", [point("p", 0, 0)]);
  layer.features[0].properties.name = '=HYPERLINK("bad")';
  const csv = layerCSV(layer);
  assert.match(csv, /rights_status,publication_authorized/);
  assert.ok(csv.includes("'=HYPERLINK"));
  assert.ok(csv.endsWith("unreviewed,false"));
});

test("CSV prep preserves selected header spelling, reports rejected rows, and refuses truncation", () => {
  const csv = "Site Name,longitude,latitude\nTest,0,0\nInvalid,,1\n";
  assert.equal(
    prepare(csv, "file.csv", { ...DEFAULT_PREP, normalize: false }).layer,
    null,
  );
  const p = prepare(csv, "file.csv", {
    ...DEFAULT_PREP,
    normalize: false,
    dropInvalid: true,
  });
  assert.equal(p.inputCount, 2);
  assert.equal(p.rejected, 1);
  assert.equal(p.layer?.features[0].properties["Site Name"], "Test");
  assert.throws(() =>
    prepare(
      "name,lon,lat\n" +
        Array.from({ length: 2001 }, (_, i) => `p${i},0,0`).join("\n"),
      "too-many.csv",
      { ...DEFAULT_PREP, dropInvalid: true },
    ),
  );
});

test("restoring a prior document retains the existing audit trail", () => {
  const a = demoState(),
    b = change(a, "First edit", (p) => {
      p.name = "One";
    }),
    c = change(b, "Second edit", (p) => {
      p.name = "Two";
    });
  const restored = change(c, "Restored prior document", (p) =>
    Object.assign(p, clone(b.project)),
  );
  assert.equal(restored.project.name, "One");
  assert.deepEqual(
    restored.project.history.map((h) => h.summary),
    ["First edit", "Second edit", "Restored prior document"],
  );
});
