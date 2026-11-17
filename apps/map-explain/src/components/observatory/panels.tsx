import { useState, type FormEvent } from "react";
import {
  answerProject,
  coverage,
  pointFeatures,
  type Analysis,
} from "../../lib/observatory/analysis";
import { request } from "../../lib/observatory/api";
import { download, fileBase64, layerCSV } from "../../lib/observatory/export";
import {
  DEFAULT_PREP,
  layerGeoJSON,
  prepare,
  xmlToGeoJSON,
  type PrepOptions,
  type PrepResult,
} from "../../lib/observatory/prep";
import {
  geometryErrors,
  id,
  label,
  makeLayer,
  now,
  type Feature,
  type Layer,
  type Position,
  type Project,
} from "../../lib/observatory/model";
import { addLayer, Check, Field, Result, type Commit } from "./shared";
import type { DrawMode } from "./canvas";
export type Perform = (action: () => void | Promise<void>) => void;
type Props = {
  project: Project;
  commit: Commit;
  perform: Perform;
  busy: boolean;
};

export function ExplainPanel({
  project,
  commit,
  perform,
  busy,
  result,
  setResult,
}: Props & {
  result: Analysis | null;
  setResult: (a: Analysis | null) => void;
}) {
  const [question, setQuestion] = useState("");
  const points = project.layers.filter((l) => pointFeatures(l).length),
    polygons = project.layers.find((l) =>
      l.features.some((f) => f.geometry.type === "Polygon"),
    );
  const examples = [
    project.layers[0] && `Show ${project.layers[0].name}`,
    points.length > 1 &&
      `Show ${points[0].name} beyond 1000 m of ${points[1].name}`,
    points.length > 1 && `Rank ${points[0].name} nearest to ${points[1].name}`,
    points[0] && polygons && `Count ${points[0].name} in ${polygons.name}`,
  ].filter(Boolean) as string[];
  const ask = (q: string) =>
    perform(() => {
      setQuestion(q);
      setResult(null);
      setResult(answerProject(q, project.layers));
    });
  return (
    <>
      <div className="tag">01 / MAPEXPLAIN</div>
      <h1>
        Ask about places.
        <br />
        <em>See how it adds up.</em>
      </h1>
      <p>
        Traceable location analysis using the layers in this project. Every
        answer has a map, records, and a reproducible method.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <Field label="Your spatial question">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Show Demand points beyond 1000 m of Facilities"
            maxLength={500}
            required
          />
        </Field>
        <button className="primary" disabled={busy}>
          Run question <span>↗</span>
        </button>
      </form>
      <div className="example-list">
        {examples.map((q) => (
          <button key={q} disabled={busy} onClick={() => ask(q)}>
            {q}
            <span>↗</span>
          </button>
        ))}
      </div>
      <p className="small">
        Use these exact patterns with your layer names. Queries run locally with
        a bounded parser; unsupported requests return an error. No language
        model or paid API is called.
      </p>
      {result && (
        <Result
          value={result}
          busy={busy}
          onSave={() =>
            perform(async () => {
              await commit(`Saved analysis: ${result.title}`, (p) =>
                addLayer(p, { ...result.layer, id: id() }),
              );
              setResult(null);
            })
          }
        />
      )}
    </>
  );
}

export function PrepPanel({
  project: _project,
  commit,
  perform,
  busy,
  token,
  setToken,
}: Props & { token: string; setToken: (s: string) => void }) {
  const [file, setFile] = useState<File | null>(null),
    [options, setOptions] = useState<PrepOptions>(DEFAULT_PREP),
    [privateMode, setPrivate] = useState(false),
    [source, setSource] = useState(""),
    [repair, setRepair] = useState(false),
    [result, setResult] = useState<PrepResult | null>(null),
    [layerChoices, setChoices] = useState<string[]>([]),
    [selectedLayer, setSelectedLayer] = useState("");
  const option = <K extends keyof PrepOptions>(
    key: K,
    value: PrepOptions[K],
  ) => {
    setOptions((o) => ({ ...o, [key]: value }));
    setResult(null);
  };
  async function preview() {
    if (!file) throw new Error("Choose a source file first.");
    setResult(null);
    if (privateMode) {
      if (file.size > 4_000_000)
        throw new Error("Private prep accepts up to 4 MB.");
      const response = await request<{
        collection?: unknown;
        diagnostics: string[];
        layers?: string[];
        source_crs?: string;
      }>("prep", token, {
        filename: file.name,
        content_base64: await fileBase64(file),
        source_crs: source.trim() || null,
        repair,
        drop_invalid: options.dropInvalid,
        layer: selectedLayer || undefined,
      });
      if (response.layers) {
        setChoices(response.layers);
        return;
      }
      const prepared = prepare(
        JSON.stringify(response.collection),
        file.name.replace(/\.[^.]+$/, ".geojson"),
        { ...options, sourceCrs: "EPSG:4326" },
        "private-output",
      );
      if (prepared.layer) {
        prepared.layer.source.name = file.name;
        prepared.layer.steps.unshift({
          operation: "private_prepare",
          at: now(),
          detail: `${response.diagnostics.join(" ")} Source CRS ${response.source_crs}; explicit repair=${repair}; drop invalid=${options.dropInvalid}.`,
        });
      }
      setResult({
        ...prepared,
        diagnostics: [...response.diagnostics, ...prepared.diagnostics],
      });
    } else {
      if (file.size > 2_000_000)
        throw new Error(
          "Browser prep accepts up to 2 MB. Choose private prep for larger supported files.",
        );
      const ext = file.name.split(".").at(-1)?.toLowerCase();
      let text = await file.text(),
        filename = file.name;
      if (ext === "kml" || ext === "gpx") {
        if (options.sourceCrs !== "EPSG:4326")
          throw new Error("KML/GPX are WGS84; choose EPSG:4326.");
        text = xmlToGeoJSON(text, ext);
        filename = file.name.replace(/\.[^.]+$/, ".geojson");
      } else if (!["geojson", "json", "csv"].includes(ext ?? ""))
        throw new Error(
          "Choose private prep for zipped Shapefile, GeoPackage, or KMZ.",
        );
      const prepared = prepare(text, filename, options);
      if (prepared.layer) prepared.layer.source.name = file.name;
      setResult(prepared);
    }
  }
  return (
    <>
      <div className="tag">02 / DATA PREP</div>
      <h1>
        Bring your data.
        <br />
        <em>Know what changed.</em>
      </h1>
      <p>
        Preview schema and geometry checks, choose explicit fixes, then add the
        prepared layer to every workspace.
      </p>
      <Field label="Source file">
        <input
          type="file"
          accept=".csv,.geojson,.json,.zip,.gpkg,.kml,.kmz,.gpx"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setResult(null);
            setChoices([]);
            setSelectedLayer("");
          }}
        />
      </Field>
      <Check
        text="Use private conversion service"
        checked={privateMode}
        onChange={(v) => {
          setPrivate(v);
          setResult(null);
        }}
      />
      {privateMode ? (
        <>
          <Field label="Private workspace token (memory only)">
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </Field>
          <Field label="Actual source CRS · blank uses file declaration">
            <input
              placeholder="EPSG:4326"
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setResult(null);
              }}
            />
          </Field>
          <Check
            text="Repair invalid geometry with GEOS"
            checked={repair}
            onChange={(v) => {
              setRepair(v);
              setResult(null);
            }}
          />
          <p className="small">
            GeoJSON, CSV, zipped Shapefile, GeoPackage, KML/KMZ, GPX. 4 MB /
            2,000 features. Files are sent only when you run this preview.
          </p>
        </>
      ) : (
        <>
          <Field label="Actual source CRS">
            <select
              value={options.sourceCrs}
              onChange={(e) =>
                option("sourceCrs", e.target.value as PrepOptions["sourceCrs"])
              }
            >
              <option>EPSG:4326</option>
              <option>EPSG:3857</option>
            </select>
          </Field>
          <p className="small">
            Local CSV / GeoJSON / basic KML / GPX. 2 MB / 2,000 features.
            Structural checks; topology needs private prep.
          </p>
        </>
      )}
      {layerChoices.length > 0 && (
        <Field label="GeoPackage layer">
          <select
            value={selectedLayer}
            onChange={(e) => setSelectedLayer(e.target.value)}
          >
            <option value="">Choose a layer</option>
            {layerChoices.map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
        </Field>
      )}
      <Check
        text="Normalize field names"
        checked={options.normalize}
        onChange={(v) => option("normalize", v)}
      />
      <Check
        text="Close unclosed polygon rings"
        checked={options.closeRings}
        onChange={(v) => option("closeRings", v)}
      />
      <Check
        text="Drop invalid records (recorded in lineage)"
        checked={options.dropInvalid}
        onChange={(v) => option("dropInvalid", v)}
      />
      <Check
        text="Remove entirely empty fields"
        checked={options.dropEmpty}
        onChange={(v) => option("dropEmpty", v)}
      />
      <button
        className="primary"
        disabled={!file || busy}
        onClick={() => perform(preview)}
      >
        Preview preparation ↗
      </button>
      {result && (
        <section className="analysis-result">
          <h3>
            {result.layer
              ? `${result.layer.features.length} features ready for review`
              : "Review required"}
          </h3>
          {result.diagnostics.map((d, i) => (
            <p className="small" key={i}>
              {d}
            </p>
          ))}
          {result.fields.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Missing values</th>
                </tr>
              </thead>
              <tbody>
                {result.fields.map((f) => (
                  <tr key={f.name}>
                    <td>{f.name}</td>
                    <td>{f.missing}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.layer && (
            <div className="actions">
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  perform(async () => {
                    const layer = result.layer!;
                    await commit(`Prepared ${file?.name}`, (p) =>
                      addLayer(p, layer),
                    );
                    setResult(null);
                  })
                }
              >
                Add prepared layer
              </button>
              <button
                onClick={() =>
                  download(
                    layerGeoJSON(result.layer!),
                    "observatory-prepared.geojson",
                    "application/geo+json",
                  )
                }
              >
                Export preview
              </button>
            </div>
          )}
        </section>
      )}
    </>
  );
}

export function CoveragePanel({
  project,
  commit,
  perform,
  busy,
  result,
  setResult,
}: Props & {
  result: Analysis | null;
  setResult: (a: Analysis | null) => void;
}) {
  const candidates = project.layers.filter((l) => pointFeatures(l).length);
  const [demand, setDemand] = useState(candidates[0]?.id ?? ""),
    [supply, setSupply] = useState(candidates[1]?.id ?? ""),
    [radius, setRadius] = useState("1000"),
    [weightField, setWeight] = useState(""),
    [distanceWeight, setDistanceWeight] = useState("1"),
    [demandWeight, setDemandWeight] = useState("1");
  const selected = project.layers.find((l) => l.id === demand);
  const fields = [
    ...new Set(
      pointFeatures(selected ?? makeLayer("empty", [])).flatMap((f) =>
        Object.keys(f.properties),
      ),
    ),
  ];
  function run(e: FormEvent) {
    e.preventDefault();
    perform(() => {
      setResult(null);
      const a = project.layers.find((l) => l.id === demand),
        b = project.layers.find((l) => l.id === supply);
      if (!a || !b)
        throw new Error("Choose existing demand and supply layers.");
      setResult(
        coverage(
          a,
          b,
          Number(radius),
          weightField,
          Number(distanceWeight),
          Number(demandWeight),
        ),
      );
    });
  }
  return (
    <>
      <div className="tag">04 / COVERAGE ANALYSIS</div>
      <h1>
        Find the gaps.
        <br />
        <em>Compare the next move.</em>
      </h1>
      <p>
        Rank demand by distance and demand weight. Add a proposed site in Map
        Workspace, then select that layer as a new supply scenario.
      </p>
      <form onSubmit={run}>
        <div className="two">
          <Field label="Demand layer">
            <select
              value={demand}
              onChange={(e) => {
                setDemand(e.target.value);
                setWeight("");
                setResult(null);
              }}
            >
              {candidates.map((l) => (
                <option value={l.id} key={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Supply / scenario layer">
            <select
              value={supply}
              onChange={(e) => {
                setSupply(e.target.value);
                setResult(null);
              }}
            >
              {candidates.map((l) => (
                <option value={l.id} key={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Coverage distance (meters)">
          <input
            type="number"
            min="1"
            max="100000"
            step="any"
            value={radius}
            onChange={(e) => {
              setRadius(e.target.value);
              setResult(null);
            }}
            required
          />
        </Field>
        <Field label="Demand weight field">
          <select
            value={weightField}
            onChange={(e) => {
              setWeight(e.target.value);
              setResult(null);
            }}
          >
            <option value="">Equal weight for every point</option>
            {fields.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </Field>
        <div className="two">
          <Field label="Distance scoring weight">
            <input
              type="number"
              min="0"
              step="any"
              required
              value={distanceWeight}
              onChange={(e) => {
                setDistanceWeight(e.target.value);
                setResult(null);
              }}
            />
          </Field>
          <Field label="Demand scoring weight">
            <input
              type="number"
              min="0"
              step="any"
              required
              value={demandWeight}
              onChange={(e) => {
                setDemandWeight(e.target.value);
                setResult(null);
              }}
            />
          </Field>
        </div>
        <button className="primary" disabled={busy}>
          Calculate coverage ↗
        </button>
      </form>
      <p className="small">
        Straight-line distance only. The score formula and all point results are
        included with each analysis.
      </p>
      {result && (
        <Result
          value={result}
          busy={busy}
          onSave={() =>
            perform(async () => {
              await commit(`Saved coverage scenario: ${result.title}`, (p) =>
                addLayer(p, { ...result.layer, id: id() }),
              );
              setResult(null);
            })
          }
        />
      )}
    </>
  );
}

async function photoData(file: File): Promise<string> {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > 5_000_000)
    throw new Error("Choose JPEG, PNG, or WebP up to 5 MB.");
  const bitmap = await createImageBitmap(file);
  try {
    const scale = Math.min(1, 1000 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Photo conversion unavailable.");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const data = canvas.toDataURL("image/jpeg", 0.65);
    if (data.length > 300000)
      throw new Error(
        "Compressed photo exceeds 300 KB. Choose a smaller image.",
      );
    return data;
  } finally {
    bitmap.close();
  }
}

export function FieldPanel({ project, commit, perform, busy }: Props) {
  const [name, setName] = useState(""),
    [status, setStatus] = useState("normal"),
    [followup, setFollowup] = useState(""),
    [lat, setLat] = useState(""),
    [lon, setLon] = useState(""),
    [accuracy, setAccuracy] = useState<number | null>(null),
    [photo, setPhoto] = useState<string | null>(null),
    [reference, setReference] = useState("");
  const config = project.fieldForm ?? {
    extraLabel: "Reference",
    extraRequired: false,
  };
  const [extraLabel, setExtraLabel] = useState(config.extraLabel),
    [extraRequired, setExtraRequired] = useState(config.extraRequired);
  const records = project.layers.filter((l) => l.source.kind === "field");
  function locate() {
    return new Promise<void>((resolve, reject) => {
      if (!navigator.geolocation)
        return reject(
          new Error("Geolocation unavailable. Enter coordinates manually."),
        );
      navigator.geolocation.getCurrentPosition(
        (p) => {
          setLat(String(p.coords.latitude));
          setLon(String(p.coords.longitude));
          setAccuracy(p.coords.accuracy);
          resolve();
        },
        (e) =>
          reject(new Error(`GPS: ${e.message}. Manual entry is available.`)),
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
      );
    });
  }
  function save(e: FormEvent) {
    e.preventDefault();
    perform(async () => {
      if (
        !name.trim() ||
        !lat.trim() ||
        !lon.trim() ||
        (status === "urgent" && !followup.trim()) ||
        (config.extraRequired && !reference.trim())
      )
        throw new Error("Complete the required observation fields.");
      const geometry = {
        type: "Point",
        coordinates: [Number(lon), Number(lat)],
      };
      if (geometryErrors(geometry).length)
        throw new Error("Enter valid WGS84 longitude and latitude.");
      const f: Feature = {
        type: "Feature",
        id: id(),
        geometry,
        properties: {
          name: name.trim(),
          condition: status,
          follow_up: status === "urgent" ? followup.trim() : null,
          reference_label: config.extraLabel,
          reference: reference.trim(),
          captured_at: now(),
          location_method: accuracy === null ? "manual" : "device GPS",
          accuracy_m: accuracy,
          review_status: "pending",
          photo_jpeg: photo,
        },
      };
      await commit(`Captured field observation: ${name.trim()}`, (p) => {
        const layer = p.layers.find((l) => l.source.kind === "field");
        if (layer) layer.features.push(f);
        else
          addLayer(
            p,
            makeLayer(
              "Field observations",
              [f],
              "field",
              "User-captured observations; device accuracy is reported, not certified. Review before use.",
            ),
          );
      });
      setName("");
      setFollowup("");
      setReference("");
      setPhoto(null);
    });
  }
  return (
    <>
      <div className="tag">03 / FIELD COLLECTION</div>
      <h1>
        Capture what’s there.
        <br />
        <em>Review it together.</em>
      </h1>
      <p>
        Observations save on this device first. Push the project when connected;
        nothing is sent automatically.
      </p>
      <details>
        <summary>Configure the collection form</summary>
        <Field label="Additional field label">
          <input
            value={extraLabel}
            maxLength={80}
            onChange={(e) => setExtraLabel(e.target.value)}
          />
        </Field>
        <Check
          text="Require this field"
          checked={extraRequired}
          onChange={setExtraRequired}
        />
        <button
          disabled={busy || !extraLabel.trim()}
          onClick={() =>
            perform(() =>
              commit("Updated collection form", (p) => {
                p.fieldForm = { extraLabel: extraLabel.trim(), extraRequired };
              }),
            )
          }
        >
          Save form configuration
        </button>
        <p className="small">
          The Urgent condition always reveals a required follow-up field.
        </p>
      </details>
      <form onSubmit={save}>
        <Field label="Observation name *">
          <input
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="Condition">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="normal">Normal</option>
            <option value="urgent">Urgent · follow-up required</option>
          </select>
        </Field>
        {status === "urgent" && (
          <Field label="Required follow-up *">
            <input
              required
              value={followup}
              maxLength={1000}
              onChange={(e) => setFollowup(e.target.value)}
            />
          </Field>
        )}
        <Field
          label={`${config.extraLabel}${config.extraRequired ? " *" : ""}`}
        >
          <input
            required={config.extraRequired}
            maxLength={1000}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </Field>
        <div className="two">
          <Field label="Longitude *">
            <input
              type="number"
              step="any"
              min="-180"
              max="180"
              required
              value={lon}
              onChange={(e) => {
                setLon(e.target.value);
                setAccuracy(null);
              }}
            />
          </Field>
          <Field label="Latitude *">
            <input
              type="number"
              step="any"
              min="-90"
              max="90"
              required
              value={lat}
              onChange={(e) => {
                setLat(e.target.value);
                setAccuracy(null);
              }}
            />
          </Field>
        </div>
        <button type="button" disabled={busy} onClick={() => perform(locate)}>
          Use device GPS
        </button>
        <p className="small">
          {accuracy === null
            ? "Manual coordinates · accuracy unknown"
            : `Device-reported accuracy: ±${accuracy.toFixed(1)} m`}
        </p>
        <Field label="Optional photo · saved locally with this project">
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => {
              const file = e.target.files?.[0];
              setPhoto(null);
              if (file) perform(async () => setPhoto(await photoData(file)));
            }}
          />
        </Field>
        {photo && (
          <div>
            <img
              className="photo"
              src={photo}
              alt="Observation attachment preview"
            />
            <button type="button" onClick={() => setPhoto(null)}>
              Remove photo
            </button>
          </div>
        )}
        <p className="small">
          Photos are resized and re-encoded. Records and photos are included in
          project exports and explicit private sync. Avoid sensitive personal
          information.
        </p>
        <button className="primary" disabled={busy}>
          Save observation on this device
        </button>
      </form>
      <section className="analysis-result">
        <h3>Review queue</h3>
        {records.flatMap((l) =>
          l.features.map((f) => (
            <div className="record" key={`${l.id}/${f.id}`}>
              <strong>{label(f)}</strong>
              <span>
                {String(f.properties.review_status)} ·{" "}
                {String(f.properties.location_method)} ·{" "}
                {String(f.properties.condition ?? f.geometry.type)}
              </span>
              <button
                disabled={busy}
                onClick={() =>
                  perform(() =>
                    commit(`Reviewed observation ${label(f)}`, (p) => {
                      p.layers
                        .find((x) => x.id === l.id)!
                        .features.find(
                          (x) => x.id === f.id,
                        )!.properties.review_status =
                        f.properties.review_status === "reviewed"
                          ? "pending"
                          : "reviewed";
                    }),
                  )
                }
              >
                {f.properties.review_status === "reviewed"
                  ? "Return to pending"
                  : "Mark reviewed"}
              </button>
            </div>
          )),
        )}
        {!records.length && (
          <p className="small">
            No observations yet. Draw lines and polygons in Map Workspace.
          </p>
        )}
      </section>
    </>
  );
}

type Selection = { layerId: string; featureId: string } | null;
export function MapPanel({
  project,
  commit,
  perform,
  busy,
  filter,
  setFilter,
  draw,
  setDraw,
  draft,
  setDraft,
  selection,
  token,
}: Props & {
  filter: string;
  setFilter: (s: string) => void;
  draw: DrawMode;
  setDraw: (d: DrawMode) => void;
  draft: Position[];
  setDraft: (p: Position[]) => void;
  selection: Selection;
  token: string;
}) {
  const [layerName, setLayerName] = useState("Proposed sites"),
    [target, setTarget] = useState(""),
    [featureName, setFeatureName] = useState(""),
    [comment, setComment] = useState(""),
    [author, setAuthor] = useState(""),
    [attributes, setAttributes] = useState<{
      target: string;
      text: string;
    } | null>(null);
  const layer = project.layers.find((l) => l.id === selection?.layerId),
    feature = layer?.features.find((f) => f.id === selection?.featureId);
  const attributeTarget = JSON.stringify([layer?.id, feature?.id]);
  const attributeText =
    attributes?.target === attributeTarget ? attributes.text : "";
  function finish() {
    return perform(async () => {
      if (draw === "none" || !featureName.trim())
        throw new Error("Choose a geometry type and name the feature.");
      const coordinates =
        draw === "Point"
          ? draft[0]
          : draw === "Polygon"
            ? [[...draft, draft[0]]]
            : draft;
      const geometry = { type: draw, coordinates };
      if (geometryErrors(geometry).length)
        throw new Error(
          "Draw one point, at least two line vertices, or at least three distinct polygon vertices.",
        );
      const f: Feature = {
        type: "Feature",
        id: id(),
        geometry,
        properties: {
          name: featureName.trim(),
          review_status: "pending",
          captured_at: now(),
          location_method: "map drawing",
          accuracy_m: null,
        },
      };
      await commit(`Drew ${draw}: ${featureName}`, (p) => {
        const existing = p.layers.find((l) => l.id === target);
        if (existing) existing.features.push(f);
        else addLayer(p, makeLayer(layerName.trim() || "Drawn features", [f]));
      });
      setDraft([]);
      setFeatureName("");
      setDraw("none");
    });
  }
  async function gpkg() {
    if (!layer)
      throw new Error("Select a feature to choose its layer for export.");
    const result = await request<{
      content_base64: string;
      filename: string;
      mime: string;
    }>("export", token, { layer, target_crs: "EPSG:4326" });
    const bytes = Uint8Array.from(atob(result.content_base64), (c) =>
      c.charCodeAt(0),
    );
    download(
      new Blob([bytes], { type: result.mime }),
      result.filename,
      result.mime,
    );
  }
  return (
    <>
      <div className="tag">05 / MAP WORKSPACE</div>
      <h1>
        One shared map.
        <br />
        <em>A clearer next step.</em>
      </h1>
      <p>
        Style and inspect layers, draw a scenario, and leave review notes.
        Export or share a private project from Project & Sync.
      </p>
      <Field label="Filter visible features by attribute text">
        <input
          placeholder="Search all attribute values…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </Field>
      <p className="small">
        Display filter only; analyses and exports use the complete selected
        layer.
      </p>
      <div className="layer-list">
        {project.layers.map((l) => (
          <div className="layer-row" key={l.id}>
            <input
              type="checkbox"
              aria-label={`Show ${l.name}`}
              checked={l.visible}
              disabled={busy}
              onChange={(e) => {
                const visible = e.currentTarget.checked;
                perform(() =>
                  commit(`Visibility: ${l.name}`, (p) => {
                    p.layers.find((x) => x.id === l.id)!.visible = visible;
                  }),
                );
              }}
            />
            <input
              type="color"
              aria-label={`Color ${l.name}`}
              value={l.color}
              disabled={busy}
              onChange={(e) => {
                const value = e.target.value;
                perform(() =>
                  commit(`Styled ${l.name}`, (p) => {
                    p.layers.find((x) => x.id === l.id)!.color = value;
                  }),
                );
              }}
            />
            <div>
              <strong>{l.name}</strong>
              <small>
                {l.features.length} features · {l.source.kind} · rights
                unreviewed
              </small>
            </div>
            <button
              disabled={busy}
              aria-label={`Remove ${l.name}`}
              onClick={() =>
                perform(() =>
                  commit(`Removed layer ${l.name}`, (p) => {
                    p.layers = p.layers.filter((x) => x.id !== l.id);
                  }),
                )
              }
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <details open>
        <summary>Draw a feature / supply scenario</summary>
        <div className="two">
          <Field label="Geometry">
            <select
              value={draw}
              onChange={(e) => {
                setDraw(e.target.value as DrawMode);
                setDraft([]);
              }}
            >
              <option value="none">Inspect</option>
              <option>Point</option>
              <option>LineString</option>
              <option>Polygon</option>
            </select>
          </Field>
          <Field label="Destination">
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">New layer</option>
              {project.layers.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {!target && (
          <Field label="New layer name">
            <input
              value={layerName}
              maxLength={100}
              onChange={(e) => setLayerName(e.target.value)}
            />
          </Field>
        )}
        <Field label="Feature name">
          <input
            value={featureName}
            maxLength={120}
            onChange={(e) => setFeatureName(e.target.value)}
          />
        </Field>
        <p className="small">
          {draft.length} vertices.{" "}
          {draft.map((p) => p.map((n) => n.toFixed(5)).join(", ")).join(" → ")}
        </p>
        <div className="actions">
          <button
            className="primary"
            disabled={busy || draw === "none"}
            onClick={finish}
          >
            Save drawn feature
          </button>
          <button onClick={() => setDraft(draft.slice(0, -1))}>
            Undo vertex
          </button>
          <button
            onClick={() => {
              setDraft([]);
              setDraw("none");
            }}
          >
            Cancel drawing
          </button>
        </div>
      </details>
      {feature && layer && (
        <section className="analysis-result">
          <h3>{label(feature)}</h3>
          <p className="small">
            {layer.name} · {feature.geometry.type} · {layer.source.note}
          </p>
          <pre className="attributes">
            {JSON.stringify(
              {
                ...feature.properties,
                ...(feature.properties.photo_jpeg
                  ? { photo_jpeg: "[local image attachment]" }
                  : {}),
              },
              null,
              2,
            )}
          </pre>
          {typeof feature.properties.photo_jpeg === "string" &&
            /^data:image\/jpeg;base64,/.test(feature.properties.photo_jpeg) && (
              <img
                className="photo"
                src={feature.properties.photo_jpeg}
                alt="Selected field observation"
              />
            )}
          <details>
            <summary>Edit attributes</summary>
            <button
              onClick={() =>
                setAttributes({
                  target: attributeTarget,
                  text: JSON.stringify(feature.properties, null, 2),
                })
              }
            >
              Load current attributes
            </button>
            <Field label="Attribute JSON">
              <textarea
                value={attributeText}
                onChange={(e) =>
                  setAttributes({
                    target: attributeTarget,
                    text: e.target.value,
                  })
                }
              />
            </Field>
            <button
              disabled={busy || !attributeText}
              onClick={() =>
                perform(async () => {
                  if (!attributes || attributes.target !== attributeTarget)
                    throw new Error(
                      "Reload attributes for the selected feature before saving.",
                    );
                  const props = JSON.parse(attributes.text);
                  await commit(`Edited ${label(feature)}`, (p) => {
                    p.layers
                      .find((l) => l.id === layer.id)!
                      .features.find((f) => f.id === feature.id)!.properties =
                      props;
                  });
                  setAttributes(null);
                })
              }
            >
              Save attributes
            </button>
          </details>
          <div className="actions">
            <button
              onClick={() =>
                download(
                  layerGeoJSON(layer),
                  "observatory-layer.geojson",
                  "application/geo+json",
                )
              }
            >
              Layer GeoJSON
            </button>
            <button
              onClick={() =>
                download(layerCSV(layer), "observatory-layer.csv", "text/csv")
              }
            >
              Layer CSV
            </button>
            <button disabled={busy} onClick={() => perform(gpkg)}>
              Private GeoPackage
            </button>
            <button
              disabled={busy}
              onClick={() =>
                perform(() =>
                  commit(`Removed feature ${label(feature)}`, (p) => {
                    const l = p.layers.find((x) => x.id === layer.id)!;
                    l.features = l.features.filter((f) => f.id !== feature.id);
                  }),
                )
              }
            >
              Remove feature
            </button>
          </div>
        </section>
      )}
      <details open>
        <summary>Review notes</summary>
        <Field label="Reviewer name">
          <input
            value={author}
            maxLength={100}
            onChange={(e) => setAuthor(e.target.value)}
          />
        </Field>
        <Field label={feature ? `Note on ${label(feature)}` : "Project note"}>
          <textarea
            value={comment}
            maxLength={4000}
            onChange={(e) => setComment(e.target.value)}
          />
        </Field>
        <button
          disabled={busy || !comment.trim() || !author.trim()}
          onClick={() =>
            perform(async () => {
              await commit("Added review note", (p) => {
                p.comments.push({
                  id: id(),
                  text: comment.trim(),
                  author: author.trim(),
                  featureId: feature?.id ?? null,
                  at: now(),
                });
              });
              setComment("");
            })
          }
        >
          Save note
        </button>
        {project.comments
          .slice()
          .reverse()
          .map((c) => (
            <div className="record" key={c.id}>
              <strong>{c.author}</strong>
              <span>{c.text}</span>
              <small>
                {new Date(c.at).toLocaleString()} ·{" "}
                {c.featureId ? `feature ${c.featureId}` : "project"}
              </small>
            </div>
          ))}
      </details>
    </>
  );
}
