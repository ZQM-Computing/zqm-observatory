import { neighborhoods } from "./data.js";

export type NbhdField =
  | "share65"
  | "shareChildren"
  | "medianIncome"
  | "broadband"
  | "pop"
  | "pop65"
  | "children";

export type PointKind = "clinics" | "parks" | "customers" | "warehouse" | "upload";

export type Intent =
  | { kind: "senior_clinic_gap"; minMeters: number; note: string | null }
  | { kind: "customers_near_warehouse"; meters: number; note: string | null }
  | { kind: "park_child_gap"; radiusM: number }
  | { kind: "rank_neighborhoods"; field: NbhdField; dir: "asc" | "desc" }
  | { kind: "neighborhoods_where"; field: NbhdField; op: "gt" | "lt" | "gte" | "lte"; value: number }
  | {
      kind: "points_within";
      subject: PointKind;
      target: PointKind;
      mode: "within" | "beyond";
      meters: number;
      note: string | null;
    }
  | { kind: "distance_rank"; subject: PointKind; target: PointKind; dir: "asc" | "desc" }
  | { kind: "zone_distance"; target: "clinics" | "parks" | "warehouse"; dir: "asc" | "desc" }
  | { kind: "points_in_zone"; zoneId: string; subject: PointKind }
  | { kind: "count_by_zone"; subject: PointKind }
  | { kind: "show"; layers: PointKind[] | ["neighborhoods"] }
  | { kind: "coverage_new_site"; demand: "seniors" | "children" | "low_income"; supply: "clinics" | "parks" }
  | {
      kind: "upload_near";
      target: "clinics" | "parks" | "warehouse";
      mode: "within" | "beyond";
      meters: number;
      note: string | null;
    };

export const EXAMPLES: { label: string; question: string }[] = [
  {
    label: "Seniors far from clinics",
    question:
      "Which neighborhoods have the highest share of residents over 65 and are more than 1 km from the nearest clinic?",
  },
  {
    label: "Customers near the warehouse",
    question: "Show customers within 1.5 km of the warehouse and color them by order volume.",
  },
  {
    label: "Park gaps for children",
    question: "Where are the gaps in park coverage for neighborhoods with a high child population?",
  },
  {
    label: "Broadband under 80%",
    question: "Which neighborhoods have broadband under 80%?",
  },
  {
    label: "Where to add a clinic",
    question: "Where should we add a clinic for older residents?",
  },
];

export const DEFAULT_QUESTION = EXAMPLES[0].question;

const FIELDS: NbhdField[] = [
  "share65",
  "shareChildren",
  "medianIncome",
  "broadband",
  "pop",
  "pop65",
  "children",
];

const POINT_KINDS: PointKind[] = ["clinics", "parks", "customers", "warehouse", "upload"];

function normalize(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/(\d),(?=\d{3}(?:\D|$))/g, "$1")
    .replace(/[?!,;:]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractDistance(q: string): { meters: number; note: string | null } | null {
  const m = q.match(
    /(\d+(?:\.\d+)?)\s*(kilometers|kilometer|km|meters|meter|miles|mile|mi|minutes|minute|min)\b/,
  );
  if (!m) return null;
  const n = Number(m[1]);
  if (!Number.isFinite(n) || n <= 0) return null;
  const u = m[2];
  if (u.startsWith("km") || u.startsWith("kilometer")) return { meters: n * 1000, note: null };
  if (u === "mi" || u === "mile" || u === "miles") return { meters: n * 1609.344, note: null };
  if (u.startsWith("min")) {
    return {
      meters: n * 500,
      note: `${n} minutes was converted to straight-line distance at 30 km/h (${(n * 0.5).toFixed(n * 0.5 < 10 ? 1 : 0)} km). This is not a routed drive time.`,
    };
  }
  return { meters: n, note: null };
}

function extractPlainNumber(q: string): number | null {
  const cleaned = q
    .replace(/over\s*65\+?|65\s*\+|age\s*65|residents\s*65|older than\s*65/g, " ")
    .replace(
      /(\d+(?:\.\d+)?)\s*(kilometers|kilometer|km|meters|meter|miles|mile|mi|minutes|minute|min)\b/g,
      " ",
    );
  const k = cleaned.match(/(\d+(?:\.\d+)?)\s*k\b/);
  if (k) return Number(k[1]) * 1000;
  const m = cleaned.match(/(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)%?/);
  if (!m) return null;
  return Number(m[1].replace(/,/g, ""));
}

function detectField(q: string): NbhdField | null {
  const share = /share|percent|%/.test(q);
  if (/broadband|internet/.test(q)) return "broadband";
  if (/income|wealth|poverty|affluent|low-income|low income/.test(q)) return "medianIncome";
  if (/child|kid|youth/.test(q)) return share ? "shareChildren" : "children";
  if (/65|senior|elder|older/.test(q)) return share ? "share65" : "pop65";
  if (/population|populous|residents/.test(q)) return "pop";
  return null;
}

function detectKinds(q: string): PointKind[] {
  const found: PointKind[] = [];
  if (/clinic|health center|doctor|hospital|fqhc|urgent|pediatric/.test(q)) found.push("clinics");
  if (/park|green space|playground/.test(q)) found.push("parks");
  if (/customer|order volume|delivery|stops?\b/.test(q)) found.push("customers");
  if (/warehouse|depot/.test(q)) found.push("warehouse");
  if (/upload|my file|my points|my locations|my data|my sites|these points|uploaded/.test(q)) {
    found.push("upload");
  }
  return found;
}

function matchZone(q: string): { id: string; name: string } | null {
  const sorted = [...neighborhoods].sort((a, b) => b.name.length - a.name.length);
  return sorted.find((n) => q.includes(n.name.toLowerCase())) ?? null;
}

function clampMeters(n: number): number {
  if (!Number.isFinite(n)) return 1000;
  return Math.min(100000, Math.max(50, n));
}

export function interpret(raw: string): Intent | null {
  const q = normalize(raw);
  if (q.length < 3 || q.length > 500) return null;
  // These need capabilities or boundary semantics absent from this demo.
  if (/\b(minutes?|mins?|drive|driving|walking|walk|route|routing|road|traffic|density|census|safe|safety|accessible|accessibility|open now|live|current|real[- ]time|volusia|daytona|deland)\b/.test(q)) return null;
  if (/\bat (least|most)\b/.test(q) && /\b(km|kilometers?|meters?|miles?|mi)\b/.test(q)) return null;
  if (/\b(between|except|not|isn't|aren't|and|or)\b/.test(q)) {
    const cleaned = q.replace(/and (?:are )?(?:more than|color them by order volume)/g, "");
    if (/\b(between|except|not|isn't|aren't|and|or)\b/.test(cleaned)) return null;
  }
  const distance = extractDistance(q);
  if (distance && (distance.meters < 50 || distance.meters > 100000 || /-\s*\d+(?:\.\d+)?\s*(?:km|m|mi)/.test(q))) return null;
  const kinds = detectKinds(q);
  const field = detectField(q);
  const zone = matchZone(q);
  // Validate the whole location phrase: "Downtown Boston" is not our Downtown.
  for (const location of q.matchAll(/\b(in|near)\s+(.+?)(?=\s+(?:within|more than|less than|from|with|for|and|by)\b|$)/g)) {
    const place = location[2].replace(/^the /, "");
    const knownZone = neighborhoods.some((n) => place === n.name.toLowerCase());
    const knownArea = /^(sample|providence|each neighborhood|park coverage|clinic coverage)$/.test(place);
    const knownTarget = location[1] === "near" && /^(?:nearest )?(clinics?|health centers?|doctors?|hospitals?|parks?|green spaces?|playgrounds?|customers?|delivery stops?|stops?|warehouse|depot|my points|my locations|my sites|uploaded points)$/.test(place);
    if (!knownZone && !knownArea && !knownTarget) return null;
  }
  const wantsWithin = /within|inside|closer than|less than|under |near\b/.test(q);
  const wantsBeyond = /more than|farther|further|beyond|outside|at least/.test(q);
  const wantsFar = /farthest|furthest/.test(q);
  const wantsNear = /nearest|closest/.test(q);
  const rankish = /rank|sort|highest|lowest|most|least|top |bottom /.test(q);

  if ((wantsFar || wantsNear) && kinds.length >= 2 && !distance) {
    const relation = q.match(/^(.*?)\b(?:nearest|closest|farthest|furthest)\s+(?:(?:to|from)\s+)?(.+)$/);
    if (!relation) return null;
    const subjects = detectKinds(relation[1]);
    const targets = detectKinds(relation[2]);
    if (subjects.length !== 1 || targets.length !== 1 || subjects[0] === targets[0]) return null;
    return { kind: "distance_rank", subject: subjects[0], target: targets[0], dir: wantsFar ? "desc" : "asc" };
  }

  if (kinds.includes("upload") && (wantsWithin || wantsBeyond || distance || wantsFar || wantsNear)) {
    const target = kinds.includes("warehouse")
      ? "warehouse"
      : kinds.includes("parks")
        ? "parks"
        : "clinics";
    if ((wantsFar || wantsNear) && !wantsWithin && !distance) {
      return {
        kind: "distance_rank",
        subject: "upload",
        target,
        dir: wantsFar ? "desc" : "asc",
      };
    }
    const mode = wantsBeyond && !wantsWithin ? "beyond" : "within";
    return {
      kind: "upload_near",
      target,
      mode,
      meters: clampMeters(distance?.meters ?? 1000),
      note: distance?.note ?? null,
    };
  }

  if (/where should|new clinic|new park|add a clinic|add a park|open a clinic|site for a/.test(q)) {
    const supply: "clinics" | "parks" =
      /park/.test(q) && !/clinic|health/.test(q) ? "parks" : "clinics";
    let demand: "seniors" | "children" | "low_income" = supply === "parks" ? "children" : "seniors";
    if (/child|kid/.test(q)) demand = "children";
    if (/income|equity|poverty|poor|low-income|low income/.test(q)) demand = "low_income";
    if (/senior|65|elder|older/.test(q)) demand = "seniors";
    return { kind: "coverage_new_site", demand, supply };
  }

  if (
    /park/.test(q) &&
    (/gap|coverage|underserv|unserved|access/.test(q) || /child|kid/.test(q))
  ) {
    return { kind: "park_child_gap", radiusM: clampMeters(distance?.meters ?? 800) };
  }

  if (
    /65|senior|elder|older/.test(q) &&
    /clinic|health|doctor|care/.test(q) &&
    (/far|gap|access|beyond|more than|nearest|from|outside/.test(q) || distance)
  ) {
    return {
      kind: "senior_clinic_gap",
      minMeters: clampMeters(distance?.meters ?? 1000),
      note: distance?.note ?? null,
    };
  }

  if (kinds.includes("customers") && kinds.includes("warehouse")) {
    if (wantsBeyond && !wantsWithin && !wantsFar) return { kind: "points_within", subject: "customers", target: "warehouse", mode: "beyond", meters: clampMeters(distance?.meters ?? 1500), note: null };
    if ((wantsFar || wantsNear) && !wantsWithin) {
      return {
        kind: "distance_rank",
        subject: "customers",
        target: "warehouse",
        dir: wantsFar ? "desc" : "asc",
      };
    }
    return {
      kind: "customers_near_warehouse",
      meters: clampMeters(distance?.meters ?? 1500),
      note: distance?.note ?? null,
    };
  }

  if (
    zone &&
    kinds.length &&
    /in |inside|within the|how many/.test(q) &&
    !distance
  ) {
    const subject = kinds.find((k) => k !== "warehouse") ?? kinds[0];
    return { kind: "points_in_zone", zoneId: zone.id, subject };
  }

  if (/each neighborhood|per neighborhood|by neighborhood/.test(q) && kinds.length) {
    return { kind: "count_by_zone", subject: kinds[0] };
  }

  if (
    /neighborhood/.test(q) &&
    (wantsFar || wantsNear || wantsBeyond || wantsWithin) &&
    (kinds.includes("clinics") || kinds.includes("parks") || kinds.includes("warehouse")) &&
    !/65|senior|child|kid/.test(q)
  ) {
    // This operation ranks centroids; threshold filtering is unsupported.
    if (distance) return null;
    const target = kinds.includes("parks")
      ? "parks"
      : kinds.includes("warehouse")
        ? "warehouse"
        : "clinics";
    return { kind: "zone_distance", target, dir: wantsNear && !wantsFar && !wantsBeyond ? "asc" : "desc" };
  }

  const pointKinds = kinds.filter((k) => k !== "upload");
  if (pointKinds.length >= 2 && (wantsWithin || wantsBeyond || distance)) {
    let target: PointKind = pointKinds[1];
    let subject: PointKind = pointKinds[0];
    if (/from (the |a |nearest )?(warehouse|depot)/.test(q)) target = "warehouse";
    else if (/from (the |a |nearest )?(clinic|health|doctor)/.test(q)) target = "clinics";
    else if (/from (the |a |nearest )?(park)/.test(q)) target = "parks";
    else if (/of (the |a |nearest )?(warehouse|depot)/.test(q)) target = "warehouse";
    else if (/of (the |a |nearest )?(clinic|health)/.test(q)) target = "clinics";
    else if (/of (the |a |nearest )?(park)/.test(q)) target = "parks";
    subject = pointKinds.find((k) => k !== target) ?? subject;
    if (subject !== target) {
      return {
        kind: "points_within",
        subject,
        target,
        mode: wantsBeyond && !wantsWithin ? "beyond" : "within",
        meters: clampMeters(distance?.meters ?? 1000),
        note: distance?.note ?? null,
      };
    }
  }

  if ((wantsFar || wantsNear) && pointKinds.length >= 2) {
    return {
      kind: "distance_rank",
      subject: pointKinds[0],
      target: pointKinds[1],
      dir: wantsFar ? "desc" : "asc",
    };
  }

  const op = /at most/.test(q) ? "lte"
    : /at least/.test(q) ? "gte"
    : /under|below|less than|lower than/.test(q) ? "lt"
    : /over|above|more than|greater than|higher than/.test(q) ? "gt" : null;
  const plain = extractPlainNumber(q);
  if (field && op && plain != null && !distance) {
    let value = plain;
    if ((field === "share65" || field === "shareChildren") && (/%|\bpercent(?:age)?\b/.test(q) || value > 1)) value = value / 100;
    return { kind: "neighborhoods_where", field, op, value };
  }

  if (field && (rankish || /which neighborhood/.test(q))) {
    const dir =
      /lowest|least|bottom|smallest|fewest|worst/.test(q) && !/highest|most/.test(q)
        ? "asc"
        : "desc";
    return { kind: "rank_neighborhoods", field, dir };
  }

  if (/^(show|list|map|display)\b/.test(q) || q.startsWith("show me") || q.startsWith("list ")) {
    if (kinds.length) return { kind: "show", layers: kinds };
    if (/neighborhood/.test(q) || /all|everything|layer/.test(q)) {
      return { kind: "show", layers: ["neighborhoods"] };
    }
  }

  return null;
}
