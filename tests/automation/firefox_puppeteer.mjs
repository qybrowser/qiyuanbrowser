/** Attach Puppeteer to the existing Firefox environment over WebDriver BiDi. */
import puppeteer from 'puppeteer-core';
import { closeBrowser, openBrowser } from './_api.mjs';

const CODE = 'd72cd8bd2209e2697b28234efaead8d1';
const URL = 'https://example.com';

const opened = await openBrowser(CODE, 'firefox');
let browser;
try {
  browser = await puppeteer.connect({
    browserWSEndpoint: opened.debug_endpoint,
    protocol: 'webDriverBiDi',
  });
  const page = await browser.newPage();
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  console.log({ kernel: opened.browser_kernel, title: await page.title(), url: page.url() });
} finally {
  if (browser) browser.disconnect();
  await closeBrowser(CODE);
}
