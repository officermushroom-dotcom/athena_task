import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const browser = process.env.CHROME_BIN || (existsSync(edge) ? edge : 'chromium');
const output = fileURLToPath(new URL('athena_poc_report.pdf', import.meta.url));
const profile = mkdtempSync(join(tmpdir(), 'athena-pdf-'));
const source = new URL("."+profile.split(/[\\/]/).pop()+".html", import.meta.url);
const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
try {
  const { default: Slides } = await vite.ssrLoadModule('/reports/Slides.tsx');
  const body = renderToStaticMarkup(React.createElement(Slides))
    .replaceAll('"/outputs/', '"../outputs/');
  const html = '<!doctype html><html lang="ja"><meta charset="utf-8"><link rel="stylesheet" href="slides.css"><body>' + body + '</body></html>';
  writeFileSync(source, html, { flag: "wx" });
  const result = spawnSync(browser, [
    '--headless', '--disable-gpu', '--no-pdf-header-footer',
    `--user-data-dir=${profile}`, `--print-to-pdf=${output}`,
    source.href,
  ], { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0 || !existsSync(output)) throw new Error('PDF export failed');
  console.log(output);
} finally {
  await vite.close();
  rmSync(source, { force: true });
  rmSync(profile, { recursive: true, force: true, maxRetries: 3 });
}
