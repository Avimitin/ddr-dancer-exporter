import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
export async function buildWeb() {
  await build({
    absWorkingDir: fileURLToPath(new URL('../', import.meta.url)),
    entryPoints: ['web/app.js'],
    outfile: 'web/app.bundle.js',
    bundle: true,
    platform: 'browser',
    format: 'iife',
    target: ['chrome110', 'firefox115'],
    minify: true,
    legalComments: 'inline',
  });
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await buildWeb();
  console.log('Built static webpage. No runtime Node.js or Python required.');
}
