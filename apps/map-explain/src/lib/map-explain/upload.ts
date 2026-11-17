import type { UploadPoint } from "./engine.js";

export type Diagnostic = { level: "info" | "warn"; text: string };
export type UploadParse = { points: UploadPoint[]; diagnostics: Diagnostic[]; numericFields: string[] };
export const MAX_FILE_BYTES = 2_000_000;
export const MAX_POINTS = 2_000;
const LAT = new Set(["lat", "latitude", "y", "lat_dd", "y_lat"]);
const LON = new Set(["lon", "lng", "long", "longitude", "x", "lon_dd", "x_lon"]);
const NAME = new Set(["name", "title", "label", "site", "id", "stop"]);
const normKey = (key: string) => key.trim().toLowerCase().replace(/\s+/g, "_");
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const fail = (text: string): UploadParse => ({ points: [], diagnostics: [{ level: "warn", text }], numericFields: [] });

function coordinate(value: unknown): number | null {
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/** RFC-style quoted fields, with explicit rejection of malformed row structure. */
export function csvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let state: "plain" | "quoted" | "closed" = "plain";
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (state === "quoted") {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') state = "closed";
      else cell += c;
      continue;
    }
    if (c === ",") { row.push(cell); cell = ""; state = "plain"; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some((v) => v.trim())) rows.push(row);
      row = []; cell = ""; state = "plain";
    } else if (c === '"' && !cell && state === "plain") state = "quoted";
    else if (state === "closed" || c === '"') throw new Error("Malformed CSV quoting.");
    else cell += c;
  }
  if (state === "quoted") throw new Error("Unclosed CSV quote.");
  row.push(cell);
  if (row.some((v) => v.trim())) rows.push(row);
  return rows;
}

export function parseUpload(text: string, filename: string): UploadParse {
  if (new TextEncoder().encode(text).byteLength > MAX_FILE_BYTES) return fail("Files over 2 MB are not read.");
  const trimmed = text.replace(/^\uFEFF/, "").trim();
  if (!trimmed) return fail("The file is empty.");
  const points: UploadPoint[] = [];
  const diagnostics: Diagnostic[] = [];
  const numeric = new Set<string>();
  let dropped = 0;
  let valid = 0;

  const add = (name: string, longitude: unknown, latitude: unknown, input: Record<string, unknown>, json = false) => {
    const lon = json && typeof longitude !== "number" ? null : coordinate(longitude);
    const lat = json && typeof latitude !== "number" ? null : coordinate(latitude);
    if (lon === null || lat === null || Math.abs(lon) > 180 || Math.abs(lat) > 90) { dropped++; return; }
    valid++;
    if (points.length >= MAX_POINTS) return;
    const props: Record<string, string | number> = Object.create(null);
    for (const [key, value] of Object.entries(input)) {
      const k = normKey(key);
      if (LAT.has(k) || LON.has(k) || NAME.has(k)) continue;
      if (typeof value === "number" && Number.isFinite(value)) { props[k] = value; numeric.add(k); }
      else if (typeof value === "string" && value.trim()) props[k] = value.trim();
    }
    points.push({ id: `upload-${points.length + 1}`, name: name.trim() || `Point ${points.length + 1}`, lon, lat, props });
  };

  if (/^[\[{]/.test(trimmed) || /\.(geojson|json)$/i.test(filename)) {
    let root: unknown;
    try { root = JSON.parse(trimmed); } catch { return fail("That JSON could not be parsed."); }
    if (!record(root)) return fail("Expected a GeoJSON Feature or FeatureCollection of points.");
    // RFC 7946 uses WGS84 longitude/latitude and omits the legacy CRS member.
    if ("crs" in root) return fail("Legacy CRS declarations are not accepted. Reproject to RFC 7946 WGS84 GeoJSON first.");
    const features = root.type === "FeatureCollection" && Array.isArray(root.features) ? root.features : root.type === "Feature" ? [root] : null;
    if (!features) return fail("Expected a GeoJSON Feature or FeatureCollection of points.");
    for (const item of features) {
      if (!record(item) || "crs" in item || item.type !== "Feature" || !record(item.geometry) || "crs" in item.geometry || item.geometry.type !== "Point" || !Array.isArray(item.geometry.coordinates) || item.geometry.coordinates.length < 2 || item.geometry.coordinates.length > 3 || item.geometry.coordinates.some((v) => typeof v !== "number" || !Number.isFinite(v))) { dropped++; continue; }
      if (item.properties !== null && item.properties !== undefined && !record(item.properties)) { dropped++; continue; }
      const props = record(item.properties) ? item.properties : {};
      const label = Object.entries(props).find(([k, v]) => NAME.has(normKey(k)) && ["string", "number"].includes(typeof v))?.[1];
      add(label === undefined ? "" : String(label), item.geometry.coordinates[0], item.geometry.coordinates[1], props, true);
    }
  } else {
    let rows: string[][];
    try { rows = csvRows(trimmed); } catch { return fail("The CSV has malformed or unclosed quoted fields."); }
    if (rows.length < 2) return fail("The CSV needs a header and at least one data row.");
    const headers = rows[0].map(normKey);
    if (headers.some((k) => !k) || new Set(headers).size !== headers.length) return fail("CSV headers must be nonempty and unique.");
    const latCols = headers.flatMap((k, i) => LAT.has(k) ? [i] : []);
    const lonCols = headers.flatMap((k, i) => LON.has(k) ? [i] : []);
    if (latCols.length !== 1 || lonCols.length !== 1) return fail("Use exactly one latitude and one longitude column in WGS84 degrees.");
    const nameIndex = headers.findIndex((k) => NAME.has(k));
    for (const row of rows.slice(1)) {
      if (row.length !== headers.length) { dropped++; continue; }
      add(nameIndex < 0 ? "" : row[nameIndex], row[lonCols[0]], row[latCols[0]], Object.fromEntries(headers.map((k, i) => [k, row[i]])));
    }
  }
  diagnostics.push({ level: "info", text: `Read ${points.length} points from ${filename}. WGS84 longitude/latitude degrees (EPSG:4326); no geocoding or reprojection.` });
  if (dropped) diagnostics.push({ level: "warn", text: `Dropped ${dropped} invalid records: missing or invalid coordinates, row structure, or non-Point geometry. No substitute geometry was invented.` });
  if (valid > MAX_POINTS) diagnostics.push({ level: "warn", text: `Only the first ${MAX_POINTS.toLocaleString("en-US")} valid points are kept (${valid} valid records found).` });
  return { points, diagnostics, numericFields: [...numeric] };
}
