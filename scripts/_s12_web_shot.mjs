import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const outDir = path.join(ROOT, 'public', 'models', 'section12');
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
page.setDefaultTimeout(45000);
page.on('console', (m) => console.log('C', m.type(), m.text()));

await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('canvas');
for (let i = 0; i < 40; i++) {
  if (await page.evaluate(() => !!(window).__c919Viewer) && (await page.locator('.hud.load').count()) === 0) break;
  await page.waitForTimeout(400);
}
await page.waitForTimeout(4000);
console.log('ready', await page.evaluate(() => !!(window).__c919Viewer));

const plan = [
  { file: 'airchina_left_front.png', index: 1, cam: 'leftFront' },
  { file: 'airchina_right_front.png', index: 1, cam: 'rightFront' },
  { file: 'donghang_left_front.png', index: 2, cam: 'leftFront' },
  { file: 'comac_left_front.png', index: 0, cam: 'leftFront' },
];
let cur = 0;
const shots = [];
for (const p of plan) {
  const steps = (p.index - cur + 4) % 4;
  for (let i = 0; i < steps; i++) {
    await page.evaluate(() => window.__c919Viewer.cycleLivery());
    await page.waitForTimeout(500);
  }
  cur = p.index;
  await page.evaluate((cam) => window.__c919Viewer.setLiveryCam(cam), p.cam);
  await page.waitForTimeout(1200);
  const out = path.join(outDir, p.file);
  // Prefer canvas data URL (preserveDrawingBuffer now on)
  const dataUrl = await Promise.race([
    page.evaluate(() => document.querySelector('canvas').toDataURL('image/png')),
    new Promise((_, rej) => setTimeout(() => rej(new Error('toDataURL timeout')), 15000)),
  ]).catch((e) => { console.log(e.message); return null; });
  if (dataUrl) {
    fs.writeFileSync(out, Buffer.from(dataUrl.split(',')[1], 'base64'));
  } else {
    await page.screenshot({ path: out, type: 'png', timeout: 20000, animations: 'disabled' });
  }
  const sz = fs.statSync(out).size;
  console.log('SHOT', p.file, sz);
  shots.push(out);
}
await browser.close();

// collage with python-less: write a list file for later
fs.writeFileSync(path.join(outDir, 'shots.json'), JSON.stringify(shots, null, 2));
console.log('DONE');
