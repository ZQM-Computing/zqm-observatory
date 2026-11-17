import { clone, validateProject, type LocalState } from "./model.js";

export class LocalConflict extends Error {}
const DB_NAME = "zqm-observatory-workspace-v1";
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("workspace");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error("Local storage unavailable."));
    request.onblocked = () =>
      reject(
        new Error("Close other Observatory tabs to upgrade local storage."),
      );
  });
}
export async function loadLocal(): Promise<LocalState | null> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("workspace", "readonly"),
      request = tx.objectStore("workspace").get("active");
    let result: LocalState | null = null;
    request.onsuccess = () => {
      result = request.result ?? null;
    };
    tx.oncomplete = () => {
      db.close();
      try {
        if (result) validateProject(result.project);
        resolve(result);
      } catch (e) {
        reject(e);
      }
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
/** Read/compare/write share one transaction; a second tab cannot silently replace edits. */
export async function saveLocal(
  state: LocalState,
  expected: number | null,
): Promise<void> {
  validateProject(state.project);
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("workspace", "readwrite"),
      store = tx.objectStore("workspace"),
      request = store.get("active");
    let conflict = false;
    request.onsuccess = () => {
      const previous = request.result as LocalState | undefined;
      if ((previous?.revision ?? null) !== expected) {
        conflict = true;
        tx.abort();
        return;
      }
      store.put(clone(state), "active");
    };
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onabort = tx.onerror = () => {
      db.close();
      reject(
        conflict
          ? new LocalConflict(
              "This project changed in another tab. Reload it before saving; your form has not been submitted.",
            )
          : (tx.error ??
              new Error("Local save failed. Export your work before closing.")),
      );
    };
  });
}

export async function clearLocal(): Promise<void> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("workspace", "readwrite");
    tx.objectStore("workspace").clear();
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
