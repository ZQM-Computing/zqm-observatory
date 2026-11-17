import { watch } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createWorkspaceServer } from "./serve.mjs";

const root = fileURLToPath(new URL("../", import.meta.url)),
  args = process.argv.slice(2),
  preview = args.includes("--preview");
const value = (flag, fallback) => {
  const i = args.indexOf(flag);
  return i < 0 ? fallback : args[i + 1];
};
const host = value("--host", "127.0.0.1"),
  port = Number(value("--port", process.env.PORT ?? (preview ? 4173 : 5173)));
if (!host || !Number.isInteger(port) || port < 0 || port > 65535)
  throw new Error("Invalid development server host or port.");
const directory = resolve(root, preview ? "dist" : ".dev-build");
const builder = preview ? null : (await import("./build.mjs")).build;
if (builder) await builder({ directory, production: false });
const server = createWorkspaceServer({
  directory,
  development: !preview,
  host,
});
await new Promise((done, reject) => {
  server.once("error", reject);
  server.listen(port, host, done);
});
console.log(
  `Observatory ${preview ? "preview" : "development"}: http://${host}:${server.address().port}/`,
);
const watchers = [];
let timer,
  running = false,
  pending = false,
  stopping = false;
async function rebuild() {
  if (stopping) return;
  if (running) {
    pending = true;
    return;
  }
  running = true;
  try {
    await builder({ directory, production: false });
    server.notify();
    console.log("Observatory rebuilt.");
  } catch (error) {
    console.error("Build failed:", error.message);
  } finally {
    running = false;
    if (pending) {
      pending = false;
      void rebuild();
    }
  }
}
if (builder)
  for (const path of ["src", "public", "index.html"]) {
    watchers.push(
      watch(resolve(root, path), { recursive: path !== "index.html" }, () => {
        clearTimeout(timer);
        timer = setTimeout(() => void rebuild(), 100);
      }),
    );
  }
function stop() {
  stopping = true;
  clearTimeout(timer);
  for (const watcher of watchers) watcher.close();
  server.closeLiveClients();
  server.close();
  server.closeAllConnections();
}
process.once("SIGINT", stop);
process.once("SIGTERM", stop);
