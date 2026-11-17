import { validateProject, type Project } from "./model.js";

export type Remote = { revision: number; document: Project };
export class SyncConflict extends Error {
  constructor(public current: Remote) {
    super(
      "Shared project changed. Review a three-way merge before sending again.",
    );
  }
}
export async function request<T>(
  path: string,
  token: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  if (!token.trim())
    throw new Error(
      "Enter the private workspace token. It stays in memory and is not added to links or saved projects.",
    );
  const response = await fetch(`/api/${path}`, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
    cache: "no-store",
  });
  const data: unknown = await response
    .json()
    .catch(() => ({
      error: "Private service not configured or returned an invalid response.",
    }));
  if (
    response.status === 409 &&
    data &&
    typeof data === "object" &&
    "current" in data
  ) {
    const current = (data as { current: Remote | null }).current;
    if (!current)
      throw new Error(
        "The shared project was removed. Export your local work and create a new project identity before pushing again.",
      );
    validateProject(current.document);
    if (!Number.isInteger(current.revision) || current.revision < 1)
      throw new Error("Invalid server conflict revision.");
    throw new SyncConflict(current);
  }
  if (!response.ok)
    throw new Error(
      data && typeof data === "object" && "error" in data
        ? String(data.error)
        : `Private service returned ${response.status}.`,
    );
  return data as T;
}
export async function pull(projectId: string, token: string): Promise<Remote> {
  if (!/^[a-zA-Z0-9_-]{1,80}$/.test(projectId))
    throw new Error("Invalid shared project ID.");
  const result = await request<Remote>(
    `projects/${encodeURIComponent(projectId)}`,
    token,
  );
  validateProject(result.document);
  if (!Number.isInteger(result.revision) || result.revision < 1)
    throw new Error("Invalid server revision.");
  return result;
}
export async function push(
  project: Project,
  baseRevision: number,
  operationId: string,
  token: string,
): Promise<Remote> {
  validateProject(project);
  const result = await request<Remote>(
    `projects/${encodeURIComponent(project.id)}`,
    token,
    {
      document: project,
      expected_revision: baseRevision,
      operation_id: operationId,
    },
    "PUT",
  );
  validateProject(result.document);
  if (!Number.isInteger(result.revision) || result.revision < 1)
    throw new Error("Invalid server revision.");
  return result;
}
