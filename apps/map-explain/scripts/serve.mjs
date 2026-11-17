import { createServer, request as upstreamRequest } from "node:http";
import { isIP } from "node:net";
import { readFile, realpath } from "node:fs/promises";
import { resolve, relative, isAbsolute, sep, extname } from "node:path";

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".webmanifest": "application/manifest+json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".woff2": "font/woff2",
};
const livePath = "/__observatory/live",
  reloadPath = "/__observatory/reload.js";
const inside = (root, path) => {
  const r = relative(root, path);
  return r !== ".." && !r.startsWith(".." + sep) && !isAbsolute(r);
};

// A local, same-origin development server. API traffic is streamed unchanged to
// the fixed loopback service; neither credentials nor request bodies are logged.
export function createWorkspaceServer({
  directory,
  development = false,
  proxyPort = 8789,
  host = "127.0.0.1",
}) {
  const clients = new Set();
  const server = createServer(async (req, res) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Cache-Control", "no-store");
    const fail = (status, message) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: message }));
    };
    let authority;
    try {
      authority = new URL("http://" + req.headers.host);
      const name = authority.hostname.replace(/^\[|\]$/g, "");
      if (
        !req.headers.host ||
        authority.host !== req.headers.host ||
        authority.username ||
        authority.password ||
        authority.pathname !== "/" ||
        !(
          isIP(name) ||
          name === "localhost" ||
          name.endsWith(".localhost") ||
          name === host
        )
      )
        return fail(403, "Untrusted host.");
      if (req.headers.origin && req.headers.origin !== authority.origin)
        return fail(403, "Cross-origin requests are not accepted.");
    } catch {
      return fail(400, "Invalid host.");
    }
    if (!req.url?.startsWith("/") || req.url.startsWith("//"))
      return fail(400, "Invalid path.");
    let pathname;
    try {
      pathname = decodeURIComponent(req.url.split("?")[0]);
      if (
        pathname.includes("\0") ||
        pathname.includes("\\") ||
        pathname.split("/").some((p) => p === "..")
      )
        throw new Error();
    } catch {
      return fail(400, "Invalid path.");
    }
    if (pathname === "/api" || pathname.startsWith("/api/")) {
      if (!development)
        return fail(404, "The private service is not connected to preview.");
      const upstream = upstreamRequest(
        {
          hostname: "127.0.0.1",
          port: proxyPort,
          path: req.url,
          method: req.method,
          headers: req.headers,
        },
        (reply) => {
          res.writeHead(reply.statusCode ?? 502, {
            ...reply.headers,
            "x-content-type-options": "nosniff",
            "cache-control": "no-store",
          });
          reply.on("error", () => res.destroy());
          reply.pipe(res);
        },
      );
      upstream.setTimeout(30000, () =>
        upstream.destroy(new Error("Service timeout")),
      );
      upstream.on("error", () => {
        if (!res.headersSent)
          fail(502, "The local private service is unavailable.");
        else res.destroy();
      });
      req.on("aborted", () => upstream.destroy());
      res.on("close", () => upstream.destroy());
      req.pipe(upstream);
      return;
    }
    if (req.method !== "GET" && req.method !== "HEAD")
      return fail(405, "Only GET and HEAD are accepted.");
    if (development && pathname === livePath && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        Connection: "keep-alive",
      });
      res.write(": connected\n\n");
      clients.add(res);
      res.on("close", () => clients.delete(res));
      return;
    }
    if (development && pathname === reloadPath) {
      res.writeHead(200, { "Content-Type": "text/javascript; charset=utf-8" });
      res.end(
        req.method === "HEAD"
          ? undefined
          : `new EventSource('${livePath}').addEventListener('change',()=>location.reload());`,
      );
      return;
    }
    try {
      const root = await realpath(directory),
        target = await realpath(
          resolve(root, "." + (pathname === "/" ? "/index.html" : pathname)),
        );
      if (!inside(root, target)) return fail(403, "Invalid asset path.");
      let body = await readFile(target);
      if (development && target === resolve(root, "index.html"))
        body = Buffer.from(
          body
            .toString()
            .replace(
              "</body>",
              `<script type="module" src="${reloadPath}"></script></body>`,
            ),
        );
      res.writeHead(200, {
        "Content-Type": mime[extname(target)] ?? "application/octet-stream",
        "Content-Length": body.length,
      });
      res.end(req.method === "HEAD" ? undefined : body);
    } catch {
      if (!res.headersSent) fail(404, "Asset not found.");
      else res.destroy();
    }
  });
  server.notify = () => {
    for (const client of clients)
      client.write("event: change\ndata: ready\n\n");
  };
  server.closeLiveClients = () => {
    for (const client of clients) client.end();
    clients.clear();
  };
  return server;
}
