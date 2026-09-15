/**
 * Qiyuan Fingerprint Manager — Storage collection coordinator (background side)
 *
 * localStorage and indexedDB live in renderer processes and cannot be accessed
 * directly from the background service worker. Instead we:
 *   1. Send a message to all active tabs via content_script (injector.js).
 *   2. Each tab reports its origin's localStorage and indexedDB snapshot back
 *      to the background, which accumulates them in chrome.storage.local.
 *   3. collectStorage() reads the accumulated data and clears the temp store.
 */

const LS_KEY = 'qiyuan_collected_localStorage';
const IDB_KEY = 'qiyuan_collected_indexedDB';

/**
 * Ask all open tabs to send their storage data, wait for responses,
 * then return the aggregated result.
 *
 * @param {number} [timeoutMs=3000] — Maximum time to wait for tab responses.
 * @returns {Promise<{localStorage: Object, indexedDB: Object}>}
 */
export async function collectStorage(timeoutMs = 3000) {
  // Clear previous run's data
  await chrome.storage.local.remove([LS_KEY, IDB_KEY]);

  // Broadcast collection request to all eligible tabs
  const tabs = await chrome.tabs.query({ url: ['http://*/*', 'https://*/*'] });
  await Promise.allSettled(
    tabs.map((tab) =>
      chrome.tabs.sendMessage(tab.id, { type: 'QIYUAN_COLLECT_STORAGE' }).catch(() => {
        // Tab may not have the content_script (e.g. chrome:// pages) — ignore
      })
    )
  );

  // Wait for responses to accumulate (content_scripts are async)
  await new Promise((resolve) => setTimeout(resolve, timeoutMs));

  // Read and clear the aggregated data
  const data = await chrome.storage.local.get([LS_KEY, IDB_KEY]);
  await chrome.storage.local.remove([LS_KEY, IDB_KEY]);

  return {
    localStorage: data[LS_KEY] ?? {},
    indexedDB: data[IDB_KEY] ?? {},
  };
}
