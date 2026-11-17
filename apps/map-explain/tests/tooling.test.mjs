import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createServer, request } from "node:http";
import vm from "node:vm";
import {
  build,
  inlineStylesheet,
  projectRoot,
  shellWorker,
} from "../scripts/build.mjs";
import { createWorkspaceServer } from "../scripts/serve.mjs";

async function temporary(t) {
  const path = await mkdtemp(join(tmpdir(), "observatory-tooling-"));
  t.after(() => rm(path, { recursive: true, force: true }));
  return path;
}
async function listen(t, server) {
  await new Promise((done) => server.listen(0, "127.0.0.1", done));
  t.after(
    () =>
      new Promise((done) => {
        server.closeLiveClients?.();
        server.close(done);
        server.closeAllConnections();
      }),
  );
  return server.address().port;
}
function get(port, path = "/", { method = "GET", headers = {}, body } = {}) {
  return new Promise((done, reject) => {
    const req = request(
      { hostname: "127.0.0.1", port, path, method, headers },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          done({
            status: res.statusCode,
            headers: res.headers,
            body: Buffer.concat(chunks).toString(),
          }),
        );
      },
    );
    req.on("error", reject);
    req.end(body);
  });
}

test("production build is deterministic, local, strict-CSP compatible and precaches real assets", async (t) => {
  const directory = join(await temporary(t), "dist"),
    first = await build({ directory });
  const before = new Map(
    await Promise.all(
      first.files.map(async (name) => [
        name,
        await readFile(join(directory, name)),
      ]),
    ),
  );
  const second = await build({ directory });
  assert.deepEqual(second, first);
  for (const [name, body] of before)
    assert.deepEqual(await readFile(join(directory, name)), body);
  const html = before.get("index.html").toString(),
    css = before.get(first.stylesheet).toString(),
    js = before.get(first.entry).toString();
  assert.match(html, /script-src 'self';/);
  assert.match(html, /src="\.\/assets\/app-[^"]+\.js"/);
  assert.match(html, /href="\.\/assets\/styles-[^"]+\.css"/);
  assert.doesNotMatch(html, /<script[^>]*>[^<]+<\/script>|vite|src\/main\.tsx/);
  assert.doesNotMatch(css, /@import\b|@theme\b|@tailwind\b|@apply\b/);
  assert.match(css, /--font-sans/);
  assert.doesNotMatch(js, /import\.meta\.env|process\.env\.NODE_ENV|@vite/);
  assert.match(js, /serviceWorker/);
  const worker = before.get("sw.js").toString(),
    paths = JSON.parse(worker.match(/const FILES=(\[[^;]+\]);/)[1]);
  assert.deepEqual(
    paths
      .filter((p) => p !== "./")
      .map((p) => p.slice(2))
      .sort(),
    first.files.filter((p) => p !== "sw.js").sort(),
  );
});

test("build refuses to replace source directories", async () => {
  for (const directory of [
    projectRoot,
    resolve(projectRoot, "src"),
    resolve(projectRoot, "public/assets"),
  ])
    await assert.rejects(build({ directory }), /Unsafe build output/);
});

test("CSS imports stay local, detect cycles and reject compiler-only or remote directives", async (t) => {
  const directory = await temporary(t),
    root = join(directory, "src");
  await mkdir(root);
  await writeFile(join(root, "part.css"), ".part { color: red; }");
  await writeFile(
    join(root, "main.css"),
    '@import "./part.css"; .main { color: blue; }',
  );
  assert.match(
    await inlineStylesheet(join(root, "main.css"), root),
    /\.part.*\.main/,
  );
  await writeFile(join(root, "part.css"), '@import "./main.css";');
  await assert.rejects(
    inlineStylesheet(join(root, "main.css"), root),
    /circular/,
  );
  await writeFile(join(directory, "outside.css"), "body{}");
  await writeFile(join(root, "main.css"), '@import "../outside.css";');
  await assert.rejects(
    inlineStylesheet(join(root, "main.css"), root),
    /Unsafe/,
  );
  for (const text of [
    '@import "https://example.test/styles.css";',
    "@theme { --color: red; }",
    ".x { @apply flex; }",
  ]) {
    await writeFile(join(root, "main.css"), text);
    await assert.rejects(
      inlineStylesheet(join(root, "main.css"), root),
      /plain local CSS/,
    );
  }
});

function workerFixture() {
  const handlers = {},
    matches = [],
    deleted = [];
  const context = {
    URL,
    self: {
      location: new URL("https://observatory.test/"),
      addEventListener: (name, fn) => (handlers[name] = fn),
      clients: { claim: async () => {} },
      skipWaiting: async () => {},
    },
    caches: {
      open: async () => ({
        match: async (key) => {
          matches.push(typeof key === "string" ? key : key.url);
          return "cached-shell";
        },
        addAll: async () => {},
      }),
      keys: async () => ["unrelated-cache", "zqm-observatory-shell-old"],
      delete: async (key) => deleted.push(key),
    },
    fetch: async () => {
      throw new Error("Offline");
    },
  };
  vm.runInNewContext(
    shellWorker(
      new Map([
        ["index.html", "shell"],
        ["assets/app.js", "code"],
      ]),
    ),
    context,
  );
  return { handlers, matches, deleted };
}
test("offline worker excludes API, cross-origin, non-GET and unlisted requests", () => {
  const { handlers } = workerFixture();
  for (const [url, method] of [
    ["https://observatory.test/api/projects", "GET"],
    ["https://observatory.test/api/projects", "POST"],
    ["https://elsewhere.test/assets/app.js", "GET"],
    ["https://observatory.test/unlisted", "GET"],
    ["https://observatory.test/assets/app.js", "POST"],
  ])
    handlers.fetch({
      request: { url, method, mode: "cors" },
      respondWith: () =>
        assert.fail("Private or unlisted request was intercepted"),
    });
});
test("offline worker serves cached shell and assets and only removes its own old caches", async () => {
  const { handlers, matches, deleted } = workerFixture();
  let response;
  handlers.fetch({
    request: {
      url: "https://observatory.test/",
      method: "GET",
      mode: "navigate",
    },
    respondWith: (r) => (response = r),
  });
  assert.equal(await response, "cached-shell");
  assert.equal(matches[0], "https://observatory.test/index.html");
  handlers.fetch({
    request: {
      url: "https://observatory.test/assets/app.js",
      method: "GET",
      mode: "cors",
    },
    respondWith: (r) => (response = r),
  });
  assert.equal(await response, "cached-shell");
  handlers.activate({ waitUntil: (r) => (response = r) });
  await response;
  assert.deepEqual(deleted, ["zqm-observatory-shell-old"]);
});

test("preview serves assets safely, preserves HEAD and never returns HTML for API routes", async (t) => {
  const directory = await temporary(t);
  await writeFile(join(directory, "index.html"), "<body>shell</body>");
  await writeFile(join(directory, "app.js"), "export {};");
  const port = await listen(t, createWorkspaceServer({ directory }));
  const index = await get(port);
  assert.equal(index.status, 200);
  assert.equal(index.headers["x-content-type-options"], "nosniff");
  assert.equal(index.body, "<body>shell</body>");
  assert.match(
    (await get(port, "/app.js")).headers["content-type"],
    /javascript/,
  );
  const head = await get(port, "/", { method: "HEAD" });
  assert.equal(head.body, "");
  assert.equal(
    Number(head.headers["content-length"]),
    Buffer.byteLength(index.body),
  );
  for (const path of ["/api", "/api/health", "/missing"]) {
    const result = await get(port, path);
    assert.equal(result.status, 404);
    assert.match(result.headers["content-type"], /json/);
  }
  for (const path of [
    "/%2e%2e/outside",
    "/%00",
    "/%ZZ",
    "/a%5cb",
    "//elsewhere.test/",
  ])
    assert.equal((await get(port, path)).status, 400);
  assert.equal(
    (await get(port, "/", { headers: { Host: "attacker.test" } })).status,
    403,
  );
  assert.equal(
    (await get(port, "/", { headers: { Origin: "https://elsewhere.test" } }))
      .status,
    403,
  );
  assert.equal((await get(port, "/", { method: "POST" })).status, 405);
});
test("development proxy preserves browser origin, authorization, method and body", async (t) => {
  const directory = await temporary(t);
  await writeFile(join(directory, "index.html"), "<body>shell</body>");
  let observed;
  const backend = createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    observed = {
      method: req.method,
      host: req.headers.host,
      origin: req.headers.origin,
      authorization: req.headers.authorization,
      body,
      url: req.url,
    };
    res.writeHead(201, { "Content-Type": "application/json" });
    res.end('{"revision":1}');
  });
  const proxyPort = await listen(t, backend),
    server = createWorkspaceServer({ directory, development: true, proxyPort }),
    port = await listen(t, server),
    origin = `http://127.0.0.1:${port}`;
  const result = await get(port, "/api/projects/fixture?check=1", {
    method: "PUT",
    headers: {
      Origin: origin,
      Authorization: "Bearer synthetic-fixture",
      "Content-Type": "application/json",
    },
    body: '{"document":"fixture"}',
  });
  assert.equal(result.status, 201);
  assert.deepEqual(observed, {
    method: "PUT",
    host: `127.0.0.1:${port}`,
    origin,
    authorization: "Bearer synthetic-fixture",
    body: '{"document":"fixture"}',
    url: "/api/projects/fixture?check=1",
  });
  assert.match((await get(port)).body, /src="\/__observatory\/reload.js"/);
  assert.match(
    (await get(port, "/__observatory/reload.js")).body,
    /EventSource/,
  );
  await new Promise((done) => {
    backend.close(done);
    backend.closeAllConnections();
  });
  const unavailable = await get(port, "/api/health");
  assert.equal(unavailable.status, 502);
  assert.doesNotMatch(unavailable.body, /Bearer|fixture|ECONNREFUSED/);
});
