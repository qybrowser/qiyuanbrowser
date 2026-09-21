/** Attach Puppeteer to the existing Chromium environment over CDP. */
import puppeteer from 'puppeteer-core';
import { closeBrowser, openBrowser } from './_api.mjs';

const CODE = '20d6fe50631423e693c9260661b33b39';
const URL = 'https://example.com';

const opened = await openBrowser(CODE, 'chrome');
let browser;
try {
  browser = await puppeteer.connect({ browserURL: opened.debug_endpoint });
  const page = await browser.newPage();
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  console.log({ kernel: opened.browser_kernel, title: await page.title(), url: page.url() });
} finally {
  if (browser) browser.disconnect();
  await closeBrowser(CODE);
}
