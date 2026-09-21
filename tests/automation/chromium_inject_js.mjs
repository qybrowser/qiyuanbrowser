/** Inject JavaScript into the existing Chromium browser (CDP + Puppeteer). */
import puppeteer from 'puppeteer-core';
import { closeBrowser, openBrowser } from './_api.mjs';

const CODE = '20d6fe50631423e693c9260661b33b39';
const URL = 'https://example.com';
// Use an endpoint you control that sends Access-Control-Allow-Origin for URL's origin.
const CROSS_ORIGIN_URL = ''; // e.g. 'https://api.example.net/data'
const EXTERNAL_SCRIPT_URL = ''; // Optional trusted JS URL; the page's CSP may block it.

const opened = await openBrowser(CODE, 'chrome');
let browser;
try {
  browser = await puppeteer.connect({ browserURL: opened.debug_endpoint });
  const page = await browser.newPage();

  // Runs before page scripts on every navigation in this tab. Install before goto().
  await page.evaluateOnNewDocument(() => {
    window.__automationStartedAt = Date.now();
  });
  await page.goto(URL, { waitUntil: 'domcontentloaded' });

  // evaluate() executes in the page. Pass data as arguments; return serializable values.
  const snapshot = await page.evaluate((label) => {
    const note = document.createElement('div');
    note.id = 'automation-note';
    note.textContent = label;
    note.style.cssText = 'padding:8px;background:#fff4c2;color:#222';
    document.body.append(note);
    sessionStorage.setItem('automation-demo', label);
    return {
      title: document.title,
      url: location.href,
      headings: [...document.querySelectorAll('h1, h2')].map((el) => el.textContent.trim()),
      note: document.querySelector('#automation-note')?.textContent,
      stored: sessionStorage.getItem('automation-demo'),
      startedAt: window.__automationStartedAt,
    };
  }, 'Injected by Chromium');
  console.log('Page snapshot:', snapshot);

  // Inline script runs in the page too. Use a trusted URL for external scripts.
  await page.addScriptTag({ content: 'window.__injectedScriptRan = true;' });
  if (EXTERNAL_SCRIPT_URL) await page.addScriptTag({ url: EXTERNAL_SCRIPT_URL });
  console.log('Script tag ran:', await page.evaluate(() => window.__injectedScriptRan));

  if (CROSS_ORIGIN_URL) {
    try {
      const result = await page.evaluate(async (url) => {
        const response = await fetch(url, { credentials: 'omit' });
        return { status: response.status, body: (await response.text()).slice(0, 500) };
      }, CROSS_ORIGIN_URL);
      console.log('Cross-origin fetch:', result);
    } catch (error) {
      console.log('Cross-origin fetch failed (check CORS, CSP, and network):', error.message);
    }
  }
} finally {
  if (browser) browser.disconnect();
  await closeBrowser(CODE);
}
