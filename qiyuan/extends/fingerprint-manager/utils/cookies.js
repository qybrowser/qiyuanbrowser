/**
 * Qiyuan Fingerprint Manager — Cookie utilities
 *
 * collectCookies() → [{domain, name, value, path, secure, httpOnly, ...}]
 * restoreCookies(cookies) → void
 */

/**
 * Collect all cookies the extension can read.
 * @returns {Promise<chrome.cookies.Cookie[]>}
 */
export async function collectCookies() {
  return chrome.cookies.getAll({});
}

/**
 * Restore cookies from a saved snapshot.
 * Existing cookies with matching (domain + name + path) are overwritten.
 *
 * @param {chrome.cookies.Cookie[]} cookies
 */
export async function restoreCookies(cookies) {
  const results = await Promise.allSettled(
    cookies.map((cookie) => {
      const details = {
        url: cookieUrl(cookie),
        name: cookie.name,
        value: cookie.value,
        domain: cookie.domain,
        path: cookie.path,
        secure: cookie.secure,
        httpOnly: cookie.httpOnly,
        sameSite: cookie.sameSite,
        storeId: cookie.storeId,
      };
      // Only set expiry if the cookie is not a session cookie
      if (!cookie.session && cookie.expirationDate) {
        details.expirationDate = cookie.expirationDate;
      }
      return chrome.cookies.set(details);
    })
  );

  const failed = results.filter((r) => r.status === 'rejected');
  if (failed.length) {
    console.warn(`[QiyuanFM] ${failed.length} cookie(s) failed to restore.`, failed);
  }
}

/**
 * Build a URL string suitable for chrome.cookies.set() from a Cookie object.
 * @param {chrome.cookies.Cookie} cookie
 * @returns {string}
 */
function cookieUrl(cookie) {
  const scheme = cookie.secure ? 'https' : 'http';
  // domain may start with '.' (domain cookie) — strip it for the URL
  const host = cookie.domain.startsWith('.') ? cookie.domain.slice(1) : cookie.domain;
  return `${scheme}://${host}${cookie.path}`;
}
