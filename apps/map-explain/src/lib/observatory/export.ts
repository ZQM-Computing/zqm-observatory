import { csvCell } from "../map-explain/export.js";
import { validateProject, type Layer, type Project } from "./model.js";

export function projectBundle(project: Project): string {
  validateProject(project);
  // Validation and restore use the UTF-8 byte size of this compact representation.
  return JSON.stringify(project);
}
export function layerCSV(layer: Layer): string {
  const keys = [
    ...new Set(layer.features.flatMap((f) => Object.keys(f.properties))),
  ];
  const rows = [
    [
      "feature_id",
      "geometry_geojson",
      ...keys.map((key) => `attribute:${key}`),
      "source_name",
      "source_kind",
      "source_note",
      "source_date",
      "processing_steps",
      "rights_status",
      "publication_authorized",
    ],
    ...layer.features.map((f) => [
      f.id,
      JSON.stringify(f.geometry),
      ...keys.map((key) =>
        f.properties[key] === undefined
          ? ""
          : typeof f.properties[key] === "object"
            ? JSON.stringify(f.properties[key])
            : String(f.properties[key]),
      ),
      layer.source.name,
      layer.source.kind,
      layer.source.note,
      layer.source.sourceDate ?? "unknown",
      JSON.stringify(layer.steps),
      layer.source.rights,
      "false",
    ]),
  ];
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}
export function download(
  body: string | Blob,
  name: string,
  mime = "application/json",
): void {
  const url = URL.createObjectURL(
    body instanceof Blob ? body : new Blob([body], { type: mime }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
export async function fileBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let raw = "";
  for (let i = 0; i < bytes.length; i += 8192)
    raw += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(raw);
}
