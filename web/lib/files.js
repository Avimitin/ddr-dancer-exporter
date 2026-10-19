import { unzipSync, zipSync, strToU8 } from 'fflate';
import { assert } from './binary.js';
export const MAX_BYTES = 512 * 1024 * 1024;
export function safePath(path) {
  path = path.replaceAll('\\', '/');
  assert(
    path &&
      !path.startsWith('/') &&
      !path
        .split('/')
        .some((p) => p === '..' || p === '.' || p.includes(':') || /[\x00-\x1f]/.test(p)),
    'Unsafe file path: ' + path,
  );
  return path;
}
export function unzip(bytes) {
  let total = 0,
    count = 0;
  const seen = new Set();
  return new Map(
    Object.entries(
      unzipSync(bytes, {
        filter: (file) => {
          const path = safePath(file.name),
            key = path.toLowerCase();
          assert(!seen.has(key), 'Duplicate archive path: ' + path);
          seen.add(key);
          total += file.originalSize;
          assert(
            ++count <= 10000 && Number.isFinite(total) && total <= 1024 * 1024 * 1024,
            'ZIP exceeds 10,000 files or 1 GiB unpacked',
          );
          return !path.endsWith('/');
        },
      }),
    ).map(([name, data]) => [safePath(name), data]),
  );
}
export async function readFiles(list) {
  const files = new Map();
  let total = 0;
  for (const file of list) {
    total += file.size;
    assert(total <= MAX_BYTES, 'Select at most 512 MiB at a time');
    const name = safePath(file.webkitRelativePath || file.name),
      bytes = new Uint8Array(await file.arrayBuffer());
    if (name.toLowerCase().endsWith('.zip'))
      for (const [n, b] of unzip(bytes)) {
        assert(!files.has(n), 'Duplicate input path: ' + n);
        files.set(n, b);
      }
    else {
      assert(!files.has(name), 'Duplicate input path');
      files.set(name, bytes);
    }
  }
  return files;
}
export function resolveFile(files, path) {
  path = path.replaceAll('\\', '/');
  const parts = [];
  for (const p of path.split('/')) {
    if (p === '..') {
      assert(parts.length, 'Texture path escapes source folder');
      parts.pop();
    } else if (p && p !== '.') parts.push(p);
  }
  const key = parts.join('/').toLowerCase(),
    found = [...files.keys()].find((n) => n.toLowerCase() === key);
  assert(found, 'Missing file: ' + path);
  return files.get(found);
}
export function packageZip(files) {
  return zipSync(
    Object.fromEntries(
      [...files].map(([name, bytes]) => [
        safePath(name),
        typeof bytes === 'string' ? strToU8(bytes) : bytes,
      ]),
    ),
    { level: 6 },
  );
}
