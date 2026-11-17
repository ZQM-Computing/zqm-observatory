import {
  clinics,
  customers,
  neighborhoods,
  parks,
  warehouse,
  type Neighborhood,
  type Place,
} from "./data.js";
import {
  circleRing,
  distanceMeters,
  formatMeters,
  formatMoney,
  formatNumber,
  formatPercent,
  pointInRing,
  type LonLat,
} from "./geo.js";
import type { Intent, NbhdField, PointKind } from "./intent.js";
import { interpret } from "./intent.js";

export type UploadPoint = {
  id: string;
  name: string;
  lon: number;
  lat: number;
  props: Record<string, string | number>;
};

export type Context = { upload: UploadPoint[] };

export type ResultRow = {
  id: string;
  name: string;
  primary: string;
  secondary: string;
  bar: number;
};

export type LegendItem = { label: string; color: string; hollow?: boolean };

export type NbhdPaint = {
  id: string;
  name: string;
  ring: LonLat[];
  center: LonLat;
  fill: string;
  opacity: number;
  emphasis: boolean;
  label: boolean;
};

export type MapPoint = {
  id: string;
  name: string;
  lon: number;
  lat: number;
  kind: "clinic" | "park" | "customer" | "warehouse" | "upload";
  fill: string;
  radius: number;
  stroke: string;
  strokeWidth: number;
};

export type QueryResult = {
  queryId: string;
  title: string;
  summary: string;
  confidence: "Calculated locally" | "Approximate";
  confidenceNote: string;
  viaNote: string;
  steps: { title: string; detail: string }[];
  sources: { name: string; detail: string }[];
  rows: ResultRow[];
  legend: LegendItem[];
  neighborhoods: NbhdPaint[];
  points: MapPoint[];
  lines: { id: string; coordinates: LonLat[] }[];
  buffers: { id: string; ring: LonLat[] }[];
  fit: LonLat[];
  details: Record<string, { name: string; detail: string }>;
  interpretedAs: string;
};

const RAMP = ["#e6f2ee", "#b7ddd4", "#6eaea0", "#2c6b5e", "#143f38"];
const INK = "#17211e";
const PINE = "#1c4f45";
const CARD = "#fbf9f4";
const MIST = "#d5ebe4";

const SOURCE_NBHD = {
  name: "Neighborhood sample",
  detail: "Illustrative shapes and attributes. Not Census ACS and not official boundaries.",
};
const SOURCE_CLINIC = {
  name: "Clinic sample",
  detail: "Fictional facilities. Not a health-system directory.",
};
const SOURCE_PARK = {
  name: "Park sample",
  detail: "Familiar park names at approximate points. Not surveyed park boundaries.",
};
const SOURCE_CUST = {
  name: "Customer sample",
  detail: "Fictional delivery stops and order volumes.",
};
const SOURCE_WH = {
  name: "Warehouse",
  detail: "One fictional site, Eddy Street Warehouse.",
};
const SOURCE_DIST = {
  name: "Distance",
  detail: "Straight-line haversine on WGS84. Neighborhood distance uses the polygon centroid.",
};

function hash(s: string): string {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(36);
}

function colorFor(t: number): string {
  const x = Math.max(0, Math.min(1, t));
  return RAMP[Math.round(x * (RAMP.length - 1))];
}

function norm(value: number, min: number, max: number): number {
  if (max === min) return 1;
  return (value - min) / (max - min);
}

function fieldValue(n: Neighborhood, field: NbhdField): number {
  switch (field) {
    case "share65":
      return n.share65;
    case "shareChildren":
      return n.shareChildren;
    case "medianIncome":
      return n.medianIncome;
    case "broadband":
      return n.broadband;
    case "pop":
      return n.pop;
    case "pop65":
      return n.pop65;
    case "children":
      return n.children;
  }
}

function formatField(field: NbhdField, value: number): string {
  if (field === "share65" || field === "shareChildren") return formatPercent(value);
  if (field === "broadband") return `${Math.round(value)}%`;
  if (field === "medianIncome") return formatMoney(value);
  return formatNumber(value);
}

const FIELD_NOUN: Record<NbhdField, string> = {
  share65: "share of residents age 65+",
  shareChildren: "share of children",
  medianIncome: "median income",
  broadband: "broadband",
  pop: "population",
  pop65: "residents age 65+",
  children: "children",
};

function nearestPlace(origin: LonLat, places: Place[]): { place: Place; meters: number } | null {
  let best: { place: Place; meters: number } | null = null;
  for (const place of places) {
    const meters = distanceMeters(origin, [place.lon, place.lat]);
    if (!best || meters < best.meters) best = { place, meters };
  }
  return best;
}

function placesFor(kind: PointKind, ctx: Context): Place[] {
  if (kind === "clinics") return clinics;
  if (kind === "parks") return parks;
  if (kind === "customers") return customers;
  if (kind === "warehouse") return [warehouse];
  return ctx.upload.map((u) => ({
    id: u.id,
    name: u.name,
    kind: "upload" as const,
    lon: u.lon,
    lat: u.lat,
    detail: Object.entries(u.props)
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${v}`)
      .join(" · "),
    orderVolume: numericProp(u),
  }));
}

function numericProp(u: UploadPoint): number | undefined {
  for (const v of Object.values(u.props)) {
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return undefined;
}

function paintNeighborhoods(
  marks: { id: string; value: number | null; emphasis: boolean; label: boolean }[],
): NbhdPaint[] {
  const valued = marks.filter((m) => m.value != null) as { id: string; value: number }[];
  const min = valued.length ? Math.min(...valued.map((m) => m.value)) : 0;
  const max = valued.length ? Math.max(...valued.map((m) => m.value)) : 1;
  return neighborhoods.map((n) => {
    const mark = marks.find((m) => m.id === n.id);
    const emphasis = mark?.emphasis ?? false;
    const value = mark?.value ?? null;
    const fill = value == null ? "#e4ece8" : colorFor(norm(value, min, max));
    const opacity = value == null ? (emphasis ? 0.45 : 0.35) : emphasis ? 0.88 : 0.4;
    return {
      id: n.id,
      name: n.name,
      ring: n.ring,
      center: n.center,
      fill,
      opacity,
      emphasis,
      label: Boolean(mark?.label && emphasis),
    };
  });
}

function asClinic(p: Place, strong = true): MapPoint {
  return {
    id: p.id,
    name: p.name,
    lon: p.lon,
    lat: p.lat,
    kind: "clinic",
    fill: INK,
    radius: strong ? 6.5 : 4.5,
    stroke: CARD,
    strokeWidth: 1.5,
  };
}

function asPark(p: Place, strong = true): MapPoint {
  return {
    id: p.id,
    name: p.name,
    lon: p.lon,
    lat: p.lat,
    kind: "park",
    fill: "#e7f3ef",
    radius: strong ? 7 : 5,
    stroke: PINE,
    strokeWidth: 2,
  };
}

function asWarehouse(): MapPoint {
  return {
    id: warehouse.id,
    name: warehouse.name,
    lon: warehouse.lon,
    lat: warehouse.lat,
    kind: "warehouse",
    fill: PINE,
    radius: 8,
    stroke: CARD,
    strokeWidth: 3,
  };
}

function asCustomer(p: Place, t: number, strong: boolean): MapPoint {
  return {
    id: p.id,
    name: p.name,
    lon: p.lon,
    lat: p.lat,
    kind: "customer",
    fill: colorFor(t),
    radius: (strong ? 5 : 3.5) + t * 8,
    stroke: strong ? INK : CARD,
    strokeWidth: strong ? 1.25 : 1,
  };
}

function asUpload(p: Place, strong = true): MapPoint {
  return {
    id: p.id,
    name: p.name,
    lon: p.lon,
    lat: p.lat,
    kind: "upload",
    fill: "#8f3d32",
    radius: strong ? 6.5 : 4,
    stroke: CARD,
    strokeWidth: 1.5,
  };
}

function bars(values: number[]): number[] {
  const max = Math.max(...values, 0);
  if (max <= 0) return values.map(() => 0);
  return values.map((v) => v / max);
}

function fitOf(points: LonLat[], fallback: LonLat[]): LonLat[] {
  return points.length ? points : fallback;
}

function allCenters(): LonLat[] {
  return neighborhoods.map((n) => n.center);
}

function detailsFrom(nb: NbhdPaint[], points: MapPoint[], extra: Record<string, string>): Record<string, { name: string; detail: string }> {
  const details: Record<string, { name: string; detail: string }> = {};
  for (const n of nb) {
    details[n.id] = { name: n.name, detail: extra[n.id] ?? "Neighborhood sample" };
  }
  for (const p of points) {
    details[p.id] = { name: p.name, detail: extra[p.id] ?? p.kind };
  }
  return details;
}

function shell(partial: Omit<QueryResult, "queryId" | "viaNote"> & { key: string }): QueryResult {
  const { key, ...rest } = partial;
  const sources = [...rest.sources];
  const sourceByKind = { clinic: SOURCE_CLINIC, park: SOURCE_PARK, customer: SOURCE_CUST, warehouse: SOURCE_WH, upload: { name: "User-supplied points", detail: "Local input, unverified. Parsing establishes neither source permission nor factual accuracy. Publication remains blocked." } };
  for (const kind of new Set(rest.points.map((p) => p.kind))) {
    const source = sourceByKind[kind];
    if (!sources.some((s) => s.name === source.name)) sources.push(source);
  }
  return {
    ...rest,
    sources,
    queryId: hash(key + JSON.stringify(rest.rows) + JSON.stringify(rest.points)),
    viaNote: key.startsWith("explain:")
      ? "No analytical step ran. Only the illustrative context layers are shown."
      : "Matched to a built-in step on this device. Every number is calculated from the layers.",
  };
}

const MEASURED =
  "Figures are measured on the sample layers. Centroid distance is not a road route, and it can miss access along the edge of a neighborhood.";

function overviewPaints(): NbhdPaint[] {
  return paintNeighborhoods(
    neighborhoods.map((n) => ({ id: n.id, value: n.pop, emphasis: true, label: false })),
  );
}

export function explainResult(message: string): QueryResult {
  const nb = overviewPaints();
  const points = [
    ...clinics.map((c) => asClinic(c)),
    ...parks.map((p) => asPark(p)),
    asWarehouse(),
  ];
  return shell({
    key: `explain:${message}`,
    title: "That question isn’t a step this map can run",
    summary: message,
    confidence: "Calculated locally",
    confidenceNote: "No filter was applied. The map is showing the sample layers unchanged.",
    steps: [
      {
        title: "No step ran",
        detail: "Askfield only maps a fixed set of spatial steps, so it will not invent a result.",
      },
    ],
    sources: [SOURCE_NBHD, SOURCE_CLINIC, SOURCE_PARK, SOURCE_CUST, SOURCE_WH],
    rows: [],
    legend: [
      { label: "Neighborhoods", color: "#6eaea0" },
      { label: "Clinic", color: INK },
      { label: "Park", color: PINE, hollow: true },
    ],
    neighborhoods: nb,
    points,
    lines: [],
    buffers: [],
    fit: allCenters(),
    details: detailsFrom(nb, points, {}),
    interpretedAs: "Unmatched question",
  });
}

function seniorGap(minMeters: number, note: string | null): QueryResult {
  const scored = neighborhoods.map((n) => {
    const near = nearestPlace(n.center, clinics)!;
    return { n, meters: near.meters, clinic: near.place };
  });
  const kept = scored.filter((s) => s.meters > minMeters).sort((a, b) => b.n.share65 - a.n.share65);
  const byCount = [...neighborhoods].sort((a, b) => b.pop65 - a.pop65)[0];
  const countKept = kept.some((s) => s.n.id === byCount.id);
  const title = kept.length
    ? `${kept.length} ${kept.length === 1 ? "neighborhood sits" : "neighborhoods sit"} more than ${formatMeters(minMeters)} from a clinic`
    : `No neighborhood centroid is more than ${formatMeters(minMeters)} from a clinic`;
  const lead = kept.length
    ? `${kept[0].n.name} has the highest share of residents age 65+ in that set, ${formatPercent(kept[0].n.share65)} (${formatNumber(kept[0].n.pop65)} of ${formatNumber(kept[0].n.pop)}).`
    : `The farthest is ${scored.sort((a, b) => b.meters - a.meters)[0].n.name} at ${formatMeters(scored.sort((a, b) => b.meters - a.meters)[0].meters)}.`;
  const contrast = !countKept
    ? ` ${byCount.name} has the most older residents in total (${formatNumber(byCount.pop65)}), but it is not in this distance filter.`
    : "";
  const rowsSource = kept.length ? kept : [...scored].sort((a, b) => b.meters - a.meters).slice(0, 4);
  const bar = bars(rowsSource.map((s) => s.n.share65));
  const emphasis = new Set(rowsSource.map((s) => s.n.id));
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => ({
      id: n.id,
      value: emphasis.has(n.id) ? n.share65 : null,
      emphasis: emphasis.has(n.id),
      label: rowsSource.slice(0, 4).some((s) => s.n.id === n.id),
    })),
  );
  const lines = rowsSource.slice(0, 6).map((s, i) => ({
    id: `link-${i}`,
    coordinates: [s.n.center, [s.clinic.lon, s.clinic.lat]] as LonLat[],
  }));
  const points = clinics.map((c) => asClinic(c));
  const extra: Record<string, string> = {};
  for (const s of scored) {
    extra[s.n.id] = `${formatPercent(s.n.share65)} age 65+ · ${formatMeters(s.meters)} to ${s.clinic.name}`;
  }
  for (const c of clinics) extra[c.id] = c.detail;
  const misses = !kept.length;
  return shell({
    key: `senior:${minMeters}:${kept.map((k) => k.n.id).join()}`,
    title,
    summary: `${lead}${contrast} Distance is from each neighborhood centroid to the nearest clinic point.${misses ? " Nothing passed the threshold, so the list shows the farthest centroids instead." : ""}`,
    confidence: note ? "Approximate" : "Calculated locally",
    confidenceNote: note ? `${note} ${MEASURED}` : MEASURED,
    steps: [
      {
        title: "Senior share",
        detail: "Divided residents age 65+ by total population in each of the 12 neighborhoods.",
      },
      {
        title: "Nearest clinic",
        detail: "Measured a straight line from each centroid to every clinic and kept the shortest.",
      },
      {
        title: "Distance filter",
        detail: `Kept neighborhoods farther than ${formatMeters(minMeters)}. ${kept.length} of 12 passed.`,
      },
      {
        title: "Rank",
        detail: "Sorted the remaining neighborhoods by senior share, highest first.",
      },
    ],
    sources: [SOURCE_NBHD, SOURCE_CLINIC, SOURCE_DIST],
    rows: rowsSource.map((s, i) => ({
      id: s.n.id,
      name: s.n.name,
      primary: formatPercent(s.n.share65) + " age 65+",
      secondary: `${formatMeters(s.meters)} to ${s.clinic.name}`,
      bar: bar[i],
    })),
    legend: [
      { label: "Higher senior share", color: "#143f38" },
      { label: "Lower senior share", color: "#e6f2ee" },
      { label: "Clinic", color: INK },
      { label: "Link to nearest clinic", color: PINE },
    ],
    neighborhoods: nb,
    points,
    lines,
    buffers: [],
    fit: fitOf(
      [...rowsSource.map((s) => s.n.center), ...clinics.map((c) => [c.lon, c.lat] as LonLat)],
      allCenters(),
    ),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Neighborhoods more than ${formatMeters(minMeters)} from the nearest clinic, ranked by share of residents age 65+.`,
  });
}

function customersNear(meters: number, note: string | null): QueryResult {
  const scored = customers.map((c) => ({
    c,
    meters: distanceMeters([c.lon, c.lat], [warehouse.lon, warehouse.lat]),
  }));
  const inside = scored.filter((s) => s.meters <= meters).sort((a, b) => (b.c.orderVolume ?? 0) - (a.c.orderVolume ?? 0));
  const vols = customers.map((c) => c.orderVolume ?? 0);
  const min = Math.min(...vols);
  const max = Math.max(...vols);
  const volIn = inside.reduce((s, r) => s + (r.c.orderVolume ?? 0), 0);
  const volAll = vols.reduce((s, v) => s + v, 0);
  const top = inside[0];
  const title = inside.length
    ? `${inside.length} of ${customers.length} stops are within ${formatMeters(meters)}`
    : `No stops are within ${formatMeters(meters)} of the warehouse`;
  const summary = inside.length
    ? `Those stops account for ${formatNumber(volIn)} of ${formatNumber(volAll)} orders in the sample. The largest inside the ring is ${top.c.name} (${formatNumber(top.c.orderVolume ?? 0)} orders, ${formatMeters(top.meters)} away). Stops outside the ring stay on the map, dimmed.`
    : `The closest stop is ${formatMeters(Math.min(...scored.map((s) => s.meters)))} from Eddy Street Warehouse.`;
  const insideIds = new Set(inside.map((s) => s.c.id));
  const points = [
    ...scored.map((s) => asCustomer(s.c, norm(s.c.orderVolume ?? 0, min, max), insideIds.has(s.c.id))),
    asWarehouse(),
  ];
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => ({ id: n.id, value: null, emphasis: false, label: false })),
  );
  const buffer = circleRing([warehouse.lon, warehouse.lat], meters);
  const bar = bars(inside.map((s) => s.c.orderVolume ?? 0));
  const extra: Record<string, string> = {
    [warehouse.id]: warehouse.detail,
  };
  for (const s of scored) {
    extra[s.c.id] = `${formatNumber(s.c.orderVolume ?? 0)} orders · ${formatMeters(s.meters)} from the warehouse${insideIds.has(s.c.id) ? "" : " · outside the ring"}`;
  }
  return shell({
    key: `cust:${meters}:${inside.length}`,
    title,
    summary,
    confidence: note ? "Approximate" : "Calculated locally",
    confidenceNote: note ? `${note} ${MEASURED}` : MEASURED,
    steps: [
      {
        title: "Warehouse ring",
        detail: `Drew a ${formatMeters(meters)} straight-line buffer around Eddy Street Warehouse.`,
      },
      {
        title: "Stops inside",
        detail: `Tested all ${customers.length} customer points. ${inside.length} fall inside the ring.`,
      },
      {
        title: "Order volume",
        detail: "Sized and colored every stop by its order volume. The list is only the stops inside the ring, largest first.",
      },
    ],
    sources: [SOURCE_CUST, SOURCE_WH, SOURCE_DIST],
    rows: inside.map((s, i) => ({
      id: s.c.id,
      name: s.c.name,
      primary: `${formatNumber(s.c.orderVolume ?? 0)} orders`,
      secondary: formatMeters(s.meters) + " from the warehouse",
      bar: bar[i],
    })),
    legend: [
      { label: "Higher order volume", color: "#143f38" },
      { label: "Lower order volume", color: "#e6f2ee" },
      { label: "Warehouse", color: PINE },
      { label: `${formatMeters(meters)} ring`, color: MIST },
    ],
    neighborhoods: nb,
    points,
    lines: [],
    buffers: [{ id: "wh-buffer", ring: buffer }],
    fit: [[warehouse.lon, warehouse.lat], ...buffer.filter((_, i) => i % 8 === 0)],
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Customer stops within ${formatMeters(meters)} of the warehouse, drawn by order volume.`,
  });
}

function parkGap(radiusM: number): QueryResult {
  const shares = neighborhoods.map((n) => n.shareChildren).sort((a, b) => a - b);
  const median = shares[Math.floor(shares.length / 2)];
  const scored = neighborhoods.map((n) => {
    const near = nearestPlace(n.center, parks)!;
    return { n, meters: near.meters, park: near.place, high: n.shareChildren >= median };
  });
  const gaps = scored
    .filter((s) => s.high && s.meters > radiusM)
    .sort((a, b) => b.n.shareChildren * b.meters - a.n.shareChildren * a.meters);
  const covered = scored.filter((s) => s.high && s.meters <= radiusM);
  const contrast = covered.length
    ? ` ${covered[0].n.name} also has a high child share (${formatPercent(covered[0].n.shareChildren)}) but its centroid is ${formatMeters(covered[0].meters)} from ${covered[0].park.name}, so it is not a gap.`
    : "";
  const title = gaps.length
    ? `${gaps.length} high-child ${gaps.length === 1 ? "neighborhood is" : "neighborhoods are"} beyond ${formatMeters(radiusM)} of a park`
    : `No high-child neighborhood is more than ${formatMeters(radiusM)} from a park`;
  const summary = gaps.length
    ? `High child share means at or above the median, ${formatPercent(median)}. The largest gap is ${gaps[0].n.name}: ${formatPercent(gaps[0].n.shareChildren)} children, ${formatMeters(gaps[0].meters)} from ${gaps[0].park.name}.${contrast}`
    : `Median child share is ${formatPercent(median)}. Try a shorter distance.`;
  const gapIds = new Set(gaps.map((g) => g.n.id));
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => {
      const s = scored.find((x) => x.n.id === n.id)!;
      const score = s.high ? s.meters : null;
      return {
        id: n.id,
        value: gapIds.size ? (gapIds.has(n.id) ? score : null) : s.meters,
        emphasis: gapIds.size ? gapIds.has(n.id) : true,
        label: gaps.slice(0, 4).some((g) => g.n.id === n.id),
      };
    }),
  );
  const points = parks.map((p) => asPark(p));
  const lines = (gaps.length ? gaps : scored.filter((s) => s.high))
    .slice(0, 5)
    .map((s, i) => ({
      id: `plink-${i}`,
      coordinates: [s.n.center, [s.park.lon, s.park.lat]] as LonLat[],
    }));
  const list = gaps.length ? gaps : scored.filter((s) => s.high).sort((a, b) => b.meters - a.meters);
  const bar = bars(list.map((s) => s.n.shareChildren));
  const extra: Record<string, string> = {};
  for (const s of scored) {
    extra[s.n.id] = `${formatPercent(s.n.shareChildren)} children · ${formatMeters(s.meters)} to ${s.park.name}${s.high ? "" : " · below median child share"}`;
  }
  for (const p of parks) extra[p.id] = p.detail;
  return shell({
    key: `park:${radiusM}:${gaps.map((g) => g.n.id).join()}`,
    title,
    summary,
    confidence: "Approximate",
    confidenceNote: `Park access is the centroid-to-nearest-park distance, not the share of the neighborhood inside a walk shed. A gap also requires child share at or above ${formatPercent(median)}. ${MEASURED}`,
    steps: [
      {
        title: "Child share",
        detail: "Divided children by total population. High means at or above the median neighborhood.",
      },
      {
        title: "Nearest park",
        detail: "Measured each centroid to the nearest park point in the sample.",
      },
      {
        title: "Gap rule",
        detail: `Kept high-child neighborhoods farther than ${formatMeters(radiusM)}. ${gaps.length} passed. Ranked by child share times distance.`,
      },
    ],
    sources: [SOURCE_NBHD, SOURCE_PARK, SOURCE_DIST],
    rows: list.map((s, i) => ({
      id: s.n.id,
      name: s.n.name,
      primary: formatPercent(s.n.shareChildren) + " children",
      secondary: `${formatMeters(s.meters)} to ${s.park.name}`,
      bar: bar[i],
    })),
    legend: [
      { label: "Larger park gap", color: "#143f38" },
      { label: "Park", color: PINE, hollow: true },
      { label: "Link to nearest park", color: PINE },
    ],
    neighborhoods: nb,
    points,
    lines,
    buffers: [],
    fit: fitOf(
      [...list.map((s) => s.n.center), ...parks.map((p) => [p.lon, p.lat] as LonLat)],
      allCenters(),
    ),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Park-coverage gaps for neighborhoods at or above the median child share, using ${formatMeters(radiusM)} as the access distance.`,
  });
}

function rankNeighborhoods(field: NbhdField, dir: "asc" | "desc"): QueryResult {
  const sorted = [...neighborhoods].sort((a, b) =>
    dir === "desc" ? fieldValue(b, field) - fieldValue(a, field) : fieldValue(a, field) - fieldValue(b, field),
  );
  const noun = FIELD_NOUN[field];
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => ({
      id: n.id,
      value: fieldValue(n, field),
      emphasis: true,
      label: sorted.slice(0, 3).some((s) => s.id === n.id),
    })),
  );
  const bar = bars(sorted.map((n) => fieldValue(n, field)));
  const extra: Record<string, string> = {};
  for (const n of neighborhoods) extra[n.id] = `${formatField(field, fieldValue(n, field))} · pop ${formatNumber(n.pop)}`;
  const top = sorted[0];
  return shell({
    key: `rank:${field}:${dir}`,
    title: `${top.name} ranks ${dir === "desc" ? "highest" : "lowest"} on ${noun}`,
    summary: `${formatField(field, fieldValue(top, field))} in ${top.name}. All 12 neighborhoods are shaded on that measure. The list is in ${dir === "desc" ? "descending" : "ascending"} order.`,
    confidence: "Calculated locally",
    confidenceNote: "This is a sort of the sample attribute. No distance filter was applied.",
    steps: [
      { title: "Read the attribute", detail: `Used ${noun} on each neighborhood.` },
      { title: "Rank", detail: `Sorted all 12 ${dir === "desc" ? "high to low" : "low to high"}.` },
    ],
    sources: [SOURCE_NBHD],
    rows: sorted.map((n, i) => ({
      id: n.id,
      name: n.name,
      primary: formatField(field, fieldValue(n, field)),
      secondary: `Pop ${formatNumber(n.pop)}`,
      bar: bar[i],
    })),
    legend: [
      { label: `Higher ${noun}`, color: "#143f38" },
      { label: `Lower ${noun}`, color: "#e6f2ee" },
    ],
    neighborhoods: nb,
    points: [],
    lines: [],
    buffers: [],
    fit: allCenters(),
    details: detailsFrom(nb, [], extra),
    interpretedAs: `Rank neighborhoods by ${noun}, ${dir === "desc" ? "highest" : "lowest"} first.`,
  });
}

function whereNeighborhoods(field: NbhdField, op: "gt" | "lt" | "gte" | "lte", value: number): QueryResult {
  const pass = (n: Neighborhood) => (op === "gt" ? fieldValue(n, field) > value : op === "gte" ? fieldValue(n, field) >= value : op === "lte" ? fieldValue(n, field) <= value : fieldValue(n, field) < value);
  const kept = neighborhoods.filter(pass).sort((a, b) =>
    (op === "lt" || op === "lte") ? fieldValue(a, field) - fieldValue(b, field) : fieldValue(b, field) - fieldValue(a, field),
  );
  const noun = FIELD_NOUN[field];
  const cmp = { gt: "over", lt: "under", gte: "at least", lte: "at most" }[op];
  const shown = formatField(field, field === "share65" || field === "shareChildren" ? value : value);
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => ({
      id: n.id,
      value: pass(n) ? fieldValue(n, field) : null,
      emphasis: pass(n),
      label: kept.slice(0, 4).some((k) => k.id === n.id),
    })),
  );
  const bar = bars(kept.map((n) => Math.abs(fieldValue(n, field))));
  const extra: Record<string, string> = {};
  for (const n of neighborhoods) {
    extra[n.id] = `${formatField(field, fieldValue(n, field))}${pass(n) ? " · matches" : " · outside the filter"}`;
  }
  return shell({
    key: `where:${field}:${op}:${value}`,
    title: kept.length
      ? `${kept.length} ${kept.length === 1 ? "neighborhood is" : "neighborhoods are"} ${cmp} ${shown}`
      : `No neighborhood is ${cmp} ${shown}`,
    summary: kept.length
      ? `Filtered on ${noun}. ${kept[0].name} is the ${(op === "lt" || op === "lte") ? "lowest" : "highest"} match at ${formatField(field, fieldValue(kept[0], field))}.`
      : "No sample neighborhood matches that filter. Context outlines remain visible.",
    confidence: "Calculated locally",
    confidenceNote: "Direct comparison against the sample attribute. No spatial join.",
    steps: [
      { title: "Filter", detail: `Kept neighborhoods with ${noun} ${cmp} ${shown}.` },
      { title: "Rank matches", detail: `${kept.length} of 12 neighborhoods passed.` },
    ],
    sources: [SOURCE_NBHD],
    rows: kept.map((n, i) => ({
      id: n.id,
      name: n.name,
      primary: formatField(field, fieldValue(n, field)),
      secondary: `Pop ${formatNumber(n.pop)}`,
      bar: bar[i] ?? 0,
    })),
    legend: [
      { label: "Matches the filter", color: "#2c6b5e" },
      { label: "Does not match", color: "#e4ece8" },
    ],
    neighborhoods: nb,
    points: [],
    lines: [],
    buffers: [],
    fit: fitOf(kept.map((n) => n.center), allCenters()),
    details: detailsFrom(nb, [], extra),
    interpretedAs: `Neighborhoods with ${noun} ${cmp} ${shown}.`,
  });
}

function zoneDistance(target: "clinics" | "parks" | "warehouse", dir: "asc" | "desc"): QueryResult {
  const targets = target === "clinics" ? clinics : target === "parks" ? parks : [warehouse];
  const label = target === "warehouse" ? "the warehouse" : target === "clinics" ? "a clinic" : "a park";
  const scored = neighborhoods.map((n) => {
    const near = nearestPlace(n.center, targets)!;
    return { n, meters: near.meters, place: near.place };
  });
  scored.sort((a, b) => (dir === "desc" ? b.meters - a.meters : a.meters - b.meters));
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => ({
      id: n.id,
      value: scored.find((s) => s.n.id === n.id)!.meters,
      emphasis: true,
      label: scored.slice(0, 3).some((s) => s.n.id === n.id),
    })),
  );
  const points =
    target === "clinics" ? clinics.map((c) => asClinic(c)) : target === "parks" ? parks.map((p) => asPark(p)) : [asWarehouse()];
  const lines = scored.slice(0, 5).map((s, i) => ({
    id: `z-${i}`,
    coordinates: [s.n.center, [s.place.lon, s.place.lat]] as LonLat[],
  }));
  const bar = bars(scored.map((s) => s.meters));
  const extra: Record<string, string> = {};
  for (const s of scored) extra[s.n.id] = `${formatMeters(s.meters)} to ${s.place.name}`;
  const top = scored[0];
  return shell({
    key: `zone:${target}:${dir}`,
    title: `${top.n.name} is ${dir === "desc" ? "farthest from" : "closest to"} ${label}`,
    summary: `${formatMeters(top.meters)} from ${top.place.name}, measured at the centroid. Shading follows that distance for every neighborhood.`,
    confidence: "Calculated locally",
    confidenceNote: MEASURED,
    steps: [
      { title: "Nearest target", detail: `Distance from each centroid to the nearest ${label}.` },
      { title: "Rank", detail: dir === "desc" ? "Longest distance first." : "Shortest distance first." },
    ],
    sources: [SOURCE_NBHD, target === "parks" ? SOURCE_PARK : target === "clinics" ? SOURCE_CLINIC : SOURCE_WH, SOURCE_DIST],
    rows: scored.map((s, i) => ({
      id: s.n.id,
      name: s.n.name,
      primary: formatMeters(s.meters),
      secondary: s.place.name,
      bar: bar[i],
    })),
    legend: [
      { label: "Farther", color: "#143f38" },
      { label: "Closer", color: "#e6f2ee" },
    ],
    neighborhoods: nb,
    points,
    lines,
    buffers: [],
    fit: allCenters(),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Neighborhoods ranked by distance to ${label}.`,
  });
}

function drawKind(kind: PointKind, list: Place[], ctx: Context, strongIds?: Set<string>): MapPoint[] {
  if (kind === "clinics") return list.map((p) => asClinic(p, strongIds ? strongIds.has(p.id) : true));
  if (kind === "parks") return list.map((p) => asPark(p, strongIds ? strongIds.has(p.id) : true));
  if (kind === "warehouse") return [asWarehouse()];
  if (kind === "customers") {
    const vols = customers.map((c) => c.orderVolume ?? 0);
    const min = Math.min(...vols);
    const max = Math.max(...vols);
    return customers.map((c) =>
      asCustomer(c, norm(c.orderVolume ?? 0, min, max), strongIds ? strongIds.has(c.id) : true),
    );
  }
  const uploads = placesFor("upload", ctx);
  return uploads.map((p) => asUpload(p, strongIds ? strongIds.has(p.id) : true));
}

function pointsWithin(
  subject: PointKind,
  target: PointKind,
  mode: "within" | "beyond",
  meters: number,
  note: string | null,
  ctx: Context,
): QueryResult {
  const subjects = placesFor(subject, ctx);
  const targets = placesFor(target, ctx);
  if (!subjects.length || !targets.length) {
    return explainResult(
      subject === "upload" || target === "upload"
        ? "Upload a CSV or GeoJSON with latitude and longitude first. The file stays in this tab."
        : "That step needs both layers, and one of them is empty.",
    );
  }
  const scored = subjects.map((s) => {
    const near = nearestPlace([s.lon, s.lat], targets)!;
    return { s, meters: near.meters, t: near.place };
  });
  const kept = scored.filter((s) => (mode === "within" ? s.meters <= meters : s.meters > meters));
  kept.sort((a, b) => (mode === "within" ? b.meters - a.meters : b.meters - a.meters));
  const strong = new Set(kept.map((k) => k.s.id));
  const points = [
    ...drawKind(subject, subjects, ctx, strong),
    ...(subject !== target ? drawKind(target, targets, ctx) : []),
  ];
  const nb = paintNeighborhoods(neighborhoods.map((n) => ({ id: n.id, value: null, emphasis: false, label: false })));
  const buffers =
    targets.length <= 3
      ? targets.map((t) => ({ id: `b-${t.id}`, ring: circleRing([t.lon, t.lat], meters) }))
      : [];
  const lines = kept.slice(0, 8).map((k, i) => ({
    id: `pw-${i}`,
    coordinates: [
      [k.s.lon, k.s.lat],
      [k.t.lon, k.t.lat],
    ] as LonLat[],
  }));
  const word = mode === "within" ? "within" : "beyond";
  const bar = bars(kept.map((k) => k.meters));
  const extra: Record<string, string> = {};
  for (const s of scored) extra[s.s.id] = `${formatMeters(s.meters)} to ${s.t.name}`;
  return shell({
    key: `pw:${subject}:${target}:${mode}:${meters}:${kept.length}`,
    title: `${kept.length} ${subject} ${word} ${formatMeters(meters)} of ${target}`,
    summary: kept.length
      ? `Compared each ${subject.replace(/s$/, "")} to the nearest ${target.replace(/s$/, "")}. ${kept.length} of ${subjects.length} passed.`
      : `None of the ${subjects.length} ${subject} are ${word} ${formatMeters(meters)}.`,
    confidence: note ? "Approximate" : "Calculated locally",
    confidenceNote: note ? `${note} ${MEASURED}` : MEASURED,
    steps: [
      { title: "Nearest pair", detail: `Distance from each ${subject} feature to the nearest ${target} feature.` },
      { title: "Threshold", detail: `${word} ${formatMeters(meters)}. ${kept.length} of ${subjects.length} passed.` },
    ],
    sources: [SOURCE_DIST],
    rows: kept.slice(0, 12).map((k, i) => ({
      id: k.s.id,
      name: k.s.name,
      primary: formatMeters(k.meters),
      secondary: k.t.name,
      bar: bar[i] ?? 0,
    })),
    legend: [
      { label: subject, color: subject === "clinics" ? INK : PINE },
      { label: target, color: INK },
    ],
    neighborhoods: nb,
    points,
    lines,
    buffers,
    fit: fitOf(
      kept.length
        ? kept.flatMap((k) => [
            [k.s.lon, k.s.lat] as LonLat,
            [k.t.lon, k.t.lat] as LonLat,
          ])
        : subjects.map((s) => [s.lon, s.lat] as LonLat),
      allCenters(),
    ),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `${subject} ${word} ${formatMeters(meters)} of ${target}.`,
  });
}

function distanceRank(subject: PointKind, target: PointKind, dir: "asc" | "desc", ctx: Context): QueryResult {
  const subjects = placesFor(subject, ctx);
  const targets = placesFor(target, ctx);
  if (!subjects.length || !targets.length) {
    return explainResult("Upload a CSV or GeoJSON with latitude and longitude first. The file stays in this tab.");
  }
  const scored = subjects.map((s) => {
    const near = nearestPlace([s.lon, s.lat], targets)!;
    return { s, meters: near.meters, t: near.place };
  });
  scored.sort((a, b) => (dir === "desc" ? b.meters - a.meters : a.meters - b.meters));
  const top = scored.slice(0, 8);
  const strong = new Set(top.map((t) => t.s.id));
  const points = [...drawKind(subject, subjects, ctx, strong), ...drawKind(target, targets, ctx)];
  const nb = paintNeighborhoods(neighborhoods.map((n) => ({ id: n.id, value: null, emphasis: false, label: false })));
  const lines = top.slice(0, 5).map((s, i) => ({
    id: `dr-${i}`,
    coordinates: [
      [s.s.lon, s.s.lat],
      [s.t.lon, s.t.lat],
    ] as LonLat[],
  }));
  const bar = bars(top.map((s) => s.meters));
  const extra: Record<string, string> = {};
  for (const s of scored) extra[s.s.id] = `${formatMeters(s.meters)} to ${s.t.name}`;
  return shell({
    key: `dr:${subject}:${target}:${dir}`,
    title: `${scored[0].s.name} is ${dir === "desc" ? "farthest from" : "closest to"} ${scored[0].t.name}`,
    summary: `${formatMeters(scored[0].meters)}. Ranked all ${subjects.length} ${subject} by distance to the nearest ${target.replace(/s$/, "")}.`,
    confidence: "Calculated locally",
    confidenceNote: MEASURED,
    steps: [
      { title: "Distance", detail: `Each ${subject} feature to the nearest ${target} feature.` },
      { title: "Rank", detail: dir === "desc" ? "Farthest first. The list shows eight." : "Closest first. The list shows eight." },
    ],
    sources: [SOURCE_DIST],
    rows: top.map((s, i) => ({
      id: s.s.id,
      name: s.s.name,
      primary: formatMeters(s.meters),
      secondary: s.t.name,
      bar: bar[i],
    })),
    legend: [{ label: dir === "desc" ? "Farthest links" : "Closest links", color: PINE }],
    neighborhoods: nb,
    points,
    lines,
    buffers: [],
    fit: fitOf(
      top.flatMap((s) => [
        [s.s.lon, s.s.lat] as LonLat,
        [s.t.lon, s.t.lat] as LonLat,
      ]),
      allCenters(),
    ),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `${subject} ranked by distance to ${target}.`,
  });
}

function pointsInZone(zoneId: string, subject: PointKind, ctx: Context): QueryResult {
  const zone = neighborhoods.find((n) => n.id === zoneId);
  const pts = placesFor(subject, ctx);
  if (!zone) return explainResult("That neighborhood is not in the sample.");
  if (!pts.length) {
    return explainResult("Upload a CSV or GeoJSON with latitude and longitude first. The file stays in this tab.");
  }
  const inside = pts.filter((p) => pointInRing([p.lon, p.lat], zone.ring));
  const strong = new Set(inside.map((p) => p.id));
  const points = drawKind(subject, pts, ctx, strong);
  const nb = paintNeighborhoods(
    neighborhoods.map((n) => ({
      id: n.id,
      value: n.id === zone.id ? 1 : null,
      emphasis: n.id === zone.id,
      label: n.id === zone.id,
    })),
  );
  const extra: Record<string, string> = {};
  extra[zone.id] = `${inside.length} ${subject} inside`;
  for (const p of pts) extra[p.id] = strong.has(p.id) ? `Inside ${zone.name}` : `Outside ${zone.name}`;
  return shell({
    key: `inz:${zoneId}:${subject}:${inside.length}`,
    title: `${inside.length} ${subject} in ${zone.name}`,
    summary: `Tested ${pts.length} points against the ${zone.name} polygon. ${inside.length} ${inside.length === 1 ? "falls" : "fall"} inside. Points were not counted on the boundary in any special way — the standard even-odd test decides.`,
    confidence: "Calculated locally",
    confidenceNote: "Point-in-polygon on the illustrative neighborhood shape. A point just outside the drawn outline is excluded even if a resident would call it the same area.",
    steps: [
      { title: "Polygon test", detail: `Ran an even-odd point-in-polygon test on ${zone.name}.` },
      { title: "Count", detail: `${inside.length} of ${pts.length} ${subject} are inside.` },
    ],
    sources: [SOURCE_NBHD, SOURCE_DIST],
    rows: inside.slice(0, 12).map((p) => ({
      id: p.id,
      name: p.name,
      primary: p.detail || subject,
      secondary: zone.name,
      bar: 1,
    })),
    legend: [
      { label: zone.name, color: "#2c6b5e" },
      { label: "Inside", color: PINE },
    ],
    neighborhoods: nb,
    points,
    lines: [],
    buffers: [],
    fit: zone.ring,
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Count ${subject} inside ${zone.name}.`,
  });
}

function countByZone(subject: PointKind, ctx: Context): QueryResult {
  const pts = placesFor(subject, ctx);
  if (!pts.length) {
    return explainResult("Upload a CSV or GeoJSON with latitude and longitude first. The file stays in this tab.");
  }
  const counts = neighborhoods.map((n) => ({
    n,
    count: pts.filter((p) => pointInRing([p.lon, p.lat], n.ring)).length,
  }));
  counts.sort((a, b) => b.count - a.count);
  const nb = paintNeighborhoods(
    counts.map((c) => ({ id: c.n.id, value: c.count, emphasis: true, label: counts.slice(0, 3).some((x) => x.n.id === c.n.id) })),
  );
  const points = drawKind(subject, pts, ctx);
  const bar = bars(counts.map((c) => c.count));
  const extra: Record<string, string> = {};
  for (const c of counts) extra[c.n.id] = `${c.count} ${subject}`;
  const missed = pts.length - counts.reduce((s, c) => s + c.count, 0);
  return shell({
    key: `count:${subject}:${counts.map((c) => c.count).join()}`,
    title: `${counts[0].n.name} contains the most ${subject}`,
    summary: `${counts[0].count} of ${pts.length}. ${missed > 0 ? `${missed} fall outside every neighborhood outline.` : "Every point falls inside some neighborhood."}`,
    confidence: "Calculated locally",
    confidenceNote: "Counts use point-in-polygon. Overlapping sample outlines could count one point twice; these invented shapes are not administrative boundaries.",
    steps: [
      { title: "Assign points", detail: `Tested each ${subject} feature against all 12 neighborhood polygons.` },
      { title: "Rank", detail: "Sorted neighborhoods by that count." },
    ],
    sources: [SOURCE_NBHD],
    rows: counts.map((c, i) => ({
      id: c.n.id,
      name: c.n.name,
      primary: `${c.count}`,
      secondary: subject,
      bar: bar[i],
    })),
    legend: [
      { label: "More points", color: "#143f38" },
      { label: "Fewer points", color: "#e6f2ee" },
    ],
    neighborhoods: nb,
    points,
    lines: [],
    buffers: [],
    fit: allCenters(),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Count of ${subject} in each neighborhood.`,
  });
}

function show(layers: PointKind[] | ["neighborhoods"], ctx: Context): QueryResult {
  const names = layers as string[];
  const wantNbhd = names.includes("neighborhoods") || names.length === 0;
  const kinds = names.filter((name) => name !== "neighborhoods") as PointKind[];
  const places = kinds.flatMap((kind) => placesFor(kind, ctx));
  const points = kinds.flatMap((kind) => drawKind(kind, placesFor(kind, ctx), ctx));
  const nb = paintNeighborhoods(neighborhoods.map((n) => ({ id: n.id, value: wantNbhd ? n.pop : null, emphasis: wantNbhd, label: false })));
  const rows: ResultRow[] = wantNbhd ? [...neighborhoods].sort((a, b) => b.pop - a.pop).map((n) => ({
    id: n.id, name: n.name, primary: `Pop ${formatNumber(n.pop)}`, secondary: formatMoney(n.medianIncome), bar: n.pop / Math.max(...neighborhoods.map((v) => v.pop)),
  })) : places.map((p) => ({ id: p.id, name: p.name, primary: p.kind === "upload" ? "Unverified user point" : p.detail, secondary: `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`, bar: 0.6 }));
  const extra = Object.fromEntries(places.map((p) => [p.id, `${p.detail} · ${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`]));
  const onlyUploads = kinds.length === 1 && kinds[0] === "upload";
  const colors: Record<PointKind, LegendItem> = {
    clinics: { label: "Fictional clinic", color: INK },
    parks: { label: "Illustrative park point", color: PINE, hollow: true },
    customers: { label: "Fictional customer", color: PINE },
    warehouse: { label: "Fictional warehouse", color: PINE },
    upload: { label: "Unverified uploaded point", color: "#8f3d32" },
  };
  return shell({
    key: `show:${layers.join()}`,
    title: onlyUploads ? `${points.length} uploaded points — unverified` : `${rows.length} sample records, no filter`,
    summary: `Showing all ${rows.length} requested records. No distance or attribute filter was applied. Neighborhood outlines are illustrative context only.`,
    confidence: "Calculated locally",
    confidenceNote: "Display only; a successfully parsed point is not a verified location or an approved public record.",
    steps: [{ title: "Show", detail: `Turned on ${layers.join(", ")}. All requested records are listed and available for local export.` }],
    sources: [SOURCE_NBHD], rows,
    legend: [{ label: "Invented neighborhood", color: "#6eaea0" }, ...kinds.map((kind) => colors[kind])],
    neighborhoods: nb, points, lines: [], buffers: [],
    fit: points.length ? points.map((p) => [p.lon, p.lat] as LonLat) : allCenters(),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `Show ${layers.join(", ")}.`,
  });
}

function newSite(demand: "seniors" | "children" | "low_income", supply: "clinics" | "parks"): QueryResult {
  const supplyPts = supply === "clinics" ? clinics : parks;
  const demandLabel =
    demand === "seniors" ? "share of residents 65+" : demand === "children" ? "child share" : "lower income";
  const raw = neighborhoods.map((n) => {
    const near = nearestPlace(n.center, supplyPts)!;
    const d =
      demand === "seniors" ? n.share65 : demand === "children" ? n.shareChildren : 1 / n.medianIncome;
    return { n, meters: near.meters, place: near.place, d };
  });
  const dMin = Math.min(...raw.map((r) => r.d));
  const dMax = Math.max(...raw.map((r) => r.d));
  const mMin = Math.min(...raw.map((r) => r.meters));
  const mMax = Math.max(...raw.map((r) => r.meters));
  const scored = raw
    .map((r) => ({ ...r, score: norm(r.d, dMin, dMax) * norm(r.meters, mMin, mMax) }))
    .sort((a, b) => b.score - a.score);
  const top = scored.slice(0, 4);
  const topIds = new Set(top.map((t) => t.n.id));
  const nb = paintNeighborhoods(
    scored.map((s) => ({
      id: s.n.id,
      value: topIds.has(s.n.id) ? s.score : null,
      emphasis: topIds.has(s.n.id),
      label: top.slice(0, 3).some((t) => t.n.id === s.n.id),
    })),
  );
  const points = supply === "clinics" ? clinics.map((c) => asClinic(c)) : parks.map((p) => asPark(p));
  const lines = top.map((s, i) => ({
    id: `site-${i}`,
    coordinates: [s.n.center, [s.place.lon, s.place.lat]] as LonLat[],
  }));
  const bar = bars(top.map((t) => t.score));
  const extra: Record<string, string> = {};
  for (const s of scored) {
    extra[s.n.id] = `Score ${s.score.toFixed(2)} · ${formatMeters(s.meters)} to ${s.place.name}`;
  }
  const supplyNoun = supply === "clinics" ? "clinic" : "park";
  return shell({
    key: `site:${demand}:${supply}`,
    title: `${top[0].n.name} scores highest for a new ${supplyNoun}`,
    summary: `The score multiplies ${demandLabel} by distance to the nearest existing ${supplyNoun}. Both parts are scaled from 0 to 1 across the 12 neighborhoods, then multiplied. ${top[0].n.name} is ${formatMeters(top[0].meters)} from ${top[0].place.name}. This is a ranking aid, not a forecast of demand or cost.`,
    confidence: "Approximate",
    confidenceNote: `Equal weights. No travel network, no capacity, no land cost. ${MEASURED}`,
    steps: [
      { title: "Demand", detail: `Scaled ${demandLabel} from the lowest neighborhood to the highest.` },
      { title: "Supply distance", detail: `Scaled centroid distance to the nearest ${supplyNoun}.` },
      { title: "Score", detail: "Multiplied the two scaled values. Highest four are listed and shaded." },
    ],
    sources: [SOURCE_NBHD, supply === "clinics" ? SOURCE_CLINIC : SOURCE_PARK, SOURCE_DIST],
    rows: top.map((s, i) => ({
      id: s.n.id,
      name: s.n.name,
      primary: `Score ${s.score.toFixed(2)}`,
      secondary: `${formatMeters(s.meters)} to ${s.place.name}`,
      bar: bar[i],
    })),
    legend: [
      { label: "Higher score", color: "#143f38" },
      { label: `Existing ${supplyNoun}`, color: supply === "clinics" ? INK : PINE, hollow: supply === "parks" },
    ],
    neighborhoods: nb,
    points,
    lines,
    buffers: [],
    fit: fitOf(
      [...top.map((t) => t.n.center), ...supplyPts.map((p) => [p.lon, p.lat] as LonLat)],
      allCenters(),
    ),
    details: detailsFrom(nb, points, extra),
    interpretedAs: `New ${supplyNoun} score = scaled ${demandLabel} × scaled distance to the nearest existing ${supplyNoun}.`,
  });
}

export function run(intent: Intent, ctx: Context): QueryResult {
  switch (intent.kind) {
    case "senior_clinic_gap":
      return seniorGap(intent.minMeters, intent.note);
    case "customers_near_warehouse":
      return customersNear(intent.meters, intent.note);
    case "park_child_gap":
      return parkGap(intent.radiusM);
    case "rank_neighborhoods":
      return rankNeighborhoods(intent.field, intent.dir);
    case "neighborhoods_where":
      return whereNeighborhoods(intent.field, intent.op, intent.value);
    case "points_within":
      return pointsWithin(intent.subject, intent.target, intent.mode, intent.meters, intent.note, ctx);
    case "distance_rank":
      return distanceRank(intent.subject, intent.target, intent.dir, ctx);
    case "zone_distance":
      return zoneDistance(intent.target, intent.dir);
    case "points_in_zone":
      return pointsInZone(intent.zoneId, intent.subject, ctx);
    case "count_by_zone":
      return countByZone(intent.subject, ctx);
    case "show":
      return show(intent.layers, ctx);
    case "coverage_new_site":
      return newSite(intent.demand, intent.supply);
    case "upload_near": {
      if (!ctx.upload.length) {
        return explainResult(
          "Upload a CSV or GeoJSON with latitude and longitude first. The file stays in this browser tab and is not sent with the question.",
        );
      }
      return pointsWithin("upload", intent.target, intent.mode, intent.meters, intent.note, ctx);
    }
  }
}

export function tryAnswer(question: string, ctx: Context): QueryResult | null {
  const intent = interpret(question);
  if (!intent) return null;
  const result = run(intent, ctx);
  return result;
}
