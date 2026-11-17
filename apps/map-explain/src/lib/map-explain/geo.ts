export type LonLat = [number, number];

const EARTH = 6371008.8;

export function distanceMeters(a: LonLat, b: LonLat): number {
  const φ1 = (a[1] * Math.PI) / 180;
  const φ2 = (b[1] * Math.PI) / 180;
  const dφ = ((b[1] - a[1]) * Math.PI) / 180;
  const dλ = ((b[0] - a[0]) * Math.PI) / 180;
  const s =
    Math.sin(dφ / 2) ** 2 +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(dλ / 2) ** 2;
  return 2 * EARTH * Math.asin(Math.min(1, Math.sqrt(s)));
}

export function ringCentroid(ring: LonLat[]): LonLat {
  let n = ring.length;
  if (
    n > 1 &&
    ring[0][0] === ring[n - 1][0] &&
    ring[0][1] === ring[n - 1][1]
  ) {
    n -= 1;
  }
  let twice = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % n];
    const cross = x1 * y2 - x2 * y1;
    twice += cross;
    cx += (x1 + x2) * cross;
    cy += (y1 + y2) * cross;
  }
  if (Math.abs(twice) < 1e-12) {
    let sx = 0;
    let sy = 0;
    for (let i = 0; i < n; i++) {
      sx += ring[i][0];
      sy += ring[i][1];
    }
    return [sx / n, sy / n];
  }
  return [cx / (3 * twice), cy / (3 * twice)];
}

export function pointInRing(pt: LonLat, ring: LonLat[]): boolean {
  const n =
    ring.length > 1 &&
    ring[0][0] === ring[ring.length - 1][0] &&
    ring[0][1] === ring[ring.length - 1][1]
      ? ring.length - 1
      : ring.length;
  let inside = false;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect =
      yi > pt[1] !== yj > pt[1] &&
      pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi + 0) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function circleRing(center: LonLat, radiusM: number, steps = 64): LonLat[] {
  const lat = (center[1] * Math.PI) / 180;
  const mPerDegLat = 111320;
  const mPerDegLon = Math.max(1e-6, 111320 * Math.cos(lat));
  const ring: LonLat[] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    ring.push([
      center[0] + (Math.cos(a) * radiusM) / mPerDegLon,
      center[1] + (Math.sin(a) * radiusM) / mPerDegLat,
    ]);
  }
  return ring;
}

export function blobRing(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  phase: number,
): LonLat[] {
  const n = 8;
  const pts: LonLat[] = [];
  for (let i = 0; i < n; i++) {
    const a = phase + (i / n) * Math.PI * 2;
    const j = 0.86 + 0.14 * Math.sin(3 * a + phase);
    pts.push([
      Number((cx + Math.cos(a) * rx * j).toFixed(6)),
      Number((cy + Math.sin(a) * ry * j).toFixed(6)),
    ]);
  }
  pts.push(pts[0]);
  return pts;
}

export function formatMeters(m: number): string {
  if (!Number.isFinite(m)) return "—";
  const a = Math.abs(m);
  if (a < 1000) return `${Math.round(a)} m`;
  const km = a / 1000;
  return `${km.toFixed(km < 10 ? 1 : 0)} km`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n);
}

export function formatPercent(fraction: number): string {
  const p = fraction * 100;
  return `${p >= 10 || p === 0 ? p.toFixed(0) : p.toFixed(1)}%`;
}

export function formatMoney(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export function extent(points: LonLat[]): [LonLat, LonLat] | null {
  if (!points.length) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of points) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return [
    [minX, minY],
    [maxX, maxY],
  ];
}
