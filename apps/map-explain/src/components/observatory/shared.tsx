import {
  cloneElement,
  isValidElement,
  useId,
  type ReactElement,
  type ReactNode,
} from "react";
import type { Analysis } from "../../lib/observatory/analysis";
import { download, layerCSV } from "../../lib/observatory/export";
import { layerGeoJSON } from "../../lib/observatory/prep";
import type { Layer, Project } from "../../lib/observatory/model";
export type Commit = (
  summary: string,
  edit: (p: Project) => void,
) => Promise<void>;
export function addLayer(p: Project, input: Layer) {
  const layer = structuredClone(input),
    original = layer.name.slice(0, 110);
  let index = 2;
  layer.name = original;
  while (
    p.layers.some((l) => l.name.toLowerCase() === layer.name.toLowerCase())
  )
    layer.name = `${original} ${index++}`;
  p.layers.push(layer);
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const controlId = useId(),
    labelId = `${controlId}-label`;
  return (
    <label className="control" htmlFor={controlId}>
      <span id={labelId}>{label}</span>
      {isValidElement(children)
        ? cloneElement(
            children as ReactElement<{
              id?: string;
              "aria-labelledby"?: string;
            }>,
            { id: controlId, "aria-labelledby": labelId },
          )
        : children}
    </label>
  );
}
export function Check({
  text,
  checked,
  onChange,
}: {
  text: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="check">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {text}
    </label>
  );
}
export function Result({
  value,
  onSave,
  busy,
}: {
  value: Analysis;
  onSave: () => void;
  busy: boolean;
}) {
  return (
    <article className="analysis-result">
      <div className="tag">COMPUTED RESULT · DRAFT</div>
      <h3>{value.title}</h3>
      <p>{value.summary}</p>
      <div className="actions">
        <button className="primary" onClick={onSave} disabled={busy}>
          Add result to project
        </button>
        <button
          onClick={() =>
            download(
              layerGeoJSON(value.layer),
              "observatory-result.geojson",
              "application/geo+json",
            )
          }
        >
          GeoJSON
        </button>
        <button
          onClick={() =>
            download(
              layerCSV(value.layer),
              "observatory-result.csv",
              "text/csv",
            )
          }
        >
          CSV
        </button>
      </div>
      <div className="result-list">
        {value.rows.map((r) => (
          <div className="record" key={r.id}>
            <strong>{r.name}</strong>
            <span>{r.detail}</span>
          </div>
        ))}
      </div>
      <details open>
        <summary>Methods & limits</summary>
        {[...value.methods, ...value.limitations].map((m) => (
          <p className="small" key={m}>
            {m}
          </p>
        ))}
        <p className="small">
          Source: {value.layer.source.note} Publication is not authorized.
        </p>
      </details>
    </article>
  );
}
