import { csvRows } from "../map-explain/upload.js";
import {
  geometryErrors,
  id,
  isRecord,
  makeLayer,
  MAX_BYTES,
  now,
  positions,
  type Feature,
  type Geometry,
  type Json,
  type Layer,
} from "./model.js";

export type PrepOptions = {
  sourceCrs: "EPSG:4326" | "EPSG:3857";
  normalize: boolean;
  closeRings: boolean;
  dropInvalid: boolean;
  dropEmpty: boolean;
};
export type PrepResult = {
  layer: Layer | null;
  diagnostics: string[];
  inputCount: number;
  rejected: number;
  fields: { name: string; missing: number }[];
};
export const DEFAULT_PREP: PrepOptions = {
  sourceCrs: "EPSG:4326",
  normalize: true,
  closeRings: false,
  dropInvalid: false,
  dropEmpty: false,
};

function mapCoordinates(
  value: unknown,
  transform: (point: number[]) => number[],
): unknown {
  if (!Array.isArray(value)) return value;
  if (value.length >= 2 && typeof value[0] === "number")
    return transform(value as number[]);
  return value.map((v) => mapCoordinates(v, transform));
}

export function reprojectGeometry(
  geometry: Geometry,
  source: string,
): Geometry {
  if (!["EPSG:4326", "EPSG:3857"].includes(source))
    throw new Error(
      "Browser conversion supports EPSG:4326 and EPSG:3857. Use private Data Prep for other CRSs.",
    );
  if (geometryErrors(geometry, source === "EPSG:4326").length)
    throw new Error("Invalid source geometry.");
  const coordinates =
    source === "EPSG:4326"
      ? structuredClone(geometry.coordinates)
      : mapCoordinates(geometry.coordinates, ([x, y, ...z]) => {
          if (Math.abs(x) > 20037508.35 || Math.abs(y) > 20037508.35)
            throw new Error("Coordinate outside the EPSG:3857 world extent.");
          return [
            ((x / 6378137) * 180) / Math.PI,
            ((2 * Math.atan(Math.exp(y / 6378137)) - Math.PI / 2) * 180) /
              Math.PI,
            ...z,
          ];
        });
  const result = { type: geometry.type, coordinates };
  if (geometryErrors(result).length)
    throw new Error(
      "Coordinate transformation produced invalid WGS84 geometry.",
    );
  return result;
}

function closeGeometry(geometry: Geometry): Geometry {
  const g = structuredClone(geometry);
  const close = (rings: unknown) => {
    if (!Array.isArray(rings)) return;
    for (const ring of rings)
      if (
        Array.isArray(ring) &&
        ring.length >= 3 &&
        JSON.stringify(ring[0]) !== JSON.stringify(ring.at(-1))
      )
        ring.push(structuredClone(ring[0]));
  };
  if (g.type === "Polygon") close(g.coordinates);
  if (g.type === "MultiPolygon" && Array.isArray(g.coordinates))
    g.coordinates.forEach(close);
  return g;
}

export function prepare(
  text: string,
  name: string,
  options: PrepOptions = DEFAULT_PREP,
  inputKind: "browser" | "private-output" = "browser",
): PrepResult {
  const diagnostics: string[] = [];
  const features: Feature[] = [];
  let input: unknown[];
  let rejected = 0;
  const limit = inputKind === "private-output" ? MAX_BYTES : 2_000_000;
  if (new TextEncoder().encode(text).byteLength > limit)
    throw new Error(
      inputKind === "private-output"
        ? "Prepared output exceeds the 8 MB project limit."
        : "Browser Data Prep accepts files up to 2 MB.",
    );
  if (/\.csv$/i.test(name)) {
    if (options.sourceCrs !== "EPSG:4326")
      throw new Error(
        "Projected CSV coordinates need private Data Prep. Browser CSV uses explicit WGS84 latitude/longitude columns.",
      );
    const rows = csvRows(text.replace(/^\uFEFF/, "").trim());
    if (rows.length < 2)
      throw new Error("CSV needs a header and at least one data row.");
    const headers = rows[0].map((h) => h.trim()),
      normalized = headers.map((h) => h.toLowerCase());
    if (headers.some((h) => !h) || new Set(headers).size !== headers.length)
      throw new Error("CSV headers must be nonempty and unique.");
    const latitude = normalized.flatMap((h, i) =>
      ["lat", "latitude", "y", "lat_dd", "y_lat"].includes(h) ? [i] : [],
    );
    const longitude = normalized.flatMap((h, i) =>
      ["lon", "lng", "longitude", "long", "x", "lon_dd", "x_lon"].includes(h)
        ? [i]
        : [],
    );
    if (latitude.length !== 1 || longitude.length !== 1)
      throw new Error(
        "CSV requires exactly one WGS84 longitude and one latitude column.",
      );
    const number = (s: string) =>
      /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(s.trim())
        ? Number(s)
        : NaN;
    input = rows.slice(1).map((row, i) =>
      row.length !== headers.length
        ? null
        : {
            type: "Feature",
            id: `row-${i + 1}`,
            properties: Object.fromEntries(headers.map((h, j) => [h, row[j]])),
            geometry: {
              type: "Point",
              coordinates: [
                number(row[longitude[0]]),
                number(row[latitude[0]]),
              ],
            },
          },
    );
  } else {
    const parsed: unknown = JSON.parse(text);
    if (!isRecord(parsed) || "crs" in parsed)
      throw new Error(
        "Use a GeoJSON FeatureCollection without a legacy CRS declaration; select the actual source CRS explicitly.",
      );
    if (parsed.type === "FeatureCollection" && Array.isArray(parsed.features))
      input = parsed.features;
    else if (parsed.type === "Feature") input = [parsed];
    else throw new Error("Expected a GeoJSON Feature or FeatureCollection.");
  }
  if (input.length > 2000)
    throw new Error(
      "Data Prep is limited to 2,000 input features; split the source instead of truncating it.",
    );
  const ids = new Set<string>();
  for (const [index, raw] of input.entries()) {
    try {
      if (
        !isRecord(raw) ||
        raw.type !== "Feature" ||
        !isRecord(raw.geometry) ||
        (raw.properties !== null && !isRecord(raw.properties))
      )
        throw new Error("Missing feature, geometry, or properties object.");
      let geometry = raw.geometry as Geometry;
      if (options.closeRings) geometry = closeGeometry(geometry);
      geometry = reprojectGeometry(geometry, options.sourceCrs);
      const properties: Record<string, Json> = Object.create(null);
      for (const [key, value] of Object.entries(raw.properties ?? {})) {
        if (["__proto__", "prototype", "constructor"].includes(key))
          throw new Error("Reserved property key.");
        const normalized = options.normalize
          ? key
              .trim()
              .toLowerCase()
              .replace(/[^a-z0-9_]+/g, "_")
              .replace(/^_+|_+$/g, "")
          : key;
        if (
          !normalized ||
          ["__proto__", "prototype", "constructor"].includes(normalized) ||
          Object.hasOwn(properties, normalized)
        )
          throw new Error(
            "Schema normalization would create empty, reserved, or duplicate fields. Disable normalization or rename fields first.",
          );
        if (typeof value === "object" && value !== null)
          properties[normalized] = JSON.stringify(value);
        else if (typeof value === "number" && !Number.isFinite(value))
          throw new Error("Nonfinite attribute.");
        else properties[normalized] = value as Json;
      }
      const featureId =
        raw.id === undefined || raw.id === null
          ? `feature-${index + 1}`
          : String(raw.id);
      if (!featureId || ids.has(featureId))
        throw new Error("Duplicate or empty feature ID.");
      ids.add(featureId);
      features.push({ type: "Feature", id: featureId, properties, geometry });
    } catch (error) {
      rejected++;
      diagnostics.push(
        `Record ${index + 1}: ${error instanceof Error ? error.message : "Invalid record"}`,
      );
    }
  }
  const keys = [...new Set(features.flatMap((f) => Object.keys(f.properties)))];
  const fields = keys.map((name) => ({
    name,
    missing: features.filter(
      (f) =>
        f.properties[name] === undefined ||
        f.properties[name] === null ||
        f.properties[name] === "",
    ).length,
  }));
  if (options.dropEmpty)
    for (const field of fields.filter((f) => f.missing === features.length))
      for (const feature of features) delete feature.properties[field.name];
  if (
    features.reduce((sum, f) => sum + positions(f.geometry).length, 0) > 40000
  )
    throw new Error("Layer exceeds 40,000 coordinates.");
  if (!features.length || (rejected > 0 && !options.dropInvalid))
    return {
      layer: null,
      diagnostics: [
        ...diagnostics,
        "Review the rejected records. No layer was added.",
      ],
      inputCount: input.length,
      rejected,
      fields,
    };
  const layer = makeLayer(name.replace(/\.[^.]+$/, ""), features);
  layer.source.name = name;
  layer.steps = [
    {
      operation: "prepare",
      at: now(),
      detail: `Source CRS explicitly set to ${options.sourceCrs}; output EPSG:4326; normalize=${options.normalize}; close rings=${options.closeRings}; rejected=${rejected}; retained=${features.length}. Basic structural checks only; use private prep for GEOS topology validation.`,
    },
  ];
  return {
    layer,
    diagnostics: [
      ...diagnostics,
      `${features.length} features prepared. Full topology and source permission remain unverified.`,
    ],
    inputCount: input.length,
    rejected,
    fields,
  };
}

/** XML is parsed as data; remote links, styles, scripts, and entities are not followed. */
export function xmlToGeoJSON(text: string, extension: "kml" | "gpx"): string {
  if (/<!DOCTYPE|<!ENTITY/i.test(text) || text.includes("\0"))
    throw new Error("Use UTF-8 XML without DTDs or entities.");
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("Invalid XML.");
  const nodes = (root: Document | Element, tag: string) =>
    Array.from(root.getElementsByTagNameNS("*", tag));
  const features: unknown[] = [];
  const gps = (p: Element) => {
    const lon = p.getAttribute("lon"),
      lat = p.getAttribute("lat");
    if (
      !lon?.trim() ||
      !lat?.trim() ||
      ![Number(lon), Number(lat)].every(Number.isFinite)
    )
      throw new Error("GPX point is missing numeric longitude or latitude.");
    return [Number(lon), Number(lat)];
  };
  if (extension === "gpx") {
    for (const point of [...nodes(doc, "wpt"), ...nodes(doc, "rtept")])
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: gps(point) },
        properties: {
          name: nodes(point, "name")[0]?.textContent ?? "GPX point",
        },
      });
    for (const segment of nodes(doc, "trkseg"))
      features.push({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: nodes(segment, "trkpt").map(gps),
        },
        properties: { name: "GPX track" },
      });
  } else
    for (const placemark of nodes(doc, "Placemark")) {
      const coords = (node: Element) =>
        (nodes(node, "coordinates")[0]?.textContent ?? "")
          .trim()
          .split(/\s+/)
          .filter(Boolean)
          .map((pair) => pair.split(",").map(Number));
      if (
        nodes(placemark, "Point").length +
          nodes(placemark, "LineString").length +
          nodes(placemark, "Polygon").length >
        1
      )
        throw new Error(
          "KML placemark has multiple geometries. Use private prep to preserve every part.",
        );
      const point = nodes(placemark, "Point")[0],
        line = nodes(placemark, "LineString")[0],
        polygon = nodes(placemark, "Polygon")[0];
      const geometry = point
        ? { type: "Point", coordinates: coords(point)[0] }
        : line
          ? { type: "LineString", coordinates: coords(line) }
          : polygon
            ? {
                type: "Polygon",
                coordinates: nodes(polygon, "LinearRing").map(coords),
              }
            : null;
      if (geometry)
        features.push({
          type: "Feature",
          geometry,
          properties: {
            name: nodes(placemark, "name")[0]?.textContent ?? "KML feature",
          },
        });
    }
  return JSON.stringify({ type: "FeatureCollection", features });
}

export function layerGeoJSON(layer: Layer): string {
  return JSON.stringify(
    {
      type: "FeatureCollection",
      zqm_observatory: {
        publisher: "ZQM Computing",
        source: layer.source,
        methods: layer.steps,
        publication_authorized: false,
      },
      features: layer.features,
    },
    null,
    2,
  );
}
