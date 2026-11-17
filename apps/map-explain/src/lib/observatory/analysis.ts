import { distanceMeters, pointInRing } from "../map-explain/geo.js";
import {
  label,
  makeLayer,
  now,
  type Feature,
  type Layer,
  type Position,
} from "./model.js";

export type Analysis = {
  title: string;
  summary: string;
  layer: Layer;
  rows: { id: string; name: string; value: number; detail: string }[];
  methods: string[];
  limitations: string[];
};
const LIMITS = [
  "Spherical straight-line distance, not routed drive or walking time.",
  "Input labels, source permission, completeness, and field conditions are unverified.",
  "Computed scores are screening aids, not a clinical, regulatory, or business determination.",
];
const inputStep = (...layers: Layer[]) => ({
  operation: "input_layers",
  at: now(),
  detail: JSON.stringify(
    layers.map((l) => ({
      id: l.id,
      name: l.name,
      source: l.source,
      prior_steps: l.steps,
    })),
  ),
});
export function pointFeatures(layer: Layer): Feature[] {
  return layer.features.filter((f) => f.geometry.type === "Point");
}
function xy(feature: Feature): Position {
  return feature.geometry.coordinates as Position;
}

export function coverage(
  demand: Layer,
  supply: Layer,
  radius: number,
  weightField: string,
  distanceWeight: number,
  demandWeight: number,
): Analysis {
  if (!Number.isFinite(radius) || radius < 1 || radius > 100000)
    throw new Error("Use a distance from 1 through 100,000 meters.");
  if (
    ![distanceWeight, demandWeight].every(
      (n) => Number.isFinite(n) && n >= 0,
    ) ||
    distanceWeight + demandWeight <= 0
  )
    throw new Error("Scoring weights must be nonnegative and sum above zero.");
  const points = pointFeatures(demand),
    facilities = pointFeatures(supply);
  if (!points.length || !facilities.length)
    throw new Error(
      "Choose demand and supply layers containing Point features.",
    );
  if (demand.id === supply.id)
    throw new Error("Demand and supply must be different layers.");
  const values = points.map((p) =>
    weightField ? Number(p.properties[weightField]) : 1,
  );
  if (
    values.some(
      (v, i) =>
        !Number.isFinite(v) ||
        v < 0 ||
        (weightField &&
          (!["number", "string"].includes(
            typeof points[i].properties[weightField],
          ) ||
            String(points[i].properties[weightField]).trim() === "")),
    )
  )
    throw new Error(
      "Demand weights must be present, finite, and nonnegative for every demand point.",
    );
  const max = Math.max(...values, 1);
  const rows = points
    .map((point, index) => {
      const nearest = facilities
        .map((f) => ({ feature: f, meters: distanceMeters(xy(point), xy(f)) }))
        .sort((a, b) => a.meters - b.meters)[0];
      const gap = nearest.meters > radius;
      const score = gap
        ? (100 *
            ((distanceWeight * Math.min(nearest.meters / radius, 3)) / 3 +
              (demandWeight * values[index]) / max)) /
          (distanceWeight + demandWeight)
        : 0;
      return { point, nearest, gap, score, weight: values[index] };
    })
    .sort((a, b) => b.score - a.score || a.point.id.localeCompare(b.point.id));
  const methods = [
    `Compared ${points.length} demand points against ${facilities.length} supply points. Nonpoint geometries were excluded explicitly.`,
    `Gap means nearest distance > ${radius} m; equality is covered.`,
    `Score = 100 × (${distanceWeight} × min(distance/radius,3)/3 + ${demandWeight} × demand/maxDemand) / ${distanceWeight + demandWeight}; covered points score zero.`,
  ];
  const features: Feature[] = rows.map((r) => ({
    ...structuredClone(r.point),
    properties: {
      ...r.point.properties,
      nearest_m: r.nearest.meters,
      nearest_id: r.nearest.feature.id,
      nearest_name: label(r.nearest.feature),
      gap: r.gap,
      score: r.score,
      demand_weight: r.weight,
    },
  }));
  const layer = makeLayer(
    `${demand.name} coverage`,
    features,
    "derived",
    `Derived from ${demand.source.name} and ${supply.source.name}; all source and publication gates remain open.`,
  );
  layer.steps = [
    inputStep(demand, supply),
    { operation: "point_coverage", at: now(), detail: methods.join(" ") },
  ];
  const gaps = rows.filter((r) => r.gap);
  return {
    title: `${gaps.length} of ${rows.length} demand points beyond ${radius.toLocaleString()} m`,
    summary: `${rows.length - gaps.length} covered; ${gaps.length} gaps; weighted demand in gaps ${gaps.reduce((sum, r) => sum + r.weight, 0).toFixed(2)}. All ${rows.length} point results are retained for inspection and export.`,
    layer,
    rows: rows.map((r) => ({
      id: r.point.id,
      name: label(r.point),
      value: r.score,
      detail: `${Math.round(r.nearest.meters)} m to ${label(r.nearest.feature)} · ${r.gap ? "gap" : "covered"} · demand ${r.weight}`,
    })),
    methods,
    limitations: LIMITS,
  };
}

function inside(feature: Feature, polygon: Feature): boolean {
  const p = xy(feature);
  const rings = polygon.geometry.coordinates as Position[][];
  return (
    pointInRing(p, rings[0]) &&
    !rings.slice(1).some((hole) => pointInRing(p, hole))
  );
}

export function answerProject(question: string, layers: Layer[]): Analysis {
  const q = question
    .trim()
    .toLowerCase()
    .replace(/[.!?]+$/, "");
  if (!q || q.length > 500)
    throw new Error(
      "Use a supported spatial question of at most 500 characters.",
    );
  const escaped = (s: string) =>
    s.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // Match the entire request, not substrings: a derived layer can contain another layer's name.
  const show = layers.find((l) =>
    new RegExp(`^(?:show|map|list) (?:me )?(?:the )?${escaped(l.name)}$`).test(
      q,
    ),
  );
  const pairs = layers
    .flatMap((a) => layers.filter((b) => b.id !== a.id).map((b) => [a, b]))
    .filter(([a, b]) => {
      const x = escaped(a.name),
        y = escaped(b.name);
      return new RegExp(
        `^(?:(?:show )?${x} (?:within|beyond) \\d+(?:\\.\\d+)? (?:km|m|meters?|kilometers?|miles?) (?:of|from) ${y}|count ${x} (?:in|by) ${y}|rank ${x} (?:nearest|farthest) (?:to|from) ${y})$`,
      ).test(q);
    });
  const matched = show ? [show] : pairs.length === 1 ? pairs[0] : [];
  const pair = matched.length === 2 ? matched.map((l) => escaped(l.name)) : [];
  const distancePattern = pair.length
    ? new RegExp(
        `^(?:show )?${pair[0]} (within|beyond) (\\d+(?:\\.\\d+)?) (km|m|meters?|kilometers?|miles?) (?:of|from) ${pair[1]}$`,
      )
    : null;
  const countPattern = pair.length
    ? new RegExp(`^count ${pair[0]} (?:in|by) ${pair[1]}$`)
    : null;
  const nearestPattern = pair.length
    ? new RegExp(`^rank ${pair[0]} (nearest|farthest) (?:to|from) ${pair[1]}$`)
    : null;
  const distance = q.match(
    /\b(\d+(?:\.\d+)?)\s*(km|m|meters?|kilometers?|miles?)\b/,
  );
  if (matched.length === 2 && distance && distancePattern?.test(q)) {
    const meters =
      Number(distance[1]) *
      (distance[2].startsWith("k")
        ? 1000
        : distance[2].startsWith("mile")
          ? 1609.344
          : 1);
    const result = coverage(matched[0], matched[1], meters, "", 1, 0);
    const beyond = /beyond|more than/.test(q);
    result.layer.features = result.layer.features.filter(
      (f) => f.properties.gap === beyond,
    );
    const ids = new Set(result.layer.features.map((f) => f.id));
    result.rows = result.rows.filter((row) => ids.has(row.id));
    result.title = `${result.rows.length} ${matched[0].name} ${beyond ? "beyond" : "within"} ${meters} m of ${matched[1].name}`;
    result.summary =
      "Only matching point records are retained. The map and exports use exactly the same selected features.";
    return result;
  }
  if (matched.length === 2 && countPattern?.test(q)) {
    const points = matched.find((l) => pointFeatures(l).length),
      zones = matched.find((l) =>
        l.features.some((f) => f.geometry.type === "Polygon"),
      );
    if (!points || !zones || points.id === zones.id)
      throw new Error("Count requires one Point layer and one Polygon layer.");
    const features = zones.features
      .filter((f) => f.geometry.type === "Polygon")
      .map((z) => ({
        ...structuredClone(z),
        properties: {
          ...z.properties,
          count: pointFeatures(points).filter((p) => inside(p, z)).length,
        },
      }));
    const layer = makeLayer(
      `${points.name} counts by ${zones.name}`,
      features,
      "derived",
    );
    const methods = [
      "Point-in-polygon with polygon holes excluded. Overlapping polygons can count a point more than once. Boundary points follow ray-casting semantics and need review.",
    ];
    layer.steps = [
      inputStep(points, zones),
      { operation: "point_counts", detail: methods[0], at: now() },
    ];
    return {
      title: `Counts for ${features.length} polygons`,
      summary: `Counted ${pointFeatures(points).length} points from ${points.name}.`,
      layer,
      rows: features.map((f) => ({
        id: f.id,
        name: label(f),
        value: Number(f.properties.count),
        detail: "Point count",
      })),
      methods,
      limitations: LIMITS,
    };
  }
  if (matched.length === 2 && nearestPattern?.test(q)) {
    const a = pointFeatures(matched[0]),
      b = pointFeatures(matched[1]);
    if (!a.length || !b.length)
      throw new Error("Nearest analysis requires two Point layers.");
    const features = a
      .map((p) => {
        const nearest = b
          .map((t) => ({ feature: t, meters: distanceMeters(xy(p), xy(t)) }))
          .sort((x, y) => x.meters - y.meters)[0];
        return {
          ...structuredClone(p),
          properties: {
            ...p.properties,
            nearest_m: nearest.meters,
            nearest_name: label(nearest.feature),
          },
        };
      })
      .sort(
        (x, y) =>
          (Number(x.properties.nearest_m) - Number(y.properties.nearest_m)) *
          (/farthest/.test(q) ? -1 : 1),
      );
    const layer = makeLayer(
      `${matched[0].name} nearest ${matched[1].name}`,
      features,
      "derived",
    );
    const methods = [
      "Compared every subject point with every target point using haversine distance, then ranked by nearest distance.",
    ];
    layer.steps = [
      inputStep(...matched),
      { operation: "nearest", at: now(), detail: methods[0] },
    ];
    return {
      title: `${features.length} nearest-distance results`,
      summary: "Subject and target follow their order in the question.",
      layer,
      rows: features.map((f) => ({
        id: f.id,
        name: label(f),
        value: Number(f.properties.nearest_m),
        detail: `${Math.round(Number(f.properties.nearest_m))} m to ${f.properties.nearest_name}`,
      })),
      methods,
      limitations: LIMITS,
    };
  }
  if (show) {
    const layer = structuredClone(matched[0]);
    return {
      title: `${layer.features.length} features in ${layer.name}`,
      summary: "Display only. No filter or spatial calculation was applied.",
      layer,
      rows: layer.features.map((f) => ({
        id: f.id,
        name: label(f),
        value: 0,
        detail: f.geometry.type,
      })),
      methods: [
        "Read the requested project layer without transforming its features.",
      ],
      limitations: LIMITS,
    };
  }
  throw new Error(
    "That wording is outside the supported patterns. Use an example or the guided Coverage workspace; no result was invented.",
  );
}
