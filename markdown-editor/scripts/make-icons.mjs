// public/icons/icon.svg から PNG アイコンを生成する(要: Chromium)
import { chromium } from 'playwright-core';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const svg = readFileSync(join(root, 'public/icons/icon.svg'), 'utf-8');

const executablePath = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium';
const browser = await chromium.launch({ executablePath, args: ['--no-sandbox'] });
const page = await browser.newPage();

async function render(size, file, padding = 0) {
  await page.setViewportSize({ width: size, height: size });
  const inner = size - padding * 2;
  await page.setContent(
    `<body style="margin:0;background:${padding ? '#2c3e50' : 'transparent'}">
       <div style="padding:${padding}px"><div style="width:${inner}px;height:${inner}px">${svg.replace(
       '<svg ',
       `<svg width="${inner}" height="${inner}" `
     )}</div></div></body>`
  );
  const buf = await page.screenshot({ omitBackground: !padding, clip: { x: 0, y: 0, width: size, height: size } });
  writeFileSync(join(root, 'public/icons', file), buf);
  console.log('generated', file);
}

await render(192, 'icon-192.png');
await render(512, 'icon-512.png');
// maskable: セーフゾーン確保のため 10% パディング + 背景色
await render(512, 'icon-maskable-512.png', 52);

await browser.close();
