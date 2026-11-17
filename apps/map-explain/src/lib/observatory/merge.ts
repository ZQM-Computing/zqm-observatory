import { equalJson, isRecord, validateProject, type Project } from "./model.js";

export type MergeConflict = {
  path: string;
  local: unknown;
  remote: unknown;
  kind?: "layer_name";
};
export type Choices = Record<string, "local" | "remote">;
const equal = equalJson;
const keyed = (v: unknown[]): v is { id: string }[] =>
  v.every((x) => isRecord(x) && typeof x.id === "string") &&
  new Set(v.map((x) => (x as { id: string }).id)).size === v.length;

/** Geometry arrays stay atomic. Entity arrays merge by stable ID, never by index. */
export function mergeProjects(
  base: Project,
  local: Project,
  remote: Project,
  choices: Choices = {},
): { project: Project; conflicts: MergeConflict[] } {
  for (const project of [base, local, remote]) validateProject(project);
  if (new Set([base.id, local.id, remote.id]).size !== 1)
    throw new Error("Cannot merge different projects.");
  const conflicts: MergeConflict[] = [];
  const merge = (b: unknown, l: unknown, r: unknown, path: string): unknown => {
    if (equal(l, r)) return structuredClone(l);
    if (equal(l, b)) return structuredClone(r);
    if (equal(r, b)) return structuredClone(l);
    if (
      Array.isArray(b) &&
      Array.isArray(l) &&
      Array.isArray(r) &&
      keyed(b) &&
      keyed(l) &&
      keyed(r)
    ) {
      const bm = new Map(b.map((v) => [v.id, v])),
        lm = new Map(l.map((v) => [v.id, v])),
        rm = new Map(r.map((v) => [v.id, v]));
      return [...new Set([...lm.keys(), ...rm.keys(), ...bm.keys()])]
        .map((key) =>
          merge(
            bm.get(key),
            lm.get(key),
            rm.get(key),
            `${path}/${encodeURIComponent(key)}`,
          ),
        )
        .filter((v) => v !== undefined);
    }
    if (isRecord(b) && isRecord(l) && isRecord(r)) {
      const out: Record<string, unknown> = Object.create(null);
      for (const key of new Set([
        ...Object.keys(b),
        ...Object.keys(l),
        ...Object.keys(r),
      ])) {
        const result = merge(
          b[key],
          l[key],
          r[key],
          `${path}/${encodeURIComponent(key)}`,
        );
        if (result !== undefined) out[key] = result;
      }
      return out;
    }
    const choice = choices[path];
    if (!choice) conflicts.push({ path, local: l, remote: r });
    return structuredClone(choice === "remote" ? r : l);
  };
  const project = merge(base, local, remote, "project") as Project;
  project.history = project.history.slice(-100);
  // Independent imports have different IDs but can share a name. Keep both
  // datasets and ask which side retains that name; the other gets a suffix.
  const groups = new Map<string, Project["layers"]>();
  for (const layer of project.layers) {
    const name = layer.name.trim().toLowerCase();
    groups.set(name, [...(groups.get(name) ?? []), layer]);
  }
  const occupied = new Set(
    project.layers.map((l) => l.name.trim().toLowerCase()),
  );
  for (const [name, group] of groups) {
    if (group.length < 2) continue;
    const path = `project/layer_names/${encodeURIComponent(name)}`;
    const proposal = (side: Project) => {
      const winner =
        group.find((l) =>
          side.layers.some(
            (s) => s.id === l.id && s.name.trim().toLowerCase() === name,
          ),
        ) ?? group[0];
      const names = new Set(occupied);
      return group.map((l) => {
        let renamed = l.name;
        if (l.id !== winner.id) {
          let suffix = 2;
          const stem = l.name.trim().slice(0, 110);
          do {
            renamed = `${stem} ${suffix++}`;
          } while (names.has(renamed.toLowerCase()));
          names.add(renamed.toLowerCase());
        }
        return { id: l.id, name: renamed };
      });
    };
    const localNames = proposal(local),
      remoteNames = proposal(remote);
    if (!choices[path])
      conflicts.push({
        path,
        local: localNames,
        remote: remoteNames,
        kind: "layer_name",
      });
    const selected = choices[path] === "remote" ? remoteNames : localNames;
    for (const named of selected) {
      group.find((l) => l.id === named.id)!.name = named.name;
      occupied.add(named.name.trim().toLowerCase());
    }
  }
  validateProject(project);
  return { project, conflicts };
}
