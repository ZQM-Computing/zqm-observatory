import { createHash } from "node:crypto";
import {
  readFile,
  writeFile,
  mkdir,
  readdir,
  lstat,
  realpath,
  rm,
} from "node:fs/promises";
import { dirname, resolve, relative, sep, isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { rolldown } from "rolldown";
import { transform } from "lightningcss";

export const projectRoot = fileURLToPath(new URL("../", import.meta.url));
const hash = (value) =>
  createHash("sha256").update(value).digest("hex").slice(0, 16);
const inside = (root, path) => {
  const r = relative(root, path);
  return r !== ".." && !r.startsWith(".." + sep) && !isAbsolute(r);
};

export async function inlineStylesheet(
  path,
  root = resolve(projectRoot, "src"),
  stack = new Set(),
) {
  root = await realpath(root);
  const file = await realpath(path);
  if (!inside(root, file) || stack.has(file) || stack.size > 32)
    throw new Error("Unsafe or circular CSS import.");
  const next = new Set([...stack, file]),
    text = await readFile(file, "utf8");
  const imports = /@import\s+["'](\.[^"']+\.css)["']\s*;/g;
  let output = "",
    offset = 0;
  for (const match of text.matchAll(imports)) {
    output +=
      text.slice(offset, match.index) +
      (await inlineStylesheet(resolve(dirname(file), match[1]), root, next));
    offset = match.index + match[0].length;
  }
  output += text.slice(offset);
  if (/@import\b|@theme\b|@tailwind\b|@apply\b/.test(output))
    throw new Error("Stylesheets must contain plain local CSS.");
  return output;
}

export function shellWorker(files) {
  const entries = [...files.entries()].sort(([a], [b]) => a.localeCompare(b));
  const version = hash(
    JSON.stringify(entries.map(([name, body]) => [name, hash(body)])),
  );
  const paths = ["./", ...entries.map(([name]) => "./" + name)];
  return `const CACHE='zqm-observatory-shell-${version}';const FILES=${JSON.stringify(paths)};const ROOT=new URL('./',self.location).href;const URLS=FILES.map(p=>new URL(p,ROOT).href);self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(URLS)).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('zqm-observatory-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==self.location.origin||u.pathname.includes('/api/'))return;if(e.request.mode==='navigate'&&u.pathname===new URL(ROOT).pathname){e.respondWith(fetch(e.request).catch(()=>caches.open(CACHE).then(c=>c.match(new URL('./index.html',ROOT).href))));return;}if(URLS.includes(u.href))e.respondWith(caches.open(CACHE).then(c=>c.match(e.request)).then(hit=>hit||fetch(e.request)));});`;
}

export async function build({
  directory = resolve(projectRoot, "dist"),
  production = true,
} = {}) {
  directory = resolve(directory);
  if (
    inside(directory, projectRoot) ||
    ["src", "public", "scripts", "node_modules"].some((name) =>
      inside(resolve(projectRoot, name), directory),
    )
  )
    throw new Error("Unsafe build output directory.");
  const css = new Set(),
    files = new Map();
  const bundle = await rolldown({
    cwd: projectRoot,
    input: resolve(projectRoot, "src/main.tsx"),
    platform: "browser",
    transform: {
      jsx: "react-jsx",
      define: {
        "process.env.NODE_ENV": JSON.stringify(
          production ? "production" : "development",
        ),
        "import.meta.env.PROD": String(production),
      },
    },
    plugins: [
      {
        name: "observatory-local-css",
        load(id) {
          if (id.endsWith(".css")) {
            css.add(id);
            return { code: "", moduleType: "js" };
          }
        },
      },
    ],
  });
  let output;
  try {
    output = (
      await bundle.generate({
        format: "esm",
        minify: production,
        entryFileNames: "assets/app-[hash].js",
        chunkFileNames: "assets/chunk-[hash].js",
      })
    ).output;
  } finally {
    await bundle.close();
  }
  const entry = output.find((item) => item.type === "chunk" && item.isEntry);
  if (!entry) throw new Error("Missing application entry.");
  for (const item of output)
    files.set(item.fileName, item.type === "chunk" ? item.code : item.source);
  const base = resolve(projectRoot, "src/styles.css");
  const sheets = [...css].sort((a, b) =>
    a === base ? -1 : b === base ? 1 : a.localeCompare(b),
  );
  const source = (
    await Promise.all(sheets.map((path) => inlineStylesheet(path)))
  ).join("\n");
  const styles = transform({
    filename: "observatory.css",
    code: Buffer.from(source),
    minify: production,
  }).code;
  const cssPath = `assets/styles-${hash(styles)}.css`;
  files.set(cssPath, styles);
  async function publicFiles(path) {
    for (const name of (await readdir(path)).sort()) {
      const file = resolve(path, name),
        stat = await lstat(file);
      if (stat.isSymbolicLink())
        throw new Error("Public assets must not be symlinks.");
      if (stat.isDirectory()) await publicFiles(file);
      else if (stat.isFile()) {
        const destination = relative(resolve(projectRoot, "public"), file)
          .split(sep)
          .join("/");
        if (
          files.has(destination) ||
          destination === "index.html" ||
          destination === "sw.js" ||
          destination.startsWith("api/")
        )
          throw new Error("Invalid public asset path.");
        files.set(destination, await readFile(file));
      }
    }
  }
  await publicFiles(resolve(projectRoot, "public"));
  const template = await readFile(resolve(projectRoot, "index.html"), "utf8"),
    marker = '<script type="module" src="./src/main.tsx"></script>';
  if (template.split(marker).length !== 2)
    throw new Error("Expected exactly one application script.");
  files.set(
    "index.html",
    template.replace(
      marker,
      `<link rel="stylesheet" href="./${cssPath}" />\n    <script type="module" src="./${entry.fileName}"></script>`,
    ),
  );
  if (production) files.set("sw.js", shellWorker(files));
  await rm(directory, { recursive: true, force: true });
  await mkdir(directory, { recursive: true });
  for (const [name, body] of files) {
    const target = resolve(directory, name);
    if (!inside(resolve(directory), target))
      throw new Error("Invalid bundle path.");
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, body);
  }
  return {
    directory,
    files: [...files.keys()].sort(),
    entry: entry.fileName,
    stylesheet: cssPath,
  };
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const result = await build();
  console.log(`Built Observatory: ${result.files.length} local shell files.`);
}
