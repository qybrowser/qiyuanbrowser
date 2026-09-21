/** Inject JavaScript into the existing Firefox browser (BiDi + Puppeteer). */
import puppeteer from 'puppeteer-core';
import { closeBrowser, openBrowser } from './_api.mjs';

const CODE = 'd72cd8bd2209e2697b28234efaead8d1';
const URL = 'https://example.com';
const CROSS_ORIGIN_URL = ''; // Optional CORS-enabled URL, e.g. 'https://api.example.net/data'
const EXTERNAL_SCRIPT_URL = ''; // Optional trusted JS URL; subject to the page's CSP.

const opened = await openBrowser(CODE, 'firefox');
let browser;
try {
  browser = await puppeteer.connect({
    browserWSEndpoint: opened.debug_endpoint,
    protocol: 'webDriverBiDi',
  });
  const page = await browser.newPage();

  // Register before navigation so the marker exists when page scripts start.
  await page.evaluateOnNewDocument(() => {
    window.__automationStartedAt = Date.now();
  });
  await page.goto(URL, { waitUntil: 'domcontentloaded' });

  // Page-side JS can read/change the DOM, storage and page globals.
  const snapshot = await page.evaluate((label) => {
    const note = document.createElement('div');
    note.id = 'automation-note';
    note.textContent = label;
    note.style.cssText = 'padding:8px;background:#dff5ff;color:#222';
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
  }, 'Injected by Firefox');
  console.log('Page snapshot:', snapshot);

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
