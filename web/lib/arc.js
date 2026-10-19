// SPDX-License-Identifier: GPL-3.0-or-later
// ARC layout from scripts/extract_arc.py; LZ back references follow tools/lz77.py
// (bemaniutils, Unlicense; notice retained in tools/LICENSE.bemaniutils).
import { Reader, assert } from './binary.js';
export function decompress(bytes, size) {
  assert(size <= 128 * 1024 * 1024, 'ARC entry too large');
  const out = new Uint8Array(size),
    ring = new Uint8Array(4096);
  let p = 0,
    n = 0,
    write = 0,
    flags = 1;
  const put = (value) => {
    assert(n < size, 'ARC decompression overflow');
    out[n++] = value;
    ring[write] = value;
    write = (write + 1) % 4096;
  };
  while (p < bytes.length) {
    if (flags === 1) flags = 256 | bytes[p++];
    const bit = flags & 1;
    flags >>= 1;
    if (bit) {
      assert(p < bytes.length, 'Truncated ARC literal');
      put(bytes[p++]);
    } else {
      assert(p + 2 <= bytes.length, 'Truncated ARC reference');
      const hi = bytes[p++],
        lo = bytes[p++],
        distance = (hi << 4) | (lo >> 4);
      if (!distance) break;
      for (let i = 0; i < (lo & 15) + 3; i++) put(ring[(write - distance + 4096) % 4096]);
    }
  }
  assert(n === size, 'ARC decompressed size mismatch');
  return out;
}
export function extractArc(bytes) {
  const r = new Reader(bytes);
  assert(r.u32(0) === 0x19751120 && r.u32(4) === 1, 'Unsupported DDR archive');
  const count = r.u32(8);
  assert(count < 10000, 'Too many ARC entries');
  const files = new Map();
  let total = 0;
  for (let i = 0; i < count; i++) {
    const p = 16 + i * 16,
      name = r.string(r.u32(p)).replaceAll('\\', '/').split('/').pop(),
      offset = r.u32(p + 4),
      size = r.u32(p + 8),
      stored = r.u32(p + 12);
    assert(
      !name.includes('/') && !name.includes('\\') && name !== '.' && name !== '..',
      'Unsafe ARC name',
    );
    total += size;
    assert(total <= 512 * 1024 * 1024, 'ARC exceeds unpacked size limit');
    r.check(offset, stored);
    const data = bytes.slice(offset, offset + stored);
    files.set(name, stored < size ? decompress(data, size) : data);
    assert(files.get(name).length === size, 'Invalid ARC entry size');
  }
  return files;
}
