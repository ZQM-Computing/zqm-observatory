import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Copy,
  Download,
  Layers,
  Upload,
  X,
} from "lucide-react";
import { SAMPLE_NOTE } from "@/lib/map-explain/data";
import {
  explainResult,
  run,
  tryAnswer,
  type QueryResult,
  type UploadPoint,
} from "@/lib/map-explain/engine";
import { DEFAULT_QUESTION, EXAMPLES } from "@/lib/map-explain/intent";
import { MAX_FILE_BYTES, parseUpload, type Diagnostic } from "@/lib/map-explain/upload";
import { DEMO_NOTICE, resultCSV, resultGeoJSON, resultSummary } from "@/lib/map-explain/export";
import { EXPORT_BASENAME, FEATURE_NAME, PLATFORM_NAME, PUBLISHER_NAME, VALUE_STATEMENT } from "@/lib/map-explain/identity";
import { MapView } from "@/components/map-explain/map-view";
import { cn } from "@/lib/cn";

const LAYER_TOGGLES: { id: string; label: string }[] = [
  { id: "clinic", label: "Clinics" },
  { id: "park", label: "Parks" },
  { id: "customer", label: "Customers" },
  { id: "warehouse", label: "Warehouse" },
  { id: "upload", label: "Uploaded points" },
];

function download(filename: string, body: string, type: string) {
  const blob = new Blob([body], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function Workspace() {
  const [draft, setDraft] = useState("");
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [upload, setUpload] = useState<UploadPoint[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [uploadName, setUploadName] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult>(() => tryAnswer(DEFAULT_QUESTION, { upload: [] })!);
  const [banner, setBanner] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [layersOpen, setLayersOpen] = useState(false);
  const [hidden, setHidden] = useState<string[]>([]);
  const [showLinks, setShowLinks] = useState(true);
  const [showBuffer, setShowBuffer] = useState(true);
  const [history, setHistory] = useState<string[]>([]);
  const uploadRead = useRef(0);
  const answerRevision = useRef(0);

  useEffect(() => {
    if (!layersOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>(".sheet");
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), a[href], [tabindex="0"]') ?? []);
    focusable()[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLayersOpen(false);
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [layersOpen]);

  useEffect(() => {
    if (!selected) return;
    document.getElementById(`row-${selected}`)?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  function remember(q: string) {
    setHistory((prev) => {
      const next = [q, ...prev.filter((item) => item !== q)].slice(0, 6);
      return next;
    });
  }

  function applyResult(next: QueryResult) {
    setResult(next);
    setSelected(null);
    setShowLinks(true);
    setShowBuffer(true);
    setHidden([]);
    setCopied(false);
  }

  function ask(text: string) {
    const q = text.trim();
    if (q.length < 3 || q.length > 500) return;
    answerRevision.current++;
    setQuestion(q);
    setDraft("");
    setBanner(null);
    remember(q);
    const local = tryAnswer(q, { upload });
    applyResult(local ?? explainResult("Use one of the examples, a sample attribute ranking, or a point-distance question. Routed travel time, other geographies, live conditions, and arbitrary GIS operations are not supported."));
  }

  function clearUpload() {
    uploadRead.current++;
    setUpload([]);
    setUploadName(null);
    setDiagnostics([]);
    setQuestion(DEFAULT_QUESTION);
    setBanner(null);
    applyResult(tryAnswer(DEFAULT_QUESTION, { upload: [] })!);
  }

  async function readFile(file: File) {
    clearUpload();
    const reading = uploadRead.current;
    const answerAtStart = answerRevision.current;
    setLayersOpen(true);
    if (file.size > MAX_FILE_BYTES) {
      setDiagnostics([{ level: "warn", text: "Files over 2 MB are not read." }]);
      return;
    }
    try {
      const parsed = parseUpload(await file.text(), file.name);
      if (reading !== uploadRead.current) return;
      setUpload(parsed.points);
      setDiagnostics(parsed.diagnostics);
      setUploadName(file.name);
      if (parsed.points.length && answerAtStart === answerRevision.current) {
        setQuestion("Show my uploaded points");
        applyResult(run({ kind: "show", layers: ["upload"] }, { upload: parsed.points }));
      }
    } catch {
      if (reading === uploadRead.current) setDiagnostics([{ level: "warn", text: "The file could not be read. No uploaded data is active." }]);
    }
  }

  async function copySummary() {
    const text = resultSummary(result, question);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setBanner("Copying was blocked by the browser.");
    }
  }

  const present = new Set<string>(result.points.map((point) => point.kind));

  return (
    <div
      className="app"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file) readFile(file);
      }}
    >
      <header className="topbar">
        <div className="brand-lockup">
          <p className="brand-parent">{PUBLISHER_NAME} <span aria-hidden="true">·</span> {PLATFORM_NAME}</p>
          <p className="brand-feature">{FEATURE_NAME}</p>
        </div>
        <button type="button" className="ghost-btn" onClick={() => setLayersOpen(true)}>
          <Layers className="size-4" />
          Layers
        </button>
      </header>

      <div className="demo-banner" role="note">
        <strong>Synthetic GIS demo</strong>
        <span>Invented Providence data · Local calculations · Not a released data product</span>
      </div>
      <section className="notebook" aria-label="Answer">
        <div className="notebook-scroll">
          <p className="text-base font-medium text-ink">{VALUE_STATEMENT}</p>
          <p className="mt-1 text-sm text-muted">
            Ask a supported question. Compare locations, find gaps, and inspect the calculation.
          </p>
          <p className="mt-4 font-serif text-lg leading-snug italic text-pretty text-ink">“{question}”</p>
          <div key={result.queryId} className="answer-in mt-4">
            {banner && <p className="mb-3 text-sm text-danger">{banner}</p>}
            <h1 id="answer-title" className="font-serif text-3xl leading-tight text-balance" aria-live="polite">
              {result.title}
            </h1>
            {(
              <>
                <p className="mt-3 text-pretty text-base leading-relaxed">{result.summary}</p>
                <p className="mt-3 text-sm text-muted">{result.viaNote}</p>
                <p className="mt-1 text-sm text-muted">
                  <span className="font-medium text-ink">{result.confidence}.</span> {result.confidenceNote}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button type="button" className="ghost-btn" onClick={() => void copySummary()}>
                    <Copy className="size-4" />
                    {copied ? "Copied" : "Copy"}
                  </button>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => download(`${EXPORT_BASENAME}.geojson`, resultGeoJSON(result, question), "application/geo+json")}
                    disabled={!result.rows.length}
                  >
                    <Download className="size-4" />
                    GeoJSON
                  </button>
                  <button
                    type="button"
                    className="ghost-btn"
                    disabled={!result.rows.length}
                    onClick={() => {
                      download(`${EXPORT_BASENAME}.csv`, resultCSV(result, question), "text/csv");
                    }}
                  >
                    <Download className="size-4" />
                    CSV
                  </button>
                </div>
                <h2 className="eyebrow mt-6">Steps</h2>
                <ol className="mt-3 flex flex-col gap-3">
                  {result.steps.map((step, index) => (
                    <li key={step.title} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
                      <span className="grid size-8 place-items-center rounded-full bg-mist font-mono text-sm text-pine">
                        {index + 1}
                      </span>
                      <div>
                        <p className="font-medium">{step.title}</p>
                        <p className="text-sm text-pretty text-muted">{step.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
                {result.rows.length > 0 && (
                  <>
                    <h2 className="eyebrow mt-6">Ranked result</h2>
                    <ul className="mt-3 flex flex-col gap-2">
                      {result.rows.map((row) => (
                        <li key={row.id}>
                          <button
                            id={`row-${row.id}`}
                            type="button"
                            className={cn("result-row", selected === row.id && "result-row-on")}
                            aria-current={selected === row.id ? "true" : undefined}
                            onClick={() => setSelected(row.id)}
                          >
                            <span className="flex items-baseline justify-between gap-3">
                              <span className="font-medium">{row.name}</span>
                              <span className="shrink-0 text-sm tabular-nums">{row.primary}</span>
                            </span>
                            <span className="mt-1 block text-sm text-muted">{row.secondary}</span>
                            <span className="mt-2 block h-1 overflow-hidden rounded-full bg-paper-2">
                              <span className="block h-full bg-pine" style={{ width: `${Math.round(row.bar * 100)}%` }} />
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                <h2 className="eyebrow mt-6">Sources</h2>
                <ul className="mt-3 flex flex-col gap-2">
                  {result.sources.map((source) => (
                    <li key={source.name}>
                      <p className="text-sm font-medium">{source.name}</p>
                      <p className="text-sm text-pretty text-muted">{source.detail}</p>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-sm text-pretty text-faint">{SAMPLE_NOTE}</p>
              </>
            )}
          </div>
        </div>
        <form
          className="askbar"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(draft);
          }}
        >
          <div className="chip-row">
            {EXAMPLES.map((example) => (
              <button
                key={example.label}
                type="button"
                className="chip"
                onClick={() => void ask(example.question)}
              >
                {example.label}
              </button>
            ))}
          </div>
          {history.length > 0 && (
            <div className="chip-row">
              {history.slice(0, 3).map((item) => (
                <button key={item} type="button" className="chip chip-quiet" onClick={() => void ask(item)}>
                  {item.length > 42 ? `${item.slice(0, 40)}…` : item}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="ask-input">
              Ask a location question
            </label>
            <input
              id="ask-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about distance, rank, or a gap"
              className="ask-input"
              maxLength={500}
            />
            <button type="submit" className="primary-btn" disabled={draft.trim().length < 3}>
              <ArrowUp className="size-4" />
              Ask
            </button>
          </div>
        </form>
      </section>

      <MapView
        result={result}
        selectedId={selected}
        onSelect={setSelected}
        showLinks={showLinks}
        showBuffer={showBuffer}
        hiddenKinds={hidden}
      />

      {layersOpen && (
        <div className="scrim" onClick={() => setLayersOpen(false)}>
          <div
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="layers-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="layers-title" className="font-serif text-2xl italic">
                  Layers
                </h2>
                <p className="mt-1 text-sm text-muted">Turn layers off, or add your own points.</p>
              </div>
              <button type="button" className="icon-btn" aria-label="Close layers" onClick={() => setLayersOpen(false)}>
                <X className="size-4" />
              </button>
            </div>
            <ul className="mt-5 flex flex-col gap-2">
              {LAYER_TOGGLES.map((layer) => {
                const available = present.has(layer.id);
                const off = hidden.includes(layer.id);
                return (
                  <li key={layer.id}>
                    <button
                      type="button"
                      className="toggle-row"
                      aria-pressed={!off && available}
                      disabled={!available}
                      onClick={() =>
                        setHidden((current) =>
                          current.includes(layer.id)
                            ? current.filter((id) => id !== layer.id)
                            : [...current, layer.id],
                        )
                      }
                    >
                      <span>{layer.label}</span>
                      <span className="text-sm text-muted">
                        {!available ? "Not in this answer" : off ? "Hidden" : "Shown"}
                      </span>
                    </button>
                  </li>
                );
              })}
              <li>
                <button
                  type="button"
                  className="toggle-row"
                  aria-pressed={showLinks}
                  disabled={!result.lines.length}
                  onClick={() => setShowLinks((value) => !value)}
                >
                  <span>Links</span>
                  <span className="text-sm text-muted">
                    {result.lines.length ? (showLinks ? "Shown" : "Hidden") : "None for this answer"}
                  </span>
                </button>
              </li>
              <li>
                <button
                  type="button"
                  className="toggle-row"
                  aria-pressed={showBuffer}
                  disabled={!result.buffers.length}
                  onClick={() => setShowBuffer((value) => !value)}
                >
                  <span>Distance ring</span>
                  <span className="text-sm text-muted">
                    {result.buffers.length ? (showBuffer ? "Shown" : "Hidden") : "None for this answer"}
                  </span>
                </button>
              </li>
            </ul>
            <div className="mt-6">
              <h3 className="font-medium">Add points</h3>
              <p className="mt-1 text-sm text-pretty text-muted">
                Use synthetic or permitted public, nonpersonal points. CSV needs latitude/longitude in WGS84 degrees; GeoJSON accepts Point features only. Files and questions stay in this tab; nothing is sent for analysis. Reloading clears them.
              </p>
              <label className="dropzone">
                <Upload className="size-4" />
                <span>{uploadName ? `${uploadName} · ${upload.length} points` : "Drop a file or browse"}</span>
                <input
                  type="file"
                  accept=".csv,.json,.geojson,text/csv,application/geo+json,application/json"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) readFile(file);
                    event.target.value = "";
                  }}
                />
              </label>
              {uploadName && <button type="button" className="ghost-btn mt-3" onClick={clearUpload}>Remove uploaded file</button>}
              {upload.length > 0 && (
                <button
                  type="button"
                  className="chip mt-3"
                  onClick={() => {
                    setLayersOpen(false);
                    void ask("Which of my locations are more than 1 km from a clinic?");
                  }}
                >
                  Ask which of my points are over 1 km from a clinic
                </button>
              )}
              <ul className="mt-3 flex flex-col gap-2">
                {diagnostics.map((item, index) => (
                  <li key={`${item.text}-${index}`} className={item.level === "warn" ? "text-sm text-danger" : "text-sm text-muted"}>
                    {item.text}
                  </li>
                ))}
              </ul>
            </div>
            <p className="mt-6 text-sm text-pretty text-faint">{DEMO_NOTICE} {SAMPLE_NOTE}</p>
          </div>
        </div>
      )}
    </div>
  );
}
