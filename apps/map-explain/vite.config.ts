import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    tailwind(),
    {
      name: "observatory-offline-shell",
      apply: "build",
      generateBundle(_options, bundle) {
        const paths = [
          "./",
          "./index.html",
          "./favicon.svg",
          "./manifest.webmanifest",
          ...Object.keys(bundle).map((p) => `./${p}`),
        ];
        const version = createHash("sha256")
          .update(
            JSON.stringify(
              Object.entries(bundle).map(([name, item]) => [
                name,
                item.type === "chunk" ? item.code : String(item.source),
              ]),
            ),
          )
          .digest("hex")
          .slice(0, 16);
        this.emitFile({
          type: "asset",
          fileName: "sw.js",
          source: `const CACHE='zqm-observatory-shell-${version}';const FILES=${JSON.stringify(paths)};const ROOT=new URL('./',self.location).href;const URLS=FILES.map(p=>new URL(p,ROOT).href);self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(URLS)).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('zqm-observatory-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==self.location.origin||u.pathname.includes('/api/'))return;if(e.request.mode==='navigate'&&u.pathname===new URL(ROOT).pathname){e.respondWith(fetch(e.request).catch(()=>caches.open(CACHE).then(c=>c.match(new URL('./index.html',ROOT).href))));return;}if(URLS.includes(u.href))e.respondWith(caches.open(CACHE).then(c=>c.match(e.request)).then(hit=>hit||fetch(e.request)));});`,
        });
      },
    },
    {
      // Vite's React development preamble is inline. Production keeps the strict
      // policy in index.html; the dev-only policy permits that local preamble.
      name: "map-explain-dev-csp",
      apply: "serve",
      transformIndexHtml: {
        order: "pre",
        handler: (html) =>
          html.replace(
            "script-src 'self';",
            "script-src 'self' 'unsafe-inline';",
          ),
      },
    },
  ],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8789", changeOrigin: false } },
  },
});
