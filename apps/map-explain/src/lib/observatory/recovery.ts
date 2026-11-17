import {
  clone,
  id,
  isRecord,
  MAX_BYTES,
  now,
  validateProject,
  type Project,
} from "./model.js";

export type RecoveryCopy = {
  id: string;
  savedAt: string;
  reason: string;
  project: Project;
};
export const MAX_RECOVERY_COPIES = 3;
export const MAX_RECOVERY_BYTES = 12_000_000;
const bytes = (value: unknown) =>
  new TextEncoder().encode(JSON.stringify(value)).byteLength;

export function readRecoveryCopies(value: unknown): RecoveryCopy[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > MAX_RECOVERY_COPIES)
    throw new Error("Local recovery copies could not be validated.");
  const seen = new Set<string>();
  for (const copy of value) {
    if (
      !isRecord(copy) ||
      typeof copy.id !== "string" ||
      !copy.id ||
      seen.has(copy.id) ||
      typeof copy.savedAt !== "string" ||
      !Number.isFinite(Date.parse(copy.savedAt)) ||
      typeof copy.reason !== "string" ||
      !copy.reason.trim() ||
      copy.reason.length > 160
    )
      throw new Error("Local recovery copies could not be validated.");
    validateProject(copy.project);
    seen.add(copy.id);
  }
  if (bytes(value) > MAX_RECOVERY_BYTES)
    throw new Error("Local recovery copies exceed their storage budget.");
  return value as RecoveryCopy[];
}

/** Keep the latest replacement, then prune the oldest copies to both limits. */
export function archiveProject(
  project: Project,
  reason: string,
  existing: unknown,
): RecoveryCopy[] {
  validateProject(project);
  const copies: RecoveryCopy[] = [
    { id: id(), savedAt: now(), reason, project: clone(project) },
    ...readRecoveryCopies(existing),
  ].slice(0, MAX_RECOVERY_COPIES);
  while (bytes(copies) > MAX_RECOVERY_BYTES && copies.length > 1) copies.pop();
  return readRecoveryCopies(copies);
}

/** A recovered document gets a fresh identity and cannot overwrite its old server copy. */
export function recoveredProject(copy: RecoveryCopy): Project {
  readRecoveryCopies([copy]);
  const project = clone(copy.project);
  project.id = id();
  if (bytes(project) > MAX_BYTES)
    throw new Error(
      "A new project ID would exceed the 8 MB limit. Export this recovery copy, then import that file to restore its original project ID.",
    );
  const history = [
    ...project.history,
    {
      id: id(),
      at: now(),
      summary: `Recovered local copy saved ${copy.savedAt}`,
    },
  ].slice(-100);
  // Preserve a valid project at the size ceiling; the recovery receipt itself
  // remains in the local queue if another history entry would exceed the limit.
  if (bytes({ ...project, history }) <= MAX_BYTES) project.history = history;
  validateProject(project);
  return project;
}
