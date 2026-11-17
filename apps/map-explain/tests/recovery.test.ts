import assert from "node:assert/strict";
import test, { beforeEach } from "node:test";
import { IDBFactory, IDBObjectStore } from "fake-indexeddb";
import {
  change,
  clone,
  demoState,
  MAX_BYTES,
  validateProject,
  type LocalState,
} from "../src/lib/observatory/model.js";
import {
  archiveProject,
  MAX_RECOVERY_BYTES,
  readRecoveryCopies,
  recoveredProject,
} from "../src/lib/observatory/recovery.js";
import {
  clearLocal,
  loadLocal,
  loadRecoveryCopies,
  LocalConflict,
  saveLocal,
} from "../src/lib/observatory/store.js";

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
});

function replacement(previous: LocalState, name: string): LocalState {
  const next = demoState();
  next.project.name = name;
  next.revision = previous.revision + 1;
  return next;
}

test("recovery copies keep immutable replaced documents and prune the oldest after three", () => {
  const project = demoState().project;
  let copies = archiveProject(project, "Before replacement", undefined);
  const original = clone(copies[0].project);
  for (let i = 1; i <= 3; i++) {
    project.name = `Replacement ${i}`;
    copies = archiveProject(project, "Before replacement", copies);
  }
  assert.equal(copies.length, 3);
  assert.deepEqual(
    copies.map((c) => c.project.name),
    ["Replacement 3", "Replacement 2", "Replacement 1"],
  );
  project.layers[0].features[0].properties.name = "Later unsaved mutation";
  assert.deepEqual(copies[0].project.layers, original.layers);
});

test("recovery copies enforce the UTF-8 byte budget while retaining the newest large project", () => {
  const project = demoState().project;
  project.layers[0].features[0].properties.description = "界".repeat(2_100_000);
  const first = archiveProject(project, "First large copy", undefined);
  project.name = "Newest large project";
  const copies = archiveProject(project, "Second large copy", first);
  assert.equal(copies.length, 1);
  assert.equal(copies[0].project.name, "Newest large project");
  assert.ok(
    new TextEncoder().encode(JSON.stringify(copies)).byteLength <=
      MAX_RECOVERY_BYTES,
  );
  assert.equal(
    copies[0].project.layers[0].features[0].properties.description,
    "界".repeat(2_100_000),
  );
});

test("recovery forks a fresh project identity and preserves source data and blocked publication", () => {
  const original = demoState().project;
  original.layers[0].features[0].properties.photo_jpeg =
    "data:image/jpeg;base64,/9j/2Q==";
  const copy = archiveProject(original, "Before replacing", undefined)[0];
  const recovered = recoveredProject(copy);
  assert.notEqual(recovered.id, original.id);
  assert.deepEqual(recovered.layers, original.layers);
  assert.equal(recovered.publication_authorized, false);
  assert.match(recovered.history.at(-1)!.summary, /Recovered local copy/);
  recovered.layers[0].name = "Changed after recovery";
  assert.deepEqual(copy.project, original);
});

test("a project at the 8 MB ceiling remains recoverable without dropping feature data", () => {
  const project = demoState().project;
  const properties = project.layers[0].features[0].properties;
  properties.padding = "";
  properties.padding = "x".repeat(
    MAX_BYTES - new TextEncoder().encode(JSON.stringify(project)).byteLength,
  );
  validateProject(project);
  const recovered = recoveredProject(
    archiveProject(project, "At limit", undefined)[0],
  );
  validateProject(recovered);
  assert.notEqual(recovered.id, project.id);
  assert.deepEqual(recovered.layers, project.layers);
});

test("invalid recovery metadata and publication claims are rejected", () => {
  const copies = archiveProject(
    demoState().project,
    "Before replacing",
    undefined,
  );
  assert.throws(() => readRecoveryCopies({ copies }));
  assert.throws(() => readRecoveryCopies([...copies, ...copies]));
  const badDate = clone(copies);
  badDate[0].savedAt = "not a date";
  assert.throws(() => readRecoveryCopies(badDate));
  const badRights: unknown = copies.map((c) => ({
    ...c,
    project: { ...c.project, publication_authorized: true },
  }));
  assert.throws(() => readRecoveryCopies(badRights));
});

test("a full project with a short ID remains exportable when a fresh ID cannot fit", () => {
  const project = demoState().project;
  project.id = "p";
  const properties = project.layers[0].features[0].properties;
  properties.padding = "";
  properties.padding = "x".repeat(
    MAX_BYTES - new TextEncoder().encode(JSON.stringify(project)).byteLength,
  );
  const copy = archiveProject(project, "At limit with short ID", undefined)[0];
  assert.throws(() => recoveredProject(copy), /Export this recovery copy/);
  validateProject(copy.project);
  assert.deepEqual(copy.project, project);
});

test("ordinary local saves preserve state without archiving every edit", async () => {
  const initial = demoState();
  await saveLocal(initial, null);
  const edited = change(initial, "Renamed", (p) => {
    p.name = "Local edit";
  });
  assert.equal(await saveLocal(edited, initial.revision), null);
  assert.deepEqual(await loadLocal(), edited);
  assert.deepEqual(await loadRecoveryCopies(), []);
});

test("replacing a project atomically retains its previous document across reads", async () => {
  const initial = demoState();
  await saveLocal(initial, null);
  const next = replacement(initial, "Incoming project");
  const copies = await saveLocal(next, initial.revision, {
    archiveReason: "Before opening another project",
  });
  assert.equal(copies!.length, 1);
  assert.deepEqual(copies![0].project, initial.project);
  assert.deepEqual(await loadRecoveryCopies(), copies);
  assert.deepEqual(await loadLocal(), next);
});

test("two concurrent replacements accept one revision without archiving a stale document", async () => {
  const initial = demoState();
  await saveLocal(initial, null);
  const results = await Promise.allSettled([
    saveLocal(replacement(initial, "First"), initial.revision, {
      archiveReason: "First tab",
    }),
    saveLocal(replacement(initial, "Second"), initial.revision, {
      archiveReason: "Second tab",
    }),
  ]);
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
  const failure = results.find((r) => r.status === "rejected");
  assert.ok(
    failure?.status === "rejected" && failure.reason instanceof LocalConflict,
  );
  const copies = await loadRecoveryCopies();
  assert.equal(copies.length, 1);
  assert.deepEqual(copies[0].project, initial.project);
  assert.equal((await loadLocal())!.revision, initial.revision + 1);
});

test("a failed replacement rolls back the recovery copy and active document together", async (t) => {
  const initial = demoState();
  await saveLocal(initial, null);
  const before = replacement(initial, "Current project");
  await saveLocal(before, initial.revision, {
    archiveReason: "First replacement",
  });
  const copies = await loadRecoveryCopies();
  const put = IDBObjectStore.prototype.put;
  t.mock.method(
    IDBObjectStore.prototype,
    "put",
    function (this: IDBObjectStore, value: unknown, key?: IDBValidKey) {
      if (key === "active")
        throw new DOMException(
          "Simulated storage exhaustion",
          "QuotaExceededError",
        );
      return put.call(this, value, key);
    },
  );
  await assert.rejects(
    saveLocal(replacement(before, "Must not replace"), before.revision, {
      archiveReason: "Failed replacement",
    }),
    { name: "QuotaExceededError" },
  );
  assert.deepEqual(await loadLocal(), before);
  assert.deepEqual(await loadRecoveryCopies(), copies);
  await assert.rejects(
    saveLocal({ ...before, revision: before.revision + 1 }, before.revision, {
      clearRecovery: true,
    }),
    { name: "QuotaExceededError" },
  );
  assert.deepEqual(await loadLocal(), before);
  assert.deepEqual(await loadRecoveryCopies(), copies);
});

test("recovery deletion observes the revision guard and keeps the active project", async () => {
  const initial = demoState();
  await saveLocal(initial, null);
  const current = replacement(initial, "Keep this project");
  await saveLocal(current, initial.revision, {
    archiveReason: "Before replacing",
  });
  await assert.rejects(
    saveLocal(
      { ...current, revision: current.revision + 1 },
      initial.revision,
      { clearRecovery: true },
    ),
    LocalConflict,
  );
  assert.equal((await loadRecoveryCopies()).length, 1);
  const purged = { ...current, revision: current.revision + 1 };
  assert.deepEqual(
    await saveLocal(purged, current.revision, { clearRecovery: true }),
    [],
  );
  assert.deepEqual(await loadRecoveryCopies(), []);
  assert.deepEqual((await loadLocal())!.project, current.project);
});

test("clearing local storage removes recovery copies as well as the active document", async () => {
  const initial = demoState();
  await saveLocal(initial, null);
  await saveLocal(replacement(initial, "Replacement"), initial.revision, {
    archiveReason: "Before clearing",
  });
  await clearLocal();
  assert.equal(await loadLocal(), null);
  assert.deepEqual(await loadRecoveryCopies(), []);
});
