const { chromium } = require('playwright');
const path = require('path');
const outDir = path.join('public', 'models', 'cockpit-int');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 60000 });
  // wait for canvas and model
  await page.waitForSelector('canvas', { timeout: 30000 });
  await page.waitForTimeout(4000);
  // dismiss any load message wait
  const views = [
    { label: '前视', file: 'web_front.png' },
    { label: '斜视', file: 'web_oblique45.png' },
    { label: '侧视', file: 'web_side.png' },
  ];
  // buttons may show garbled in source but text content in DOM should be Chinese
  const buttons = await page.locator('.hud.views button').allTextContents();
  console.log('buttons', JSON.stringify(buttons));
  for (const v of views) {
    const btn = page.locator('.hud.views button', { hasText: v.label });
    if (await btn.count()) {
      await btn.click();
    } else {
      // fallback by index: 斜视0 前视1 侧视2 俯视3
      const idx = v.file.includes('front') ? 1 : v.file.includes('side') ? 2 : 0;
      await page.locator('.hud.views button').nth(idx).click();
    }
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(outDir, v.file), fullPage: false });
    console.log('saved', v.file);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
