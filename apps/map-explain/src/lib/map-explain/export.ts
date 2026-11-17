import { SAMPLE_NOTE } from "./data.js";
import type { QueryResult } from "./engine.js";
import { APPLICATION_NAME, FEATURE_NAME, PLATFORM_NAME, PUBLISHER_NAME } from "./identity.js";

export const DEMO_NOTICE = `${APPLICATION_NAME}, by ${PUBLISHER_NAME}. Local demonstration: illustrative Providence sample; user points are unverified. Not a released Observatory data product. Publication is not authorized.`;

export function provenance(result: QueryResult, question: string) {
  return {
    application: APPLICATION_NAME,
    publisher: PUBLISHER_NAME,
    platform: PLATFORM_NAME,
    feature: FEATURE_NAME,
    schema_version: 1,
    status: "unverified_demo",
    publication_authorized: false,
    query_id: result.queryId,
    question,
    interpreted_as: result.interpretedAs,
    method: result.steps,
    sources: result.sources,
    limitations: [DEMO_NOTICE, SAMPLE_NOTE, result.confidenceNote],
  };
}

export function resultGeoJSON(result: QueryResult, question: string): string {
  const ids = new Set(result.rows.map((row) => row.id));
  const features = [
    ...result.neighborhoods.filter((n) => ids.has(n.id)).map((n) => ({
      type: "Feature", id: n.id,
      properties: { name: n.name, detail: result.details[n.id]?.detail ?? "", source_class: "illustrative_sample", publication_authorized: false },
      geometry: { type: "Polygon", coordinates: [n.ring] },
    })),
    ...result.points.filter((p) => ids.has(p.id)).map((p) => ({
      type: "Feature", id: p.id,
      properties: { name: p.name, detail: result.details[p.id]?.detail ?? "", kind: p.kind, source_class: p.kind === "upload" ? "user_supplied_unverified" : "illustrative_sample", publication_authorized: false },
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    })),
  ];
  return JSON.stringify({ type: "FeatureCollection", zqm_observatory: provenance(result, question), features }, null, 2);
}

/** Prefix spreadsheet formulas even when hidden behind whitespace or a control character. */
export function csvCell(value: string): string {
  const safe = /^[\s\u0000-\u001f]*[=+@-]/.test(value) || /^[\t\r\n]/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function resultCSV(result: QueryResult, question: string): string {
  const rows = [
    ["id", "name", "primary", "secondary", "status", "publication_authorized", "question", "interpreted_as", "method", "sources", "limitations"],
    ...result.rows.map((row) => [row.id, row.name, row.primary, row.secondary, "unverified_demo", "false", question, result.interpretedAs, JSON.stringify(result.steps), JSON.stringify(result.sources), `${DEMO_NOTICE} ${SAMPLE_NOTE} ${result.confidenceNote}`]),
  ];
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}

export function resultSummary(result: QueryResult, question: string): string {
  return [DEMO_NOTICE, SAMPLE_NOTE, "", `Question: ${question}`, result.title, result.summary, "", ...result.steps.map((s, i) => `${i + 1}. ${s.title} — ${s.detail}`), "", result.interpretedAs, result.confidenceNote, "", ...result.sources.map((s) => `${s.name}: ${s.detail}`)].join("\n");
}
