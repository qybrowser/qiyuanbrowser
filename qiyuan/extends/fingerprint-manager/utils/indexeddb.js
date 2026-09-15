/**
 * Qiyuan Fingerprint Manager — IndexedDB utilities (renderer/content_script side)
 *
 * These functions run inside a content_script (renderer process) where
 * IndexedDB is accessible.
 *
 * collectIndexedDB() — dump all databases, object stores, and records for
 *                      the current origin.
 * restoreIndexedDB(snapshot) — write a previously collected snapshot back.
 *
 * Snapshot format:
 * {
 *   "dbName": {
 *     "version": 2,
 *     "stores": {
 *       "storeName": [record, record, ...]
 *     }
 *   }
 * }
 */

/**
 * Collect all IndexedDB data for the current origin.
 * @returns {Promise<Object>} snapshot keyed by database name
 */
export async function collectIndexedDB() {
  const snapshot = {};
  let dbInfoList = [];

  try {
    dbInfoList = await indexedDB.databases();
  } catch {
    // indexedDB.databases() may be unavailable on some origins; return empty.
    return snapshot;
  }

  await Promise.allSettled(
    dbInfoList.map(async ({ name, version }) => {
      try {
        const dbSnapshot = await dumpDatabase(name, version);
        snapshot[name] = dbSnapshot;
      } catch (err) {
        console.warn(`[QiyuanFM] Failed to dump IDB database "${name}":`, err);
      }
    })
  );

  return snapshot;
}

/**
 * Open a database and dump all records from every object store.
 * @param {string} name
 * @param {number} version
 * @returns {Promise<{version: number, stores: Object}>}
 */
async function dumpDatabase(name, version) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(name, version);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const db = req.result;
      const storeNames = Array.from(db.objectStoreNames);
      const stores = {};
      const tx = db.transaction(storeNames, 'readonly');

      Promise.allSettled(
        storeNames.map(
          (storeName) =>
            new Promise((res, rej) => {
              const records = [];
              const cursorReq = tx.objectStore(storeName).openCursor();
              cursorReq.onsuccess = (e) => {
                const cursor = e.target.result;
                if (cursor) {
                  records.push({ key: cursor.key, value: cursor.value });
                  cursor.continue();
                } else {
                  stores[storeName] = records;
                  res();
                }
              };
              cursorReq.onerror = () => rej(cursorReq.error);
            })
        )
      ).then(() => {
        db.close();
        resolve({ version, stores });
      });
    };
  });
}

/**
 * Restore an IndexedDB snapshot for the current origin.
 * Existing data in each object store is cleared before writing.
 *
 * @param {Object} snapshot — as returned by collectIndexedDB()
 */
export async function restoreIndexedDB(snapshot) {
  for (const [dbName, dbData] of Object.entries(snapshot)) {
    try {
      await restoreDatabase(dbName, dbData);
    } catch (err) {
      console.warn(`[QiyuanFM] Failed to restore IDB database "${dbName}":`, err);
    }
  }
}

/**
 * @param {string} dbName
 * @param {{version: number, stores: Object}} dbData
 */
async function restoreDatabase(dbName, { version, stores }) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(dbName, version);
    req.onerror = () => reject(req.error);

    // onupgradeneeded fires when the DB doesn't exist or version is newer —
    // we skip schema changes here as we're just writing data.
    req.onupgradeneeded = () => {
      // No-op: the schema must already exist for puts to succeed.
      // Full schema recreation would require storing createObjectStore args,
      // which is a future enhancement.
    };

    req.onsuccess = () => {
      const db = req.result;
      const storeNames = Object.keys(stores).filter((s) =>
        db.objectStoreNames.contains(s)
      );
      if (storeNames.length === 0) {
        db.close();
        resolve();
        return;
      }
      const tx = db.transaction(storeNames, 'readwrite');
      tx.oncomplete = () => { db.close(); resolve(); };
      tx.onerror = () => { db.close(); reject(tx.error); };

      for (const storeName of storeNames) {
        const store = tx.objectStore(storeName);
        store.clear();
        for (const { key, value } of stores[storeName]) {
          store.put(value, key);
        }
      }
    };
  });
}
