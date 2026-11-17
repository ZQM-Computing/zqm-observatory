import { equalJson, isRecord, validateProject, type Project } from "./model.js";

export type Remote = { revision: number; document: Project };
export class SyncConflict extends Error {
  constructor(public current: Remote) {
    super(
      "Shared project changed. Review a three-way merge before sending again.",
    );
  }
}
function remoteProject(value: unknown, expectedId: string): Remote {
  if (
    !isRecord(value) ||
    !Number.isSafeInteger(value.revision) ||
    Number(value.revision) < 1
  )
    throw new Error(
      "Private service returned an invalid project response or revision.",
    );
  validateProject(value.document);
  if (value.document.id !== expectedId)
    throw new Error(
      "Private service returned a different project. Your local project has not been replaced.",
    );
  return { revision: Number(value.revision), document: value.document };
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
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "Private service not configured or returned an invalid JSON response.",
    );
  }
  const projectPath = /^projects\/([a-zA-Z0-9_-]{1,80})$/.exec(path);
  if (response.status === 409 && projectPath) {
    if (!isRecord(data) || !("current" in data))
      throw new Error(
        "Private service returned an invalid conflict response. Your upload remains unconfirmed.",
      );
    if (data.current === null)
      throw new Error(
        "The shared project was removed. Export your local work and create a new project identity before pushing again.",
      );
    throw new SyncConflict(remoteProject(data.current, projectPath[1]));
  }
  if (!response.ok)
    throw new Error(
      data && typeof data === "object" && "error" in data
        ? String(data.error)
        : `Private service returned ${response.status}.`,
    );
  return data as T;
}
export async function checkService(token: string): Promise<void> {
  const result = await request<unknown>("health", token);
  if (
    !isRecord(result) ||
    result.status !== "ready" ||
    result.publication_authorized !== false
  )
    throw new Error(
      "Private service did not return the expected authenticated readiness response.",
    );
}
export async function pull(projectId: string, token: string): Promise<Remote> {
  if (typeof projectId !== "string" || !/^[a-zA-Z0-9_-]{1,80}$/.test(projectId))
    throw new Error("Invalid shared project ID.");
  const result = await request<unknown>(
    `projects/${encodeURIComponent(projectId)}`,
    token,
  );
  return remoteProject(result, projectId);
}
export async function push(
  project: Project,
  baseRevision: number,
  operationId: string,
  token: string,
): Promise<Remote> {
  validateProject(project);
  if (
    !Number.isSafeInteger(baseRevision) ||
    baseRevision < 0 ||
    baseRevision >= Number.MAX_SAFE_INTEGER ||
    typeof operationId !== "string" ||
    !/^[a-zA-Z0-9_-]{1,80}$/.test(operationId)
  )
    throw new Error("Invalid upload revision or operation identity.");
  const result = remoteProject(
    await request<unknown>(
      `projects/${encodeURIComponent(project.id)}`,
      token,
      {
        document: project,
        expected_revision: baseRevision,
        operation_id: operationId,
      },
      "PUT",
    ),
    project.id,
  );
  if (
    result.revision !== baseRevision + 1 ||
    !equalJson(result.document, project)
  )
    throw new Error(
      "Private service did not confirm this exact upload. Retry it before sending later changes.",
    );
  return result;
}
