import assert from "node:assert/strict";
import test, { beforeEach } from "node:test";
import { IDBFactory, IDBObjectStore } from "fake-indexeddb";
import { pull, push, SyncConflict } from "../src/lib/observatory/api.js";
import {
  change,
  clone,
  demoState,
  equalJson,
  type LocalState,
  type Project,
} from "../src/lib/observatory/model.js";
import { mergeProjects } from "../src/lib/observatory/merge.js";
import {
  loadLocal,
  LocalConflict,
  saveLocal,
} from "../src/lib/observatory/store.js";
import {
  prepareSend,
  sendProject,
  validatePendingSend,
} from "../src/lib/observatory/sync.js";
import { projectBundle } from "../src/lib/observatory/export.js";

const TOKEN = "synthetic-client-test-token";
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
function reordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(reordered);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .reverse()
        .map(([k, v]) => [k, reordered(v)]),
    );
  return value;
}
function client(initial: LocalState) {
  let state = clone(initial);
  return {
    read: () => state,
    persist: async (next: LocalState, expected: number) => {
      await saveLocal(next, expected);
      state = next;
    },
  };
}
beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
});

test("an accepted upload with a lost reply survives reload and confirms before later edits", async (t) => {
  const initial = change(demoState(), "First edit", (p) => {
    p.name = "First uploaded snapshot";
  });
  await saveLocal(initial, null);
  let active = client(initial),
    revision = 0;
  const receipts = new Map<string, { revision: number; document: Project }>();
  const bodies: string[] = [];
  t.mock.method(
    globalThis,
    "fetch",
    async (_url: unknown, init: RequestInit) => {
      const raw = String(init.body);
      bodies.push(raw);
      const body = JSON.parse(raw);
      const stored = (await loadLocal())!;
      assert.equal(stored.pendingSend!.operation, body.operation_id);
      assert.deepEqual(stored.pendingSend!.project, body.document);
      let receipt = receipts.get(body.operation_id);
      if (!receipt) {
        assert.equal(body.expected_revision, revision);
        receipt = { revision: ++revision, document: body.document };
        receipts.set(body.operation_id, receipt);
      }
      if (bodies.length === 1)
        throw new TypeError("Synthetic connection lost after commit");
      return response(reordered(receipt));
    },
  );
  await assert.rejects(
    sendProject(active.read, active.persist, TOKEN),
    /connection lost/,
  );
  const persisted = (await loadLocal())!;
  assert.ok(persisted.pendingSend);
  assert.ok(!JSON.stringify(persisted).includes(TOKEN));
  assert.ok(
    !projectBundle(persisted.project).includes(persisted.pendingSend.operation),
  );
  active = client(persisted);
  await active.persist(
    change(active.read(), "Later edit", (p) => {
      p.name = "Newer local work";
    }),
    active.read().revision,
  );
  active = client((await loadLocal())!);
  const confirmed = await sendProject(active.read, active.persist, TOKEN);
  assert.equal(confirmed.kind, "confirmed");
  assert.equal(bodies[1], bodies[0]);
  assert.equal(revision, 1);
  assert.equal(active.read().project.name, "Newer local work");
  assert.equal(active.read().base!.name, "First uploaded snapshot");
  assert.deepEqual(
    active.read().outbox.map((o) => o.summary),
    ["Later edit"],
  );
  assert.equal(active.read().pendingSend, null);
  await sendProject(active.read, active.persist, TOKEN);
  assert.notEqual(
    JSON.parse(bodies[2]).operation_id,
    JSON.parse(bodies[0]).operation_id,
  );
  assert.equal(JSON.parse(bodies[2]).expected_revision, 1);
  assert.equal(active.read().remoteRevision, 2);
  assert.equal(active.read().outbox.length, 0);
});

test("local storage failure prevents a new upload from reaching the network", async (t) => {
  const initial = demoState();
  await saveLocal(initial, null);
  const active = client(initial),
    fetch = t.mock.method(globalThis, "fetch", async () => response({}));
  t.mock.method(IDBObjectStore.prototype, "put", () => {
    throw new DOMException("Synthetic quota failure", "QuotaExceededError");
  });
  await assert.rejects(sendProject(active.read, active.persist, TOKEN), {
    name: "QuotaExceededError",
  });
  assert.equal(fetch.mock.callCount(), 0);
  assert.deepEqual(await loadLocal(), initial);
});

test("a failed local acknowledgement keeps the receipt reusable after reload", async (t) => {
  const initial = change(demoState(), "Saved edit", (p) => {
    p.name = "Keep this edit";
  });
  await saveLocal(initial, null);
  let active = client(initial),
    writes = 0;
  const put = IDBObjectStore.prototype.put,
    operations: string[] = [];
  t.mock.method(
    IDBObjectStore.prototype,
    "put",
    function (this: IDBObjectStore, value: unknown, key?: IDBValidKey) {
      if (key === "active" && ++writes === 2)
        throw new DOMException("Synthetic ack failure", "QuotaExceededError");
      return put.call(this, value, key);
    },
  );
  t.mock.method(
    globalThis,
    "fetch",
    async (_url: unknown, init: RequestInit) => {
      const body = JSON.parse(String(init.body));
      operations.push(body.operation_id);
      return response({ revision: 1, document: body.document });
    },
  );
  await assert.rejects(sendProject(active.read, active.persist, TOKEN), {
    name: "QuotaExceededError",
  });
  const stored = (await loadLocal())!;
  assert.ok(stored.pendingSend);
  assert.equal(stored.outbox.length, 1);
  active = client(stored);
  await sendProject(active.read, active.persist, TOKEN);
  assert.equal(operations[0], operations[1]);
  assert.equal(active.read().pendingSend, null);
  assert.equal(active.read().outbox.length, 0);
});

test("competing tabs cannot create two independent upload requests from one revision", async (t) => {
  const initial = demoState();
  await saveLocal(initial, null);
  const a = client(initial),
    b = client(initial);
  const fetch = t.mock.method(
    globalThis,
    "fetch",
    async (_url: unknown, init: RequestInit) =>
      response({
        revision: 1,
        document: JSON.parse(String(init.body)).document,
      }),
  );
  const results = await Promise.allSettled([
    sendProject(a.read, a.persist, TOKEN),
    sendProject(b.read, b.persist, TOKEN),
  ]);
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
  assert.ok(
    results.some(
      (r) => r.status === "rejected" && r.reason instanceof LocalConflict,
    ),
  );
  assert.equal(fetch.mock.callCount(), 1);
});

test("a validated revision conflict ends the retry without replacing local edits", async (t) => {
  const initial = change(demoState(), "Local edit", (p) => {
    p.name = "Local work";
  });
  await saveLocal(initial, null);
  const active = client(initial),
    remote = clone(initial.project);
  remote.name = "Shared work";
  t.mock.method(globalThis, "fetch", async () =>
    response({ current: { revision: 2, document: remote } }, 409),
  );
  const outcome = await sendProject(active.read, active.persist, TOKEN);
  assert.equal(outcome.kind, "conflict");
  assert.equal(active.read().pendingSend, null);
  assert.equal(active.read().project.name, "Local work");
  assert.equal(active.read().outbox.length, 1);
  assert.equal(outcome.remote.document.name, "Shared work");
});

test("malformed or foreign acknowledgements retain the unconfirmed upload", async (t) => {
  const initial = demoState();
  await saveLocal(initial, null);
  const active = client(initial),
    foreign = demoState().project;
  t.mock.method(globalThis, "fetch", async () =>
    response({ revision: 1, document: foreign }),
  );
  await assert.rejects(
    sendProject(active.read, active.persist, TOKEN),
    /different project/,
  );
  const saved = (await loadLocal())!;
  assert.ok(saved.pendingSend);
  assert.equal(saved.project.id, initial.project.id);
  assert.equal(saved.remoteRevision, 0);
});

test("pull and conflict responses must belong to the requested project", async (t) => {
  const requested = demoState().project,
    foreign = demoState().project;
  let status = 200;
  t.mock.method(globalThis, "fetch", async () =>
    response(
      status === 200
        ? { revision: 1, document: foreign }
        : { current: { revision: 2, document: foreign } },
      status,
    ),
  );
  await assert.rejects(pull(requested.id, TOKEN), /different project/);
  status = 409;
  await assert.rejects(
    push(requested, 0, "operation", TOKEN),
    /different project/,
  );
});

test("invalid response envelopes and unsafe revisions fail with a protocol error", async (t) => {
  const project = demoState().project;
  let value: unknown;
  t.mock.method(globalThis, "fetch", async () => response(value));
  for (value of [
    null,
    [],
    {},
    { error: "Not a project" },
    ...[0, -1, 1.5, "1", Number.MAX_SAFE_INTEGER + 1].map((revision) => ({
      revision,
      document: project,
    })),
  ])
    await assert.rejects(
      pull(project.id, TOKEN),
      /invalid project response or revision/,
    );
});

test("successful responses must confirm the exact uploaded content and next revision", async (t) => {
  const project = demoState().project;
  let value: unknown;
  t.mock.method(globalThis, "fetch", async () => response(value));
  const changed = clone(project);
  changed.layers[0].features[0].properties.name = "Different content";
  for (value of [
    { revision: 1, document: changed },
    { revision: 2, document: project },
  ])
    await assert.rejects(push(project, 0, "operation", TOKEN), /exact upload/);
  value = reordered({ revision: 1, document: project });
  assert.deepEqual(
    (await push(project, 0, "operation", TOKEN)).document,
    project,
  );
});

test("missing and malformed conflicts are not mistaken for a deleted project", async (t) => {
  const project = demoState().project;
  let value: unknown;
  t.mock.method(globalThis, "fetch", async () => response(value, 409));
  for (value of [{}, { current: undefined }, { current: {} }])
    await assert.rejects(push(project, 0, "operation", TOKEN), /invalid/);
  value = { current: null };
  await assert.rejects(push(project, 0, "operation", TOKEN), /was removed/);
  value = { current: { revision: 1, document: project } };
  await assert.rejects(push(project, 0, "operation", TOKEN), SyncConflict);
});

test("invalid upload identities, revisions and missing credentials never request the service", async (t) => {
  const project = demoState().project,
    fetch = t.mock.method(globalThis, "fetch", async () => response({}));
  for (const revision of [-1, 0.5, Number.MAX_SAFE_INTEGER, Number.NaN])
    await assert.rejects(
      push(project, revision, "operation", TOKEN),
      /Invalid upload/,
    );
  await assert.rejects(push(project, 0, "bad/path", TOKEN), /Invalid upload/);
  await assert.rejects(pull("bad/path", TOKEN), /Invalid shared project ID/);
  await assert.rejects(
    push(project, 0, "operation", ""),
    /private workspace token/,
  );
  assert.equal(fetch.mock.callCount(), 0);
});

test("pending uploads validate their project, revision, operation and credential-free metadata", async () => {
  const initial = demoState();
  await saveLocal(initial, null);
  const queued = prepareSend(initial);
  const mutations: ((s: LocalState) => void)[] = [
    (s) => {
      s.pendingSend!.project.id = "another-project";
    },
    (s) => {
      s.pendingSend!.baseRevision = 9;
    },
    (s) => {
      s.pendingSend!.localRevision = s.revision;
    },
    (s) => {
      s.revision = Number.NaN;
    },
    (s) => {
      s.pendingSend!.ops = new Array(1);
    },
    (s) => {
      s.pendingSend!.operation = "";
    },
    (s) => {
      s.pendingSend!.ops = ["duplicate", "duplicate"];
    },
    (s) => {
      Object.assign(s.pendingSend!, { token: TOKEN });
    },
  ];
  for (const mutate of mutations) {
    const invalid = clone(queued);
    mutate(invalid);
    assert.throws(() => validatePendingSend(invalid));
    await assert.rejects(saveLocal(invalid, initial.revision));
    assert.deepEqual(await loadLocal(), initial);
  }
  assert.equal(prepareSend(queued), queued);
});

test("server object-key ordering cannot create false processing-step merge conflicts", () => {
  const base = demoState().project;
  base.layers[0].steps = [
    { operation: "prep", detail: "Original", at: "2026-11-17T12:00:00Z" },
  ];
  const local = clone(base),
    remote = reordered(base) as Project;
  local.layers[0].steps[0].detail = "Local method improvement";
  remote.layers[0].features[0].properties.name = "Independent shared edit";
  const merged = mergeProjects(base, local, remote);
  assert.equal(merged.conflicts.length, 0);
  assert.equal(
    merged.project.layers[0].steps[0].detail,
    "Local method improvement",
  );
  assert.equal(
    merged.project.layers[0].features[0].properties.name,
    "Independent shared edit",
  );
  assert.ok(equalJson({ a: [1, 2], b: 3 }, { b: 3, a: [1, 2] }));
  assert.ok(!equalJson({ a: [1, 2] }, { a: [2, 1] }));
});
