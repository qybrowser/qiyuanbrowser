/** Local Runtime helper for the Node.js automation examples. */
export const BASE_URL = 'http://127.0.0.1:9003';
export const SERVICE_TOKEN = ''; // Set this if Runtime was started with --service_token.

export async function api(path, body) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(SERVICE_TOKEN ? { 'X-Qiyuan-Runtime-Token': SERVICE_TOKEN } : {}),
    },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!result.success) throw new Error(result.error ?? JSON.stringify(result));
  return result.data;
}

export async function openBrowser(code, kernel) {
  if (code.startsWith('REPLACE_')) throw new Error('Replace CODE with the environment code from /open/env/list');
  const data = await api('/open/env/open', { code, headless: false, needDebugPort: true });
  const protocol = kernel === 'chrome' ? 'cdp' : 'webdriver-bidi';
  if (data.browser_kernel !== kernel || data.debug_protocol !== protocol || !data.debug_endpoint) {
    await api('/open/env/close', { code });
    throw new Error(`Unexpected browser/debug protocol: ${JSON.stringify(data)}`);
  }
  return data;
}

export async function closeBrowser(code) {
  await api('/open/env/close', { code });
}
