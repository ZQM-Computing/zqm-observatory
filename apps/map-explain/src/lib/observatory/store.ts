import { clone, validateProject, type LocalState } from "./model.js";
import {
  archiveProject,
  readRecoveryCopies,
  type RecoveryCopy,
} from "./recovery.js";

export type SaveOptions = { archiveReason?: string; clearRecovery?: boolean };

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
    tx.onabort = tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
/** Read/compare/write share one transaction; a second tab cannot silently replace edits. */
export async function saveLocal(
  state: LocalState,
  expected: number | null,
  options: SaveOptions = {},
): Promise<RecoveryCopy[] | null> {
  validateProject(state.project);
  if (options.archiveReason && options.clearRecovery)
    throw new Error("Cannot preserve and delete recovery copies in one save.");
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("workspace", "readwrite"),
      store = tx.objectStore("workspace"),
      request = store.get("active");
    let conflict = false;
    let copies: RecoveryCopy[] | null = null;
    let failure: unknown;
    function write(nextCopies: RecoveryCopy[] | null) {
      try {
        if (nextCopies !== null) {
          if (nextCopies.length) store.put(nextCopies, "recovery");
          else store.delete("recovery");
        }
        store.put(clone(state), "active");
        copies = nextCopies;
      } catch (e) {
        failure = e;
        tx.abort();
      }
    }
    request.onsuccess = () => {
      const previous = request.result as LocalState | undefined;
      if ((previous?.revision ?? null) !== expected) {
        conflict = true;
        tx.abort();
        return;
      }
      if (options.archiveReason && previous) {
        const recovery = store.get("recovery");
        recovery.onsuccess = () => {
          try {
            write(
              archiveProject(
                previous.project,
                options.archiveReason!,
                recovery.result,
              ),
            );
          } catch (e) {
            failure = e;
            tx.abort();
          }
        };
      } else {
        write(options.clearRecovery ? [] : null);
      }
    };
    tx.oncomplete = () => {
      db.close();
      resolve(copies);
    };
    tx.onabort = tx.onerror = () => {
      db.close();
      reject(
        conflict
          ? new LocalConflict(
              "This project changed in another tab. Reload it before saving; your form has not been submitted.",
            )
          : (failure ??
              tx.error ??
              new Error("Local save failed. Export your work before closing.")),
      );
    };
  });
}

export async function loadRecoveryCopies(): Promise<RecoveryCopy[]> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("workspace", "readonly"),
      request = tx.objectStore("workspace").get("recovery");
    tx.oncomplete = () => {
      db.close();
      try {
        resolve(readRecoveryCopies(request.result));
      } catch (e) {
        reject(e);
      }
    };
    tx.onabort = tx.onerror = () => {
      db.close();
      reject(tx.error ?? new Error("Local recovery copies could not be read."));
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
    tx.onabort = tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
