import {
  acknowledge,
  clone,
  equalJson,
  id,
  isRecord,
  validateProject,
  type LocalState,
} from "./model.js";
import { push, SyncConflict, type Remote } from "./api.js";

export function validatePendingSend(state: LocalState): void {
  const pending: unknown = state.pendingSend;
  if (pending === null || pending === undefined) return;
  if (
    !isRecord(pending) ||
    !Number.isSafeInteger(state.revision) ||
    state.revision < 1 ||
    state.revision >= Number.MAX_SAFE_INTEGER ||
    Object.keys(pending).some(
      (k) =>
        ![
          "project",
          "localRevision",
          "baseRevision",
          "ops",
          "operation",
        ].includes(k),
    ) ||
    !Number.isSafeInteger(pending.localRevision) ||
    Number(pending.localRevision) < 0 ||
    Number(pending.localRevision) >= state.revision ||
    !Number.isSafeInteger(pending.baseRevision) ||
    Number(pending.baseRevision) < 0 ||
    Number(pending.baseRevision) >= Number.MAX_SAFE_INTEGER ||
    pending.baseRevision !== state.remoteRevision ||
    typeof pending.operation !== "string" ||
    !/^[a-zA-Z0-9_-]{1,80}$/.test(pending.operation) ||
    !Array.isArray(pending.ops) ||
    pending.ops.length > 500 ||
    Array.from(pending.ops).some(
      (op) => typeof op !== "string" || !/^[a-zA-Z0-9_-]{1,80}$/.test(op),
    ) ||
    new Set(pending.ops).size !== pending.ops.length
  )
    throw new Error(
      "The unconfirmed upload could not be validated. No upload was sent.",
    );
  validateProject(pending.project);
  if (pending.project.id !== state.project.id)
    throw new Error(
      "An unconfirmed upload belongs to a different project. No upload was sent.",
    );
}

/** Persist this state before issuing the request. Retrying reuses the exact receipt key and body. */
export function prepareSend(state: LocalState): LocalState {
  validateProject(state.project);
  if (
    !Number.isSafeInteger(state.revision) ||
    state.revision < 0 ||
    state.revision >= Number.MAX_SAFE_INTEGER
  )
    throw new Error("Invalid local revision. No upload was sent.");
  validatePendingSend(state);
  if (state.pendingSend) return state;
  const prepared: LocalState = {
    ...state,
    revision: state.revision + 1,
    pendingSend: {
      project: clone(state.project),
      localRevision: state.revision,
      baseRevision: state.remoteRevision,
      ops: state.outbox.map((o) => o.id),
      operation: id(),
    },
  };
  validatePendingSend(prepared);
  return prepared;
}

export function confirmSend(
  state: LocalState,
  remote: { revision: number; document: unknown },
): LocalState {
  validatePendingSend(state);
  const sent = state.pendingSend;
  if (
    !sent ||
    remote.revision !== sent.baseRevision + 1 ||
    !equalJson(remote.document, sent.project)
  )
    throw new Error(
      "The server did not confirm the saved upload. Its retry and later edits remain on this device.",
    );
  return {
    ...acknowledge(
      state,
      sent.localRevision,
      sent.ops,
      remote.revision,
      sent.project,
    ),
    pendingSend: null,
  };
}

/** Only a validated server conflict or an explicit replacement/deletion ends a failed retry. */
export function clearPendingSend(state: LocalState): LocalState {
  return { ...state, revision: state.revision + 1, pendingSend: null };
}

export async function sendProject(
  read: () => LocalState,
  persist: (next: LocalState, expected: number) => Promise<void>,
  token: string,
): Promise<{ kind: "confirmed" | "conflict"; remote: Remote }> {
  const local = read();
  if (!local.pendingSend) await persist(prepareSend(local), local.revision);
  const queued = read();
  validatePendingSend(queued);
  const snapshot = queued.pendingSend!;
  try {
    const remote = await push(
      snapshot.project,
      snapshot.baseRevision,
      snapshot.operation,
      token,
    );
    const latest = read();
    await persist(confirmSend(latest, remote), latest.revision);
    return { kind: "confirmed", remote };
  } catch (error) {
    if (!(error instanceof SyncConflict)) throw error;
    const latest = read();
    await persist(clearPendingSend(latest), latest.revision);
    return { kind: "conflict", remote: error.current };
  }
}
