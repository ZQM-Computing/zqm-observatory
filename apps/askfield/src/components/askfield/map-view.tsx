import { useMemo, useState } from "react";
import { X, ZoomIn, ZoomOut, Maximize } from "lucide-react";
import type { QueryResult } from "@/lib/askfield/engine";
import type { LonLat } from "@/lib/askfield/geo";

type Props = {
  result: QueryResult;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  showLinks: boolean;
  showBuffer: boolean;
  hiddenKinds: string[];
};

/** Local equirectangular illustration. Measurements always use the engine's haversine function. */
export function MapView(props: Props) {
  // A new answer resets the viewport, while point/row selection preserves it.
  return <ResultMap key={props.result.queryId} {...props} />;
}

function ResultMap({ result, selectedId, onSelect, showLinks, showBuffer, hiddenKinds }: Props) {
  const [zoom, setZoom] = useState(1);
  const WIDTH = 1000;
  const HEIGHT = 760;
  const project = useMemo(() => {
    const coords: LonLat[] = [
      ...result.neighborhoods.flatMap((n) => n.ring),
      ...result.points.map((p): LonLat => [p.lon, p.lat]),
      ...result.buffers.flatMap((b) => b.ring),
    ];
    if (!coords.length) coords.push([-71.46, 41.78], [-71.38, 41.86]);
    // Iteration avoids argument-count limits on 2,000-point uploads.
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    const meanLat = coords.reduce((sum, p) => sum + p[1], 0) / coords.length;
    const cos = Math.max(0.01, Math.cos(meanLat * Math.PI / 180));
    for (const [lon, lat] of coords) {
      xMin = Math.min(xMin, lon * cos); xMax = Math.max(xMax, lon * cos);
      yMin = Math.min(yMin, lat); yMax = Math.max(yMax, lat);
    }
    const scale = Math.min((WIDTH - 120) / Math.max(0.005, xMax - xMin), (HEIGHT - 160) / Math.max(0.005, yMax - yMin));
    return ([lon, lat]: LonLat): LonLat => [WIDTH / 2 + (lon * cos - (xMin + xMax) / 2) * scale, HEIGHT / 2 - (lat - (yMin + yMax) / 2) * scale];
  }, [result]);
  const path = (coords: LonLat[]) => coords.map((p) => project(p).join(",")).join(" ");
  const pick = (id: string) => ({
    role: "button" as const, tabIndex: 0,
    "aria-label": `Select ${result.details[id]?.name ?? id}`,
    "aria-pressed": id === selectedId,
    onClick: () => onSelect(id),
    onKeyDown: (event: React.KeyboardEvent<SVGElement>) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(id); }
    },
  });
  const detail = selectedId ? result.details[selectedId] : undefined;
  const selectedPoint = result.points.find((p) => p.id === selectedId);
  const selectedZone = result.neighborhoods.find((p) => p.id === selectedId);
  const focus = selectedPoint ? project([selectedPoint.lon, selectedPoint.lat]) : selectedZone ? project(selectedZone.center) : [WIDTH / 2, HEIGHT / 2];
  const center = zoom === 1 ? [WIDTH / 2, HEIGHT / 2] : focus;
  const box = `${center[0] - WIDTH / (2 * zoom)} ${center[1] - HEIGHT / (2 * zoom)} ${WIDTH / zoom} ${HEIGHT / zoom}`;
  return (
    <section className="map-pane" aria-label="Illustrative result map">
      <svg className="map-canvas local-map" viewBox={box} preserveAspectRatio="xMidYMid meet" role="group" aria-label="Synthetic layers. Select a shape or a point for its calculated detail.">
        <title>Illustrative GIS results; no basemap or verified place conditions</title>
        {showBuffer && result.buffers.map((b) => <polygon key={b.id} points={path(b.ring)} fill="#1c4f45" fillOpacity="0.08" stroke="#1c4f45" strokeWidth="1" vectorEffect="non-scaling-stroke" />)}
        {result.neighborhoods.map((n) => <polygon key={n.id} points={path(n.ring)} fill={n.fill} fillOpacity={n.opacity} stroke={n.id === selectedId ? "#1c4f45" : "#59675f"} strokeWidth={n.id === selectedId ? 3 : n.emphasis ? 1.3 : 0.7} vectorEffect="non-scaling-stroke" {...pick(n.id)} />)}
        {showLinks && result.lines.map((line) => <polyline key={line.id} points={path(line.coordinates)} fill="none" stroke="#1c4f45" strokeDasharray="5 4" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />)}
        {result.neighborhoods.filter((n) => n.label).map((n) => {
          const [x, y] = project(n.center);
          return <text key={n.id} x={x} y={y} className="svg-map-label" textAnchor="middle" pointerEvents="none">{n.name}</text>;
        })}
        {result.points.filter((p) => !hiddenKinds.includes(p.kind)).map((p) => {
          const [cx, cy] = project([p.lon, p.lat]);
          return <circle key={p.id} cx={cx} cy={cy} r={p.radius / zoom} fill={p.fill} stroke={p.id === selectedId ? "#d48235" : p.stroke} strokeWidth={p.strokeWidth + (p.id === selectedId ? 3 : 0)} vectorEffect="non-scaling-stroke" {...pick(p.id)}><title>{p.name}</title></circle>;
        })}
      </svg>
      <p className="map-context">Illustrative layers · WGS84 · No basemap<br />N ↑ · Straight-line calculations</p>
      <div className="map-tools" aria-label="Map controls">
        <button type="button" className="icon-btn" aria-label="Zoom in" disabled={zoom >= 8} onClick={() => setZoom((z) => Math.min(8, z * 1.5))}><ZoomIn className="size-4" /></button>
        <button type="button" className="icon-btn" aria-label="Zoom out" disabled={zoom <= 1} onClick={() => setZoom((z) => Math.max(1, z / 1.5))}><ZoomOut className="size-4" /></button>
        <button type="button" className="icon-btn" aria-label="Fit all layers" onClick={() => { setZoom(1); onSelect(null); }}><Maximize className="size-4" /></button>
      </div>
      <ul className="map-legend" aria-label="Map legend">
        {result.legend.map((item) => <li key={item.label}><span className={item.hollow ? "swatch swatch-hollow" : "swatch"} style={{ background: item.hollow ? "transparent" : item.color, borderColor: item.color }} />{item.label}</li>)}
      </ul>
      {detail && <div className="map-callout"><div><p className="font-medium">{detail.name}</p><p className="text-sm text-muted">{detail.detail}</p></div><button type="button" className="icon-btn" aria-label="Clear selection" onClick={() => onSelect(null)}><X className="size-4" /></button></div>}
    </section>
  );
}
