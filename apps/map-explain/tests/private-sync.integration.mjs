// Optional: npm run test:sync-service. Requires Python 3.11+; no GIS wheels needed.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { IDBFactory } from "fake-indexeddb";
import { pull, push } from "../.test-build/src/lib/observatory/api.js";
import {
  change,
  demoState,
  MAX_BYTES,
  validateProject,
} from "../.test-build/src/lib/observatory/model.js";
import {
  loadLocal,
  saveLocal,
} from "../.test-build/src/lib/observatory/store.js";
import { sendProject } from "../.test-build/src/lib/observatory/sync.js";

const TOKEN = "synthetic-integration-fixture-not-a-user-secret-12345";
const serviceDir = fileURLToPath(
  new URL("../../../services/observatory/", import.meta.url),
);
const directory = mkdtempSync(join(tmpdir(), "zqm-sync-integration-"));
const bootstrap = `
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from server import Store, make_server
root = Path(sys.argv[2])
static = root / "static"
static.mkdir()
(static / "index.html").write_text("Synthetic integration fixture")
server = make_server(("127.0.0.1", 0), os.environ["OBSERVATORY_TOKEN"], Store(root / "sync.sqlite"), static)
print(server.server_port, flush=True)
server.serve_forever()
`;
const service = spawn(
  process.env.OBSERVATORY_TEST_PYTHON || "python",
  ["-u", "-c", bootstrap, serviceDir, directory],
  {
    env: { ...process.env, OBSERVATORY_TOKEN: TOKEN },
    stdio: ["ignore", "pipe", "pipe"],
  },
);
const realFetch = globalThis.fetch;
let diagnostic = "";
service.stderr.on("data", (chunk) => {
  diagnostic = (diagnostic + chunk.toString()).slice(-4000);
});
try {
  const reader = createInterface({ input: service.stdout });
  const port = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () =>
        reject(
          new Error("Python sync fixture did not start within 10 seconds."),
        ),
      10000,
    );
    service.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    service.once("exit", () => {
      clearTimeout(timer);
      reject(
        new Error("Python sync fixture exited before readiness. " + diagnostic),
      );
    });
    reader.once("line", (line) => {
      clearTimeout(timer);
      reader.close();
      if (!/^\d+$/.test(line) || Number(line) < 1 || Number(line) > 65535)
        reject(new Error("Invalid fixture port."));
      else resolve(Number(line));
    });
  });
  globalThis.indexedDB = new IDBFactory();
  let dropReply = true;
  const uploads = [];
  globalThis.fetch = async (path, options) => {
    const result = await realFetch(
      new URL(path, `http://127.0.0.1:${port}`),
      options,
    );
    if (options?.method === "PUT") uploads.push(options.body);
    if (dropReply && options?.method === "PUT" && result.ok) {
      dropReply = false;
      await result.arrayBuffer(); // Commit was accepted; simulate the client losing its reply.
      throw new TypeError(
        "Synthetic lost acknowledgement after real server commit",
      );
    }
    return result;
  };
  let state = change(demoState(), "Initial synthetic sync edit", (p) => {
    p.name = "Original shared snapshot";
  });
  await saveLocal(state, null);
  const read = () => state;
  const persist = async (next, expected) => {
    await saveLocal(next, expected);
    state = next;
  };
  await assert.rejects(
    sendProject(read, persist, TOKEN),
    /Synthetic lost acknowledgement/,
  );
  state = await loadLocal();
  const operation = state.pendingSend.operation;
  assert.ok(!JSON.stringify(state).includes(TOKEN));
  await persist(
    change(state, "Newer offline edit", (p) => {
      p.name = "Newer local snapshot";
    }),
    state.revision,
  );
  state = await loadLocal(); // Fresh database read, as on page reload; token supplied separately.
  const confirmed = await sendProject(read, persist, TOKEN);
  assert.equal(confirmed.kind, "confirmed");
  assert.equal(confirmed.remote.revision, 1);
  assert.equal(uploads[0], uploads[1]);
  assert.equal(JSON.parse(uploads[1]).operation_id, operation);
  assert.equal(state.pendingSend, null);
  assert.equal(state.project.name, "Newer local snapshot");
  assert.equal(state.outbox.length, 1);
  assert.equal(
    (await pull(state.project.id, TOKEN)).document.name,
    "Original shared snapshot",
  );
  await sendProject(read, persist, TOKEN);
  assert.equal(state.remoteRevision, 2);
  assert.equal(state.outbox.length, 0);
  assert.equal(
    (await pull(state.project.id, TOKEN)).document.name,
    "Newer local snapshot",
  );

  const large = demoState().project;
  large.layers = [large.layers[0]];
  large.layers[0].steps = [];
  large.layers[0].features = [
    {
      type: "Feature",
      id: "size-boundary",
      geometry: { type: "Point", coordinates: [0, 0] },
      properties: { name: "Synthetic full-budget feature", padding: "" },
    },
  ];
  large.layers[0].features[0].properties.padding = "x".repeat(
    MAX_BYTES - new TextEncoder().encode(JSON.stringify(large)).byteLength,
  );
  validateProject(large);
  const fullBudget = await push(large, 0, "full-budget-integration", TOKEN);
  assert.equal(fullBudget.revision, 1);
  assert.deepEqual(fullBudget.document, large);
  console.log(
    JSON.stringify({
      durableRetryAfterLostReply: "passed",
      identicalReceiptAfterReload: "passed",
      laterEditsConfirmedSeparately: "passed",
      fullBudgetProjectBytes: MAX_BYTES,
      tokenPersisted: false,
    }),
  );
} finally {
  globalThis.fetch = realFetch;
  if (service.pid && service.exitCode === null && service.signalCode === null) {
    const exited = once(service, "exit");
    service.kill();
    await exited;
  }
  rmSync(directory, { recursive: true, force: true });
}
