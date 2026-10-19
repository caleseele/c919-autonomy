import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const outDir = path.join(ROOT, 'public', 'models', 'section12');
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: false,
  args: ['--start-maximized', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
page.setDefaultTimeout(30000);
page.on('console', (m) => console.log('C', m.type(), m.text()));

await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('canvas');
for (let i = 0; i < 40; i++) {
  if (await page.evaluate(() => !!(window).__c919Viewer) && (await page.locator('.hud.load').count()) === 0) break;
  await page.waitForTimeout(400);
}
await page.waitForTimeout(3000);
console.log('ready', await page.evaluate(() => !!(window).__c919Viewer));

const plan = [
  { file: 'airchina_left_front.png', index: 1, cam: 'leftFront' },
  { file: 'airchina_right_front.png', index: 1, cam: 'rightFront' },
  { file: 'donghang_left_front.png', index: 2, cam: 'leftFront' },
  { file: 'comac_left_front.png', index: 0, cam: 'leftFront' },
];
let cur = 0;
for (const p of plan) {
  const steps = (p.index - cur + 4) % 4;
  for (let i = 0; i < steps; i++) {
    await page.evaluate(() => window.__c919Viewer.cycleLivery());
    await page.waitForTimeout(400);
  }
  cur = p.index;
  await page.evaluate((cam) => window.__c919Viewer.setLiveryCam(cam), p.cam);
  await page.waitForTimeout(1000);
  const out = path.join(outDir, p.file);
  await page.screenshot({ path: out, type: 'png', timeout: 15000, animations: 'disabled' });
  console.log('SHOT', p.file, fs.statSync(out).size);
}
await browser.close();
console.log('DONE');
