const { chromium } = require('playwright-core');
const path = require('path');
const outDir = path.join('public', 'models', 'cockpit-int');

(async () => {
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: ['--disable-gpu-sandbox'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 90000 });
  await page.waitForSelector('canvas', { timeout: 30000 });
  await page.waitForTimeout(6000);
  const buttons = await page.locator('.hud.views button').allTextContents();
  console.log('buttons', JSON.stringify(buttons));
  const shots = [
    { idx: 1, file: 'web_front.png' },
    { idx: 0, file: 'web_oblique45.png' },
    { idx: 2, file: 'web_side.png' },
  ];
  for (const s of shots) {
    await page.locator('.hud.views button').nth(s.idx).click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, s.file), fullPage: false });
    console.log('saved', s.file, require('fs').statSync(path.join(outDir, s.file)).size);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
