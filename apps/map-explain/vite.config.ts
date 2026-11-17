import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    tailwind(),
    {
      // Vite's React development preamble is inline. Production keeps the strict
      // policy in index.html; the dev-only policy permits that local preamble.
      name: "map-explain-dev-csp",
      apply: "serve",
      transformIndexHtml: {
        order: "pre",
        handler: (html) => html.replace("script-src 'self';", "script-src 'self' 'unsafe-inline';"),
      },
    },
  ],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});
