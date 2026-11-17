import { useEffect, useRef, useState } from "react";
import {
  Aperture,
  ArrowUpRight,
  CheckCircle2,
  Layers,
  MapPin,
  Radio,
  SlidersHorizontal,
  Sparkles,
  Upload,
  WifiOff,
} from "lucide-react";
import {
  change,
  clone,
  demoState,
  id,
  validateProject,
  type Feature,
  type Layer,
  type LocalState,
  type Project,
} from "../../lib/observatory/model";
import {
  loadLocal,
  loadRecoveryCopies,
  LocalConflict,
  saveLocal,
  type SaveOptions,
} from "../../lib/observatory/store";
import {
  recoveredProject,
  type RecoveryCopy,
} from "../../lib/observatory/recovery";
import {
  checkService,
  pull,
  request,
  type Remote,
} from "../../lib/observatory/api";
import {
  mergeProjects,
  type Choices,
  type MergeConflict,
} from "../../lib/observatory/merge";
import { download, projectBundle } from "../../lib/observatory/export";
import { sendProject } from "../../lib/observatory/sync";
import type { Analysis } from "../../lib/observatory/analysis";
import { Canvas, type DrawMode } from "./canvas";
import {
  CoveragePanel,
  ExplainPanel,
  FieldPanel,
  MapPanel,
  PrepPanel,
} from "./panels";
import { Field } from "./shared";
import "./workspace.css";
const TABS = [
  { name: "MapExplain", icon: Sparkles, detail: "Ask & understand" },
  { name: "Data Prep", icon: Upload, detail: "Import & prepare" },
  { name: "Field Collection", icon: MapPin, detail: "Capture & review" },
  { name: "Coverage Analysis", icon: Radio, detail: "Find & rank gaps" },
  { name: "Map Workspace", icon: Layers, detail: "Draw & collaborate" },
] as const;
type Tab = (typeof TABS)[number]["name"] | "Project & Sync";

export function Observatory() {
  const [state, setState] = useState<LocalState | null>(null),
    current = useRef<LocalState | null>(null),
    saving = useRef(false),
    running = useRef(false);
  const [fatal, setFatal] = useState(""),
    [notice, setNotice] = useState(""),
    [noticeError, setNoticeError] = useState(false),
    [busy, setBusy] = useState(false),
    [online, setOnline] = useState(navigator.onLine);
  const [tab, setTab] = useState<Tab>("MapExplain"),
    [token, setToken] = useState(""),
    [projectName, setProjectName] = useState(""),
    [remoteId, setRemoteId] = useState(
      new URLSearchParams(location.search).get("project") ?? "",
    );
  const [explain, setExplain] = useState<Analysis | null>(null),
    [coverageResult, setCoverage] = useState<Analysis | null>(null),
    [filter, setFilter] = useState(""),
    [draw, setDraw] = useState<DrawMode>("none"),
    [draft, setDraft] = useState<[number, number][]>([]),
    [selection, setSelection] = useState<{
      layerId: string;
      featureId: string;
    } | null>(null);
  const [incoming, setIncoming] = useState<{
      document: Project;
      revision: number;
      source: string;
    } | null>(null),
    [merging, setMerging] = useState<{
      base: Project;
      local: Project;
      remote: Remote;
      revision: number;
      conflicts: MergeConflict[];
    } | null>(null),
    [choices, setChoices] = useState<Choices>({});
  const incomingReview = useRef<HTMLElement | null>(null);
  const [recoveryCopies, setRecoveryCopies] = useState<RecoveryCopy[]>([]),
    [recoveryError, setRecoveryError] = useState("");
  useEffect(() => {
    if (incoming) incomingReview.current?.focus();
  }, [incoming]);
  function show(message: string, error = false) {
    setNotice(message);
    setNoticeError(error);
  }
  useEffect(() => {
    let live = true;
    (async () => {
      let loaded = await loadLocal();
      if (!loaded) {
        const initial = demoState();
        try {
          await saveLocal(initial, null);
          loaded = initial;
        } catch (e) {
          if (!(e instanceof LocalConflict)) throw e;
          loaded = await loadLocal();
        }
      }
      if (!loaded) throw new Error("Local workspace could not be initialized.");
      try {
        const copies = await loadRecoveryCopies();
        if (live) setRecoveryCopies(copies);
      } catch (e) {
        if (live) setRecoveryError(e instanceof Error ? e.message : String(e));
      }
      if (live) {
        current.current = loaded;
        setState(loaded);
        setProjectName(loaded.project.name);
        if (loaded.pendingSend)
          show(
            "An unconfirmed upload is saved on this device. Open Project & Sync, enter the private token again, and retry it before sending newer edits.",
          );
      }
    })().catch((e) => {
      if (live) setFatal(String(e instanceof Error ? e.message : e));
    });
    const connected = () => setOnline(navigator.onLine);
    window.addEventListener("online", connected);
    window.addEventListener("offline", connected);
    return () => {
      live = false;
      window.removeEventListener("online", connected);
      window.removeEventListener("offline", connected);
    };
  }, []);
  async function persist(
    next: LocalState,
    expected: number,
    options: SaveOptions = {},
  ) {
    if (saving.current)
      throw new Error(
        "A local save is already running. Retry after it completes.",
      );
    saving.current = true;
    try {
      const copies = await saveLocal(next, expected, options);
      current.current = next;
      setState(next);
      if (copies) {
        setRecoveryCopies(copies);
        setRecoveryError("");
      }
      show("Saved on this device.");
    } finally {
      saving.current = false;
    }
  }
  async function commit(summary: string, edit: (p: Project) => void) {
    const previous = current.current;
    if (!previous) throw new Error("Workspace not ready.");
    await persist(change(previous, summary, edit), previous.revision);
  }
  function perform(action: () => void | Promise<void>) {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setNotice("");
    Promise.resolve()
      .then(action)
      .catch((e) => show(e instanceof Error ? e.message : String(e), true))
      .finally(() => {
        running.current = false;
        setBusy(false);
      });
  }
  function switchTab(next: Tab) {
    setTab(next);
    if (next !== "Coverage Analysis") setCoverage(null);
    if (next !== "MapExplain") setExplain(null);
    setDraw("none");
    setDraft([]);
    setNotice("");
  }
  function clearView() {
    setExplain(null);
    setCoverage(null);
    setSelection(null);
    setDraft([]);
    setDraw("none");
    setFilter("");
  }
  function reviewMerge(remote: Remote, local: LocalState) {
    if (!local.base)
      throw new Error(
        "No common shared revision exists. Export the local project, then open the shared copy explicitly.",
      );
    const result = mergeProjects(local.base, local.project, remote.document);
    setChoices({});
    setMerging({
      base: clone(local.base),
      local: clone(local.project),
      remote,
      revision: local.revision,
      conflicts: result.conflicts,
    });
    show(
      result.conflicts.length
        ? `Review ${result.conflicts.length} conflicting values. Nothing has been overwritten.`
        : "Nonconflicting edits can be combined. Review and apply the merge below.",
    );
  }
  async function send() {
    const outcome = await sendProject(() => current.current!, persist, token);
    if (outcome.kind === "conflict") {
      reviewMerge(outcome.remote, current.current!);
      return;
    }
    setRemoteId(current.current!.project.id);
    show(
      `Private server confirmed revision ${outcome.remote.revision}. ${current.current!.outbox.length} later local changes remain queued.`,
    );
  }
  async function fetchShared() {
    if (current.current!.pendingSend)
      throw new Error(
        "Retry the unconfirmed upload before fetching a shared project. Newer local edits will stay queued.",
      );
    const remote = await pull(remoteId.trim(), token),
      local = current.current!;
    if (
      remote.document.id === local.project.id &&
      local.base &&
      local.outbox.length
    ) {
      reviewMerge(remote, local);
      return;
    }
    setIncoming({ ...remote, source: "private server" });
  }
  async function applyMerge() {
    const local = current.current!;
    if (!merging || local.revision !== merging.revision)
      throw new Error(
        "Local project changed after merge preview. Fetch the shared project again.",
      );
    const resolved = mergeProjects(
      merging.base,
      merging.local,
      merging.remote.document,
      choices,
    );
    if (resolved.conflicts.length)
      throw new Error("Choose local or shared for every conflicting value.");
    const next = change(
      {
        ...local,
        base: clone(merging.remote.document),
        remoteRevision: merging.remote.revision,
        pendingSend: null,
      },
      "Merged shared project for review",
      (p) => Object.assign(p, resolved.project),
    );
    await persist(next, local.revision);
    setMerging(null);
    clearView();
    show(
      "Merge saved locally. Inspect the project, then push to confirm a new shared revision.",
    );
  }
  async function openIncoming() {
    if (!incoming) return;
    const local = current.current!;
    await persist(
      {
        project: clone(incoming.document),
        revision: local.revision + 1,
        remoteRevision: incoming.revision,
        base: incoming.revision ? clone(incoming.document) : null,
        undo: [],
        outbox: incoming.revision
          ? []
          : [
              {
                id: id(),
                revision: local.revision + 1,
                summary: `Opened project from ${incoming.source}`,
              },
            ],
      },
      local.revision,
      { archiveReason: "Before opening another project" },
    );
    setProjectName(incoming.document.name);
    setIncoming(null);
    setMerging(null);
    clearView();
    show("Project opened and saved on this device.");
  }
  if (!state)
    return (
      <main className="loading">
        <Aperture size={40} />
        <h1>ZQM Observatory</h1>
        <p>{fatal || "Opening your local workspace…"}</p>
        {fatal && (
          <button onClick={() => location.reload()}>Retry local storage</button>
        )}
      </main>
    );
  const project = state.project,
    props = { project, commit, perform, busy };
  const result =
    tab === "MapExplain"
      ? explain
      : tab === "Coverage Analysis"
        ? coverageResult
        : null;
  const select = (f: Feature, l: Layer) =>
    setSelection({ layerId: l.id, featureId: f.id });
  const selectedFeature = project.layers
    .find((l) => l.id === selection?.layerId)
    ?.features.find((f) => f.id === selection?.featureId);
  return (
    <div className="observatory">
      <header className="obs-header">
        <a className="obs-brand" href="./" aria-label="ZQM Observatory home">
          <Aperture size={30} strokeWidth={1.3} />
          <span>
            <small>ZQM COMPUTING</small>
            <strong>
              Observatory<span className="brand-dot">.</span>
            </strong>
          </span>
        </a>
        <div className="header-meta">
          <span className="prototype">WORKING PROTOTYPE</span>
          <button
            className={tab === "Project & Sync" ? "active" : ""}
            onClick={() => switchTab("Project & Sync")}
          >
            <SlidersHorizontal size={15} /> Project & Sync
          </button>
        </div>
      </header>
      <nav className="obs-nav" aria-label="Observatory workspaces">
        {TABS.map(({ name, icon: Icon, detail }, i) => (
          <button
            key={name}
            aria-current={tab === name ? "page" : undefined}
            onClick={() => switchTab(name)}
          >
            <Icon size={18} strokeWidth={1.6} />
            <span>
              <strong>{name}</strong>
              <small>{detail}</small>
            </span>
            <i>0{i + 1}</i>
          </button>
        ))}
      </nav>
      <div className="project-strip">
        <div>
          <span className="status-dot" /> <strong>{project.name}</strong>
          <span>
            {project.layers.length} layers ·{" "}
            {project.layers.reduce((n, l) => n + l.features.length, 0)} features
          </span>
        </div>
        <div>
          {!online && (
            <span>
              <WifiOff size={13} /> Device offline
            </span>
          )}
          <span>
            <CheckCircle2 size={13} /> Saved locally · r{state.revision}
          </span>
          <button onClick={() => switchTab("Project & Sync")}>
            {state.pendingSend
              ? "Unconfirmed upload"
              : `${state.outbox.length} changes to sync`}{" "}
            <ArrowUpRight size={13} />
          </button>
        </div>
      </div>
      {notice && (
        <div
          role={noticeError ? "alert" : "status"}
          className={`notice ${noticeError ? "error" : ""}`}
        >
          {notice}
          <button aria-label="Dismiss message" onClick={() => setNotice("")}>
            ×
          </button>
        </div>
      )}
      <main className="obs-main">
        <section className="workspace-panel" aria-label={tab} key={tab}>
          {tab === "MapExplain" && (
            <ExplainPanel {...props} result={explain} setResult={setExplain} />
          )}
          {tab === "Data Prep" && (
            <PrepPanel {...props} token={token} setToken={setToken} />
          )}
          {tab === "Field Collection" && <FieldPanel {...props} />}
          {tab === "Coverage Analysis" && (
            <CoveragePanel
              {...props}
              result={coverageResult}
              setResult={setCoverage}
            />
          )}
          {tab === "Map Workspace" && (
            <MapPanel
              {...props}
              filter={filter}
              setFilter={setFilter}
              draw={draw}
              setDraw={setDraw}
              draft={draft}
              setDraft={setDraft}
              selection={selection}
              token={token}
            />
          )}
          {tab === "Project & Sync" && (
            <>
              <div className="tag">SHARED FOUNDATION</div>
              <h1>
                Your work, connected.
                <br />
                <em>Every change accounted for.</em>
              </h1>
              <p>
                One local project connects all five workspaces. Private sync
                requires the optional service; this preview has no public
                sharing or account service.
              </p>
              <Field label="Project name">
                <input
                  maxLength={120}
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                />
              </Field>
              <button
                disabled={busy || !projectName.trim()}
                onClick={() =>
                  perform(() =>
                    commit("Renamed project", (p) => {
                      p.name = projectName.trim();
                    }),
                  )
                }
              >
                Save project name
              </button>
              <div className="actions">
                <button
                  className="primary"
                  onClick={() =>
                    download(
                      projectBundle(project),
                      "zqm-observatory-project.json",
                    )
                  }
                >
                  Export project bundle
                </button>
                <button
                  disabled={busy || !state.undo.length}
                  onClick={() =>
                    perform(() =>
                      commit("Restored previous local document", (p) =>
                        Object.assign(p, clone(state.undo.at(-1)!)),
                      ),
                    )
                  }
                >
                  Restore previous document
                </button>
              </div>
              <Field label="Import an Observatory project bundle (8 MB)">
                <input
                  type="file"
                  accept=".json"
                  disabled={busy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file)
                      perform(async () => {
                        if (file.size > 8_000_000)
                          throw new Error("Project bundle exceeds 8 MB.");
                        const document: unknown = JSON.parse(await file.text());
                        validateProject(document);
                        setIncoming({
                          document,
                          revision: 0,
                          source: "bundle",
                        });
                      });
                  }}
                />
              </Field>
              <section
                className="analysis-result"
                aria-label="Local recovery copies"
              >
                <h3>Local recovery copies</h3>
                <p className="small">
                  Opening another project keeps a copy of the current document,
                  including photos. Up to three copies fit within 12 MB; older
                  copies are removed first. These stay on this device and can be
                  lost when browser data is cleared. Export a file for durable
                  backup.
                </p>
                {recoveryError && (
                  <p role="alert">
                    {recoveryError} Export your current project before deleting
                    invalid recovery copies.
                  </p>
                )}
                {!recoveryCopies.length && !recoveryError && (
                  <p className="small">No replaced projects to recover yet.</p>
                )}
                {recoveryCopies.map((copy) => (
                  <article className="record" key={copy.id}>
                    <strong>{copy.project.name}</strong>
                    <small>
                      {new Date(copy.savedAt).toLocaleString()} ·{" "}
                      {copy.project.layers.length} layers
                    </small>
                    <p className="small">{copy.reason}</p>
                    <div className="actions">
                      <button
                        onClick={() =>
                          download(
                            projectBundle(copy.project),
                            "observatory-recovery.json",
                          )
                        }
                      >
                        Export recovery copy
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          perform(() => {
                            setIncoming({
                              document: recoveredProject(copy),
                              revision: 0,
                              source: "local recovery with a new project ID",
                            });
                            setMerging(null);
                          })
                        }
                      >
                        Review recovered copy
                      </button>
                    </div>
                  </article>
                ))}
                <p className="small">
                  A recovered copy gets a new project ID and starts without a
                  shared revision. Review it before opening; the original server
                  project is separate.
                </p>
                <button
                  disabled={busy || (!recoveryCopies.length && !recoveryError)}
                  onClick={() =>
                    perform(async () => {
                      if (
                        !window.confirm(
                          "Permanently delete all local recovery copies, including their photos? The active project, exported files and server copies are separate.",
                        )
                      )
                        return;
                      const latest = current.current!;
                      await persist(
                        { ...latest, revision: latest.revision + 1 },
                        latest.revision,
                        { clearRecovery: true },
                      );
                      show(
                        "Local recovery copies deleted. The active project is still on this device.",
                      );
                    })
                  }
                >
                  Delete recovery copies
                </button>
              </section>
              <section className="analysis-result">
                <h3>Private project sync</h3>
                <p className="small">
                  Project ID: <code>{project.id}</code>
                  <br />
                  Shared revision {state.remoteRevision} · {state.outbox.length}{" "}
                  local changes queued. Device data stays in this browser’s
                  IndexedDB until you replace or clear it. Export a copy for
                  durable backup.
                </p>
                <Field label="Private workspace token">
                  <input
                    type="password"
                    autoComplete="off"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                  />
                </Field>
                <p className="small">
                  Memory only. One token covers this prototype’s private
                  workspace; per-person accounts and access roles are not
                  implemented.
                </p>
                {state.pendingSend && (
                  <p className="small" role="status">
                    An earlier upload is saved for confirmation, including after
                    reload. Retry sends that exact snapshot; newer local edits
                    stay queued for a later push. Enter the private token again
                    after reload. Retry before fetching a shared copy.
                  </p>
                )}
                <div className="actions">
                  <button
                    className="primary"
                    disabled={busy || !online || !token}
                    onClick={() => perform(send)}
                  >
                    {state.pendingSend
                      ? "Retry unconfirmed upload"
                      : "Push local project"}
                  </button>
                  <button
                    disabled={busy || !token}
                    onClick={() =>
                      perform(async () => {
                        await checkService(token);
                        show(
                          "Private service responded and accepted the token.",
                        );
                      })
                    }
                  >
                    Check service
                  </button>
                </div>
                <Field label="Shared project ID to open">
                  <input
                    value={remoteId}
                    maxLength={80}
                    onChange={(e) => setRemoteId(e.target.value)}
                  />
                </Field>
                <div className="actions">
                  <button
                    disabled={
                      busy || !online || !token || Boolean(state.pendingSend)
                    }
                    onClick={() => perform(fetchShared)}
                  >
                    Fetch & review shared project
                  </button>
                  <button
                    onClick={() =>
                      perform(async () => {
                        const url = new URL(location.href);
                        url.search = "";
                        url.searchParams.set("project", project.id);
                        await navigator.clipboard.writeText(url.href);
                        show(
                          "Private project link copied. Recipients need the separately supplied workspace token; the link contains no token or records.",
                        );
                      })
                    }
                  >
                    Copy private project link
                  </button>
                </div>
              </section>
              {incoming && (
                <section
                  className="analysis-result"
                  ref={incomingReview}
                  tabIndex={-1}
                  aria-label="Review incoming project"
                >
                  <h3>Review incoming project</h3>
                  <p>
                    {incoming.document.name} · {incoming.document.layers.length}{" "}
                    layers · from {incoming.source}.
                  </p>
                  <p className="small">
                    Opening this replaces the local document and its undo
                    history. A local recovery copy is saved in the same
                    transaction. Export the current project for a durable
                    backup.
                    {state.pendingSend &&
                      " Opening this also stops retrying the unconfirmed upload. It may already exist on the private server; the recovery copy contains the document, without its upload receipt."}
                  </p>
                  <div className="actions">
                    <button
                      onClick={() =>
                        download(
                          projectBundle(project),
                          "observatory-before-replace.json",
                        )
                      }
                    >
                      Export current project
                    </button>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => perform(openIncoming)}
                    >
                      Open incoming project
                    </button>
                    <button onClick={() => setIncoming(null)}>Cancel</button>
                  </div>
                </section>
              )}
              {merging && (
                <section className="analysis-result">
                  <h3>Review shared changes</h3>
                  <p className="small">
                    Shared revision {merging.remote.revision}. Independent edits
                    combine by entity ID; geometry coordinate arrays stay
                    together.
                  </p>
                  {merging.conflicts.map((c) => (
                    <div className="conflict" key={c.path}>
                      <strong>{c.path}</strong>
                      {c.kind === "layer_name" && (
                        <p className="small">
                          Choose which side keeps the original name. Both layers
                          and their records remain; the other layer receives a
                          numbered suffix.
                        </p>
                      )}
                      <div className="two">
                        <pre>Local: {JSON.stringify(c.local) ?? "deleted"}</pre>
                        <pre>
                          Shared: {JSON.stringify(c.remote) ?? "deleted"}
                        </pre>
                      </div>
                      <Field label="Use this value">
                        <select
                          value={choices[c.path] ?? ""}
                          onChange={(e) =>
                            setChoices((v) => ({
                              ...v,
                              [c.path]: e.target.value as "local" | "remote",
                            }))
                          }
                        >
                          <option value="">Choose…</option>
                          <option value="local">Local</option>
                          <option value="remote">Shared</option>
                        </select>
                      </Field>
                    </div>
                  ))}
                  <button
                    className="primary"
                    disabled={
                      busy || merging.conflicts.some((c) => !choices[c.path])
                    }
                    onClick={() => perform(applyMerge)}
                  >
                    Apply merge locally
                  </button>
                  <button onClick={() => setMerging(null)}>Cancel merge</button>
                </section>
              )}
              <details open>
                <summary>Project history · latest 100 entries</summary>
                {project.history
                  .slice()
                  .reverse()
                  .map((h) => (
                    <div className="record" key={h.id}>
                      <strong>{h.summary}</strong>
                      <small>{new Date(h.at).toLocaleString()}</small>
                    </div>
                  ))}
                {!project.history.length && (
                  <p className="small">
                    Start with an import, observation, or analysis.
                  </p>
                )}
              </details>
              <details>
                <summary>Remove private data</summary>
                <p className="small">
                  Delete the server copy and its retained versions separately
                  from this browser. There is no recovery through this
                  interface.
                </p>
                <button
                  disabled={busy || !token || !state.remoteRevision}
                  onClick={() =>
                    perform(async () => {
                      if (
                        !window.confirm(
                          "Permanently delete this shared project and all retained server versions? Export a backup first.",
                        )
                      )
                        return;
                      await request(
                        `projects/${project.id}`,
                        token,
                        undefined,
                        "DELETE",
                      );
                      const latest = current.current!;
                      await persist(
                        {
                          ...latest,
                          revision: latest.revision + 1,
                          remoteRevision: 0,
                          base: null,
                          pendingSend: null,
                        },
                        latest.revision,
                      );
                      clearView();
                      show(
                        "Private server copy and retained versions deleted. The local project is still on this device.",
                      );
                    })
                  }
                >
                  Delete server project & history
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      if (
                        !window.confirm(
                          "Replace this device project, photos, undo history, and all recovery copies with synthetic examples? Export a backup first.",
                        )
                      )
                        return;
                      const latest = current.current!,
                        fresh = demoState();
                      await persist(
                        { ...fresh, revision: latest.revision + 1 },
                        latest.revision,
                        { clearRecovery: true },
                      );
                      clearView();
                      setProjectName(fresh.project.name);
                      show(
                        "Local project, photo records, undo history, and recovery copies replaced with synthetic examples. Existing exported files and server copies are separate.",
                      );
                    })
                  }
                >
                  Replace device project with synthetic examples
                </button>
              </details>
            </>
          )}
        </section>
        <div className="map-column">
          <Canvas
            layers={project.layers}
            result={result?.layer}
            filter={filter}
            draw={draw}
            draft={draft}
            onDraw={(p) =>
              setDraft((d) => (draw === "Point" ? [p] : [...d, p]))
            }
            onSelect={select}
            selected={
              selection
                ? `${selection.layerId}/${selection.featureId}`
                : undefined
            }
          />
          {selectedFeature && (
            <div className="selection-strip">
              <strong>
                {String(selectedFeature.properties.name ?? selectedFeature.id)}
              </strong>
              <span>{selectedFeature.geometry.type}</span>
              <button onClick={() => switchTab("Map Workspace")}>
                Inspect & edit ↗
              </button>
              <button
                aria-label="Clear selected feature"
                onClick={() => setSelection(null)}
              >
                ×
              </button>
            </div>
          )}
          <footer className="map-footer">
            <span>
              <i /> SYNTHETIC STARTER DATA
            </span>
            <span>
              Imported records retain their source labels · rights unreviewed ·
              publication not authorized
            </span>
          </footer>
        </div>
      </main>
      <footer className="obs-footer">
        <span>
          ZQM COMPUTING <b>/</b> OBSERVATORY
        </span>
        <span>
          {busy ? "Working…" : "Local-first spatial work, with a trail."}
        </span>
        <span>STAGE 0 · PRIVATE REVIEW</span>
      </footer>
    </div>
  );
}
