import { blobRing, ringCentroid, type LonLat } from "./geo.js";

export type Neighborhood = {
  id: string;
  name: string;
  ring: LonLat[];
  pop: number;
  pop65: number;
  children: number;
  medianIncome: number;
  broadband: number;
  share65: number;
  shareChildren: number;
  center: LonLat;
};

export type PlaceKind = "clinic" | "park" | "customer" | "warehouse" | "upload";

export type Place = {
  id: string;
  name: string;
  kind: PlaceKind;
  lon: number;
  lat: number;
  detail: string;
  orderVolume?: number;
  acres?: number;
  facility?: string;
};

type Spec = [
  id: string,
  name: string,
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  phase: number,
  pop: number,
  pop65: number,
  children: number,
  income: number,
  broadband: number,
];

const SPECS: Spec[] = [
  ["wanskuck", "Wanskuck", -71.441, 41.852, 0.012, 0.0065, 0.2, 7300, 1210, 1600, 49000, 77],
  ["smith-hill", "Smith Hill", -71.422, 41.837, 0.01, 0.006, 1.1, 8700, 920, 1900, 46000, 79],
  ["mount-hope", "Mount Hope", -71.396, 41.844, 0.011, 0.0062, 0.6, 6400, 1480, 1100, 58000, 86],
  ["olneyville", "Olneyville", -71.458, 41.823, 0.012, 0.0065, 2.0, 9800, 890, 2600, 41000, 76],
  ["federal-hill", "Federal Hill", -71.43, 41.822, 0.01, 0.006, 0.9, 8200, 980, 1400, 62000, 88],
  ["college-hill", "College Hill", -71.398, 41.83, 0.01, 0.0064, 1.7, 9600, 1100, 900, 92000, 96],
  ["west-end", "West End", -71.446, 41.809, 0.012, 0.0062, 0.3, 12400, 1450, 3100, 48000, 81],
  ["downtown", "Downtown", -71.414, 41.824, 0.009, 0.0055, 2.4, 5400, 410, 420, 78000, 94],
  ["fox-point", "Fox Point", -71.393, 41.816, 0.0095, 0.0058, 1.2, 7100, 860, 980, 74000, 93],
  ["south-providence", "South Providence", -71.419, 41.803, 0.012, 0.006, 0.8, 14200, 1680, 4200, 36000, 72],
  ["elmwood", "Elmwood", -71.426, 41.79, 0.011, 0.006, 1.5, 11100, 1540, 2800, 44000, 78],
  ["washington-park", "Washington Park", -71.397, 41.784, 0.012, 0.0062, 0.5, 6900, 1320, 1500, 52000, 80],
];

export const neighborhoods: Neighborhood[] = SPECS.map((s) => {
  const ring = blobRing(s[2], s[3], s[4], s[5], s[6]);
  const pop = s[7];
  return {
    id: s[0],
    name: s[1],
    ring,
    pop,
    pop65: s[8],
    children: s[9],
    medianIncome: s[10],
    broadband: s[11],
    share65: s[8] / pop,
    shareChildren: s[9] / pop,
    center: ringCentroid(ring),
  };
});

function clinic(id: string, name: string, facility: string, lon: number, lat: number): Place {
  return { id, name, kind: "clinic", facility, lon, lat, detail: facility };
}

function park(id: string, name: string, acres: number, lon: number, lat: number): Place {
  return {
    id,
    name,
    kind: "park",
    acres,
    lon,
    lat,
    detail: `${acres} acres, approximate point`,
  };
}

function stop(n: number, street: string, volume: number, lon: number, lat: number): Place {
  const name = `Stop ${String(n).padStart(2, "0")} · ${street}`;
  return {
    id: `stop-${n}`,
    name,
    kind: "customer",
    orderVolume: volume,
    lon,
    lat,
    detail: `${volume} orders`,
  };
}

export const clinics: Place[] = [
  clinic("c-atwells", "Atwells Family Clinic", "FQHC", -71.427, 41.822),
  clinic("c-kennedy", "Kennedy Plaza Urgent Care", "Urgent care", -71.413, 41.824),
  clinic("c-thayer", "Thayer Street Health", "Primary care", -71.4, 41.829),
  clinic("c-wickenden", "Wickenden Primary", "Primary care", -71.395, 41.818),
  clinic("c-olney", "Olneyville Health Center", "FQHC", -71.455, 41.822),
  clinic("c-prairie", "Prairie Avenue Clinic", "Primary care", -71.419, 41.806),
  clinic("c-elmwood", "Elmwood Pediatrics", "Primary care", -71.422, 41.792),
  clinic("c-smith", "Smith Hill Community Clinic", "FQHC", -71.421, 41.836),
];

export const parks: Place[] = [
  park("p-dexter", "Dexter Training Ground", 10, -71.428, 41.817),
  park("p-india", "India Point Park", 18, -71.39, 41.817),
  park("p-prospect", "Prospect Terrace", 2, -71.404, 41.831),
  park("p-donigian", "Donigian Park", 4, -71.458, 41.823),
  park("p-roger", "Roger Williams Park", 435, -71.412, 41.781),
  park("p-blackstone", "Blackstone Park", 45, -71.386, 41.838),
  park("p-davis", "Davis Park", 12, -71.434, 41.849),
];

export const customers: Place[] = [
  stop(1, "Eddy St", 42, -71.412, 41.814),
  stop(2, "Point St", 18, -71.406, 41.81),
  stop(3, "Hospital St", 64, -71.416, 41.809),
  stop(4, "Richmond St", 27, -71.402, 41.815),
  stop(5, "Clifford St", 11, -71.418, 41.817),
  stop(6, "Pine St", 53, -71.408, 41.806),
  stop(7, "Chestnut St", 8, -71.42, 41.812),
  stop(8, "Ship St", 36, -71.401, 41.808),
  stop(9, "Dorrance St", 22, -71.414, 41.819),
  stop(10, "Friendship St", 71, -71.406, 41.818),
  stop(11, "Bassett St", 15, -71.424, 41.808),
  stop(12, "Elm St", 31, -71.4, 41.812),
  stop(13, "Plane St", 9, -71.417, 41.804),
  stop(14, "Claverick St", 44, -71.411, 41.821),
  stop(15, "Pearl St", 19, -71.405, 41.804),
  stop(16, "South St", 28, -71.422, 41.816),
  stop(17, "Atwells Ave", 40, -71.436, 41.824),
  stop(18, "Academy Ave", 17, -71.448, 41.81),
  stop(19, "Thayer St", 23, -71.398, 41.831),
  stop(20, "Gano St", 12, -71.39, 41.818),
  stop(21, "Branch Ave", 33, -71.44, 41.85),
  stop(22, "Broad St", 26, -71.418, 41.798),
  stop(23, "Lockwood St", 14, -71.398, 41.786),
  stop(24, "Manton Ave", 21, -71.462, 41.826),
  stop(25, "Hope St", 37, -71.394, 41.842),
  stop(26, "Elmwood Ave", 16, -71.428, 41.788),
  stop(27, "Chalkstone Ave", 29, -71.428, 41.838),
  stop(28, "Public St", 48, -71.422, 41.802),
];

export const warehouse: Place = {
  id: "w-eddy",
  name: "Eddy Street Warehouse",
  kind: "warehouse",
  lon: -71.409,
  lat: 41.812,
  detail: "Single distribution site in the sample",
};

export const SAMPLE_NOTE =
  "Neighborhood shapes, counts, clinics, and customers are an invented Providence demonstration — not census data, a health directory, public-access evidence, or a live business file. Real place names are illustrative labels at approximate points. No field verification or source-rights clearance has occurred.";
