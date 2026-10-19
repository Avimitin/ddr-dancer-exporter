import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { zipSync } from 'fflate';
import { buildWeb } from './build-web.js';
const root = fileURLToPath(new URL('../', import.meta.url));
await buildWeb();
const files = [
  'Start Exporter.cmd',
  'Launch.ps1',
  'README.md',
  'package.json',
  'package-lock.json',
  'web/index.html',
  'web/style.css',
  'web/app.bundle.js',
  'web/app.js',
  'web/preview.js',
  'web/lib/binary.js',
  'web/lib/adapters.js',
  'web/lib/ktmdl.js',
  'web/lib/exporter.js',
  'web/lib/motion.js',
  'web/lib/files.js',
  'web/lib/textures.js',
  'web/lib/arc.js',
  'web/lib/references.js',
  'service/blender_bridge.py',
  'scripts/import_blend.py',
  'scripts/build-web.js',
  'scripts/build-release.js',
  'docs/LOCAL-SERVICE.md',
  'docs/TECHNICAL.md',
  'docs/README.md',
  'docs/SETUP.md',
  'docs/CONVERTING.md',
  'docs/ARM-RETARGETING.txt',
  'docs/DEVELOPMENT.txt',
  'docs/STATIC-FRONTEND.md',
  'tests/js/conversion.test.js',
  'tests/test_bridge.py',
  'tests/test_frontend.py',
  'tests/test_launcher.ps1',
  'tools/LICENSE.upstream',
  'tools/LICENSE.bemaniutils',
  'tools/UPSTREAM.txt',
];
const entries = {};
for (const path of files)
  entries['ddr-dancer-exporter/' + path] = new Uint8Array(await readFile(root + path));
for (const name of ['three', 'fflate', 'esbuild'])
  entries['ddr-dancer-exporter/licenses/' + name + '.txt'] = new Uint8Array(
    await readFile(
      root + 'node_modules/' + name + (name === 'esbuild' ? '/LICENSE.md' : '/LICENSE'),
    ),
  );
await mkdir(root + 'dist', { recursive: true });
await writeFile(root + 'dist/ddr-dancer-exporter-windows.zip', zipSync(entries, { level: 6 }));
console.log(
  'Built dist/ddr-dancer-exporter-windows.zip (webpage + optional Blender bridge; no runtimes or model assets).',
);
