import { useMemo, useState, type MouseEvent } from "react";
import {
  label,
  positions,
  type Feature,
  type Geometry,
  type Layer,
  type Position,
} from "../../lib/observatory/model";

import { mapFrame } from "../../lib/observatory/view";

export type DrawMode = "none" | "Point" | "LineString" | "Polygon";
export function Canvas({
  layers,
  result,
  filter,
  draw,
  draft,
  onDraw,
  onSelect,
  selected,
}: {
  layers: Layer[];
  result?: Layer;
  filter: string;
  draw: DrawMode;
  draft: Position[];
  onDraw: (p: Position) => void;
  onSelect: (f: Feature, l: Layer) => void;
  selected?: string;
}) {
  const [zoom, setZoom] = useState(1);
  const frame = useMemo(() => mapFrame(layers), [layers]);
  const scale = frame.scale * zoom;
  const project = (p: Position) => [
    500 + (p[0] - frame.cx) * frame.cos * scale,
    350 - (p[1] - frame.cy) * scale,
  ];
  const pathLine = (v: Position[]) =>
    v.map((p, i) => `${i ? "L" : "M"}${project(p).join(",")}`).join(" ");
  function path(g: Geometry): string {
    const c = g.coordinates as Position[];
    if (g.type === "LineString") return pathLine(c);
    if (g.type === "MultiLineString")
      return (g.coordinates as Position[][]).map(pathLine).join(" ");
    if (g.type === "Polygon")
      return (g.coordinates as Position[][])
        .map((r) => pathLine(r) + "Z")
        .join(" ");
    if (g.type === "MultiPolygon")
      return (g.coordinates as Position[][][])
        .flatMap((p) => p.map((r) => pathLine(r) + "Z"))
        .join(" ");
    return "";
  }
  function click(e: MouseEvent<SVGSVGElement>) {
    if (draw === "none") return;
    const matrix = e.currentTarget.getScreenCTM();
    if (!matrix) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
      matrix.inverse(),
    );
    const lon = frame.cx + (p.x - 500) / (scale * frame.cos),
      lat = frame.cy - (p.y - 350) / scale;
    if (Math.abs(lon) <= 180 && Math.abs(lat) <= 90)
      onDraw([Number(lon.toFixed(7)), Number(lat.toFixed(7))]);
  }
  const display = [
    ...layers.filter((l) => l.visible),
    ...(result ? [{ ...result, color: "#c35f2f" }] : []),
  ];
  return (
    <section className="atlas" aria-label="Shared project map">
      <div className="atlas-top">
        <span>
          PROJECT MAP <b>EPSG:4326</b>
        </span>
        <span>Local vectors · no external basemap</span>
      </div>
      <svg
        className={draw !== "none" ? "drawing" : ""}
        viewBox="0 0 1000 700"
        role="group"
        aria-label="Interactive project geometry map"
        onClick={click}
      >
        <defs>
          <pattern
            id="grid"
            width="50"
            height="50"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 50 0 L 0 0 0 50"
              fill="none"
              stroke="#b1baad"
              strokeWidth=".55"
            />
          </pattern>
        </defs>
        <rect width="1000" height="700" fill="url(#grid)" />
        <text x="950" y="65" className="north">
          N ↑
        </text>
        {display.map((layer, index) => (
          <g key={`${layer.id}-${index}`}>
            {layer.features
              .filter(
                (f) =>
                  !filter ||
                  JSON.stringify(f.properties)
                    .toLowerCase()
                    .includes(filter.toLowerCase()),
              )
              .map((f) => {
                const polygons = /Polygon/.test(f.geometry.type),
                  points = /Point/.test(f.geometry.type);
                const active = selected === `${layer.id}/${f.id}`;
                const select = () => {
                  if (draw === "none") onSelect(f, layer);
                };
                const style = {
                  color: active
                    ? "#a23c22"
                    : typeof f.properties.gap === "boolean"
                      ? f.properties.gap
                        ? "#c35f2f"
                        : "#557b68"
                      : layer.color,
                };
                return (
                  <g
                    key={f.id}
                    role="button"
                    tabIndex={draw === "none" ? 0 : -1}
                    aria-label={`${layer.name}: ${label(f)}`}
                    onClick={select}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        select();
                      }
                    }}
                    style={style}
                  >
                    <title>{`${label(f)} · ${layer.name}`}</title>
                    {points ? (
                      positions(f.geometry).map((p, i) => {
                        const [cx, cy] = project(p);
                        return (
                          <circle
                            key={i}
                            cx={cx}
                            cy={cy}
                            r={active ? 9 : 6}
                            fill="currentColor"
                            stroke="#fbfaf4"
                            strokeWidth="2"
                          />
                        );
                      })
                    ) : (
                      <path
                        d={path(f.geometry)}
                        fill={polygons ? "currentColor" : "none"}
                        fillOpacity={polygons ? 0.19 : 1}
                        fillRule="evenodd"
                        stroke="currentColor"
                        strokeWidth={active ? 4 : 2}
                      />
                    )}
                  </g>
                );
              })}
          </g>
        ))}
        {draft.length > 0 && (
          <g fill="#9d3c24" stroke="#9d3c24">
            <path
              d={
                pathLine(draft) +
                (draw === "Polygon" && draft.length >= 3 ? "Z" : "")
              }
              fillOpacity=".15"
              strokeWidth="3"
              strokeDasharray="7 5"
            />
            {draft.map((p, i) => {
              const [cx, cy] = project(p);
              return <circle key={i} cx={cx} cy={cy} r="5" />;
            })}
          </g>
        )}
        <text x="25" y="675" className="extent">
          {frame.cx.toFixed(4)}° lon / {frame.cy.toFixed(4)}° lat ·
          equirectangular display
        </text>
      </svg>
      <div className="atlas-controls">
        <button
          aria-label="Zoom in"
          onClick={() => setZoom((z) => Math.min(8, z * 1.4))}
        >
          +
        </button>
        <button
          aria-label="Zoom out"
          onClick={() => setZoom((z) => Math.max(0.25, z / 1.4))}
        >
          −
        </button>
        <button onClick={() => setZoom(1)}>Fit</button>
      </div>
      <div className="atlas-legend">
        {display.map((l, i) => (
          <span key={`${l.id}-${i}`}>
            <i style={{ background: l.color }} />
            {l.name}
            {i >= layers.filter((l) => l.visible).length ? " · result" : ""}
          </span>
        ))}
        {display.some((l) =>
          l.features.some((f) => typeof f.properties.gap === "boolean"),
        ) && (
          <>
            <span>
              <i style={{ background: "#c35f2f" }} />
              Gap
            </span>
            <span>
              <i style={{ background: "#557b68" }} />
              Covered
            </span>
          </>
        )}
      </div>
      {draw !== "none" && (
        <div className="draw-hint">
          Click the map to add {draw === "Point" ? "a point" : "vertices"}.
          Review coordinates before saving.
        </div>
      )}
    </section>
  );
}
