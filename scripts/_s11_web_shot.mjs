import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const outDir = path.join(ROOT, 'public', 'models', 'section11');
fs.mkdirSync(outDir, { recursive: true });
const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
const outPath = path.join(outDir, `comac_left_front_${stamp}.png`);

const browser = await chromium.launch({
  headless: true,
  args: [
    '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader',
    '--ignore-gpu-blocklist',
    '--disable-gpu-sandbox',
  ],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.setDefaultTimeout(90000);
page.on('console', (m) => console.log('CONSOLE', m.type(), m.text()));
page.on('pageerror', (e) => console.log('PAGEERR', e.message));
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('canvas', { state: 'attached', timeout: 30000 });
console.log('canvas attached');
// wait for GLB fetch
await page.waitForResponse((r) => r.url().includes('c919.glb') && r.status() === 200, { timeout: 60000 }).catch(() => null);
console.log('glb response ok or skipped');
await page.waitForTimeout(12000);
await page.screenshot({ path: outPath, type: 'png' });
console.log('SHOT=' + outPath);
fs.copyFileSync(outPath, path.join(ROOT, 'logs', 's11_page_raw.png'));
await browser.close();
