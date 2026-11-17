import {
  clinics,
  customers,
  neighborhoods,
  warehouse,
} from "../map-explain/data.js";

export type Json =
  | null
  | boolean
  | number
  | string
  | Json[]
  | { [key: string]: Json };
export type Position = [number, number];
export type Geometry = {
  type: string;
  coordinates?: unknown;
  geometries?: Geometry[];
};
export type Feature = {
  type: "Feature";
  id: string;
  geometry: Geometry;
  properties: Record<string, Json>;
};
export type Step = { operation: string; detail: string; at: string };
export type Layer = {
  id: string;
  name: string;
  features: Feature[];
  color: string;
  visible: boolean;
  source: {
    name: string;
    kind: "synthetic" | "user" | "derived" | "field";
    importedAt: string;
    sourceDate: string | null;
    rights: "unreviewed";
    note: string;
  };
  steps: Step[];
};
export type Comment = {
  id: string;
  text: string;
  author: string;
  featureId: string | null;
  at: string;
};
export type Project = {
  schema_version: 1;
  id: string;
  name: string;
  layers: Layer[];
  comments: Comment[];
  history: { id: string; at: string; summary: string }[];
  publication_authorized: false;
  fieldForm?: { extraLabel: string; extraRequired: boolean };
};
export type LocalState = {
  project: Project;
  revision: number;
  remoteRevision: number;
  base: Project | null;
  undo: Project[];
  outbox: { id: string; revision: number; summary: string }[];
};
export const MAX_FEATURES = 2000;
export const MAX_BYTES = 8_000_000;
export const id = () => crypto.randomUUID();
export const clone = <T>(value: T): T => structuredClone(value);
export const now = () => new Date().toISOString();
export const isRecord = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
export function label(feature: Feature): string {
  return String(
    feature.properties.name ?? feature.properties.title ?? feature.id,
  );
}

export function positions(geometry: Geometry): Position[] {
  const walk = (value: unknown): Position[] => {
    if (!Array.isArray(value)) return [];
    if (
      value.length >= 2 &&
      typeof value[0] === "number" &&
      typeof value[1] === "number"
    )
      return [[value[0], value[1]]];
    return value.flatMap(walk);
  };
  return walk(geometry.coordinates);
}

export function geometryErrors(geometry: unknown, wgs84 = true): string[] {
  if (!isRecord(geometry) || typeof geometry.type !== "string")
    return ["Missing geometry."];
  let count = 0;
  const point = (v: unknown) => {
    count++;
    return (
      Array.isArray(v) &&
      v.length >= 2 &&
      v.length <= 3 &&
      v.every((n) => typeof n === "number" && Number.isFinite(n)) &&
      (!wgs84 || (Math.abs(v[0]) <= 180 && Math.abs(v[1]) <= 90))
    );
  };
  const line = (v: unknown, min = 2): boolean =>
    Array.isArray(v) && v.length >= min && v.every(point);
  const ring = (v: unknown): boolean =>
    line(v, 4) &&
    Array.isArray(v) &&
    JSON.stringify(v[0]) === JSON.stringify(v.at(-1)) &&
    new Set(v.map((p) => JSON.stringify(p))).size >= 3;
  const polygon = (v: unknown): boolean =>
    Array.isArray(v) && v.length > 0 && v.every(ring);
  const many = (v: unknown, fn: (value: unknown) => boolean) =>
    Array.isArray(v) && v.length > 0 && v.every(fn);
  let valid = false;
  switch (geometry.type) {
    case "Point":
      valid = point(geometry.coordinates);
      break;
    case "MultiPoint":
      valid = many(geometry.coordinates, point);
      break;
    case "LineString":
      valid = line(geometry.coordinates);
      break;
    case "MultiLineString":
      valid = many(geometry.coordinates, (v) => line(v));
      break;
    case "Polygon":
      valid = polygon(geometry.coordinates);
      break;
    case "MultiPolygon":
      valid = many(geometry.coordinates, polygon);
      break;
    default:
      return [
        "Unsupported geometry. Use Point, LineString, Polygon, or their Multi variants.",
      ];
  }
  if (count > 20000) return ["Geometry exceeds 20,000 coordinates."];
  return valid
    ? []
    : ["Invalid, unclosed, nonfinite, or out-of-range geometry coordinates."];
}

function safeJson(value: unknown, depth = 0): boolean {
  if (depth > 12) return false;
  if (value === null || typeof value === "boolean" || typeof value === "string")
    return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every((v) => safeJson(v, depth + 1));
  if (isRecord(value))
    return Object.entries(value).every(
      ([k, v]) =>
        !["__proto__", "constructor", "prototype"].includes(k) &&
        safeJson(v, depth + 1),
    );
  return false;
}

export function validateProject(input: unknown): asserts input is Project {
  if (
    !safeJson(input) ||
    !isRecord(input) ||
    input.schema_version !== 1 ||
    input.publication_authorized !== false
  )
    throw new Error(
      "Expected a draft Observatory project (schema 1, publication false).",
    );
  if (new TextEncoder().encode(JSON.stringify(input)).byteLength > MAX_BYTES)
    throw new Error("Project exceeds the 8 MB limit.");
  if (
    typeof input.id !== "string" ||
    !/^[a-zA-Z0-9_-]{1,80}$/.test(input.id) ||
    typeof input.name !== "string" ||
    !input.name.trim() ||
    input.name.length > 120
  )
    throw new Error("Invalid project identity.");
  if (
    !Array.isArray(input.layers) ||
    input.layers.length > 30 ||
    !Array.isArray(input.comments) ||
    input.comments.length > 500 ||
    !Array.isArray(input.history) ||
    input.history.length > 100
  )
    throw new Error("Invalid project collections.");
  if (
    input.fieldForm !== undefined &&
    (!isRecord(input.fieldForm) ||
      typeof input.fieldForm.extraLabel !== "string" ||
      !input.fieldForm.extraLabel.trim() ||
      input.fieldForm.extraLabel.length > 80 ||
      typeof input.fieldForm.extraRequired !== "boolean")
  )
    throw new Error("Invalid field form configuration.");
  const layerIds = new Set<string>(),
    layerNames = new Set<string>();
  for (const layer of input.layers) {
    if (
      !isRecord(layer) ||
      typeof layer.id !== "string" ||
      layerIds.has(layer.id) ||
      typeof layer.name !== "string" ||
      !layer.name.trim() ||
      typeof layer.visible !== "boolean" ||
      typeof layer.color !== "string" ||
      !/^#[a-fA-F0-9]{6}$/.test(layer.color) ||
      !Array.isArray(layer.features) ||
      layer.features.length > MAX_FEATURES ||
      !isRecord(layer.source) ||
      layer.source.rights !== "unreviewed" ||
      !["synthetic", "user", "derived", "field"].includes(
        String(layer.source.kind),
      ) ||
      typeof layer.source.name !== "string" ||
      !Array.isArray(layer.steps)
    )
      throw new Error("Invalid layer, source, or feature limit.");
    if (
      layer.name.length > 120 ||
      layerNames.has(layer.name.trim().toLowerCase())
    )
      throw new Error("Layer names must be unique and at most 120 characters.");
    layerNames.add(layer.name.trim().toLowerCase());
    layerIds.add(layer.id);
    if (
      typeof layer.source.note !== "string" ||
      typeof layer.source.importedAt !== "string" ||
      !(
        layer.source.sourceDate === null ||
        typeof layer.source.sourceDate === "string"
      ) ||
      layer.steps.length > 100 ||
      layer.steps.some(
        (s) =>
          !isRecord(s) ||
          typeof s.operation !== "string" ||
          typeof s.detail !== "string" ||
          typeof s.at !== "string",
      )
    )
      throw new Error("Invalid source or processing history.");
    const featureIds = new Set<string>();
    let coordinates = 0;
    for (const feature of layer.features) {
      if (
        !isRecord(feature) ||
        feature.type !== "Feature" ||
        typeof feature.id !== "string" ||
        !feature.id ||
        featureIds.has(feature.id) ||
        !isRecord(feature.properties) ||
        geometryErrors(feature.geometry).length
      )
        throw new Error("Invalid feature, duplicate ID, or geometry.");
      featureIds.add(feature.id);
      coordinates += positions(feature.geometry as Geometry).length;
    }
    if (coordinates > 40000)
      throw new Error("Layer exceeds 40,000 coordinates.");
  }
  for (const c of input.comments)
    if (
      !isRecord(c) ||
      typeof c.id !== "string" ||
      typeof c.text !== "string" ||
      c.text.length > 4000 ||
      typeof c.author !== "string" ||
      c.author.length > 100
    )
      throw new Error("Invalid comment.");
  for (const h of input.history)
    if (
      !isRecord(h) ||
      typeof h.id !== "string" ||
      typeof h.at !== "string" ||
      typeof h.summary !== "string"
    )
      throw new Error("Invalid project history.");
}

export function makeLayer(
  name: string,
  features: Feature[],
  kind: Layer["source"]["kind"] = "user",
  note = "Source permission, accuracy, and field conditions remain unverified.",
): Layer {
  return {
    id: id(),
    name,
    features,
    visible: true,
    color: "#28675b",
    source: {
      name,
      kind,
      importedAt: now(),
      sourceDate: null,
      rights: "unreviewed",
      note,
    },
    steps: [],
  };
}

export function demoState(): LocalState {
  const point = (p: {
    id: string;
    name: string;
    lon: number;
    lat: number;
    orderVolume?: number;
  }): Feature => ({
    type: "Feature",
    id: p.id,
    geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    properties: { name: p.name, demand: p.orderVolume ?? 1 },
  });
  const project: Project = {
    schema_version: 1,
    id: id(),
    name: "Providence synthetic workspace",
    publication_authorized: false,
    comments: [],
    history: [],
    layers: [
      makeLayer(
        "Demand points",
        customers.map(point),
        "synthetic",
        "Invented customer locations and demand values; no real business records.",
      ),
      makeLayer(
        "Facilities",
        clinics.map(point),
        "synthetic",
        "Fictional clinic locations; not a health directory.",
      ),
      makeLayer(
        "Warehouse",
        [point(warehouse)],
        "synthetic",
        "One invented supply site.",
      ),
      makeLayer(
        "Neighborhoods",
        neighborhoods.map((n) => ({
          type: "Feature",
          id: n.id,
          geometry: { type: "Polygon", coordinates: [n.ring] },
          properties: {
            name: n.name,
            population: n.pop,
            seniors: n.pop65,
            children: n.children,
          },
        })),
        "synthetic",
        "Invented boundaries and demographics; not census or parcel data.",
      ),
    ],
  };
  project.layers[1].color = "#b57736";
  project.layers[2].color = "#594b89";
  project.layers[3].color = "#98b8a6";
  return {
    project,
    revision: 0,
    remoteRevision: 0,
    base: null,
    undo: [],
    outbox: [],
  };
}

export function change(
  state: LocalState,
  summary: string,
  edit: (project: Project) => void,
): LocalState {
  const project = clone(state.project);
  edit(project);
  project.publication_authorized = false;
  const history = [
    ...new Map(
      [...state.project.history, ...project.history].map((h) => [h.id, h]),
    ).values(),
  ];
  project.history = [...history, { id: id(), at: now(), summary }].slice(-100);
  validateProject(project);
  const revision = state.revision + 1;
  return {
    ...state,
    project,
    revision,
    undo: [...state.undo, clone(state.project)].slice(-5),
    outbox: [...state.outbox, { id: id(), revision, summary }].slice(-500),
  };
}

export function acknowledge(
  state: LocalState,
  sentRevision: number,
  sentIds: string[],
  serverRevision: number,
  sent: Project,
): LocalState {
  if (serverRevision < state.remoteRevision)
    throw new Error("Stale server acknowledgement.");
  return {
    ...state,
    revision: state.revision + 1,
    remoteRevision: serverRevision,
    base: clone(sent),
    outbox: state.outbox.filter(
      (op) => !sentIds.includes(op.id) || op.revision > sentRevision,
    ),
  };
}
