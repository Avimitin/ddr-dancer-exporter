// SPDX-License-Identifier: GPL-3.0-or-later
// Narrow DDR reader, ported from the vendored ktmdl.py; see tools/UPSTREAM.txt.
import { Reader, assert, half } from './binary.js';
export function parseKtmdl(bytes) {
  const r = new Reader(bytes);
  assert(r.string(0) === 'KTMDL', 'Not a KTMDL model');
  const h = {};
  for (const [name, offset] of Object.entries({
    boneCount: 0x18,
    boneOffset: 0x1c,
    packetCount: 0x28,
    packetOffset: 0x2c,
    groupCount: 0x40,
    groupOffset: 0x44,
    textureTypeCount: 0x50,
    textureTypeOffset: 0x54,
    boundingCount: 0x58,
    boundingOffset: 0x5c,
    debugInfoOffset: 0x60,
    streamDataOffset: 0x78,
    textureCount: 0x7c,
  }))
    h[name] = r.u32(offset);
  assert(
    h.boneCount < 512 && h.packetCount < 512 && r.u32(0x90) === bytes.length,
    'Unsupported KTMDL header',
  );
  const bones = Array.from({ length: h.boneCount }, (_, i) => {
    const offset = h.boneOffset + i * 0xb0;
    return {
      index: i,
      offset,
      matrix: r.floats(offset + 16, 16),
      inverse: r.floats(offset + 80, 16),
      parent: r.i32(offset + 0xac),
    };
  });
  const names = [],
    nt = h.debugInfoOffset + r.i32(h.debugInfoOffset + 4);
  for (let i = 0; i < h.textureCount; i++) names.push(r.string(nt + r.u32(nt + i * 4)));
  const descriptor = (p) => ({
    offset: p,
    data: p + r.i32(p),
    count: r.u32(p + 4),
    stride: r.u8(p + 9),
  });
  const packets = Array.from({ length: h.packetCount }, (_, i) => {
    const offset = h.packetOffset + i * 0x60;
    assert(r.u8(offset + 2) === 1, 'Only triangle-list KTMDL is supported');
    const palette = Array.from({ length: r.u32(offset + 0x18) }, (_, j) =>
      r.u16(offset + r.i32(offset + 0x1c) + j * 2),
    );
    const vd = descriptor(offset + r.i32(offset + 0x14)),
      ind = descriptor(offset + r.i32(offset + 0x24));
    assert([28, 44, 48].includes(vd.stride), 'Unsupported KTMDL vertex layout');
    r.check(vd.data, vd.count * vd.stride);
    r.check(ind.data, ind.count * 2);
    const vertices = Array.from({ length: vd.count }, (_, j) => {
      const p = vd.data + j * vd.stride,
        rigid = vd.stride === 28,
        explicit = rigid ? [0, 0, 0] : r.floats(p + 16, 3),
        uv = p + (rigid ? 24 : 40);
      return {
        position: r.floats(p, 3),
        normal: r.floats(p + (rigid ? 12 : 28), 3),
        uv: [half(r.u16(uv)), half(r.u16(uv + 2))],
        weights: [1 - explicit.reduce((a, b) => a + b, 0), ...explicit],
        ids: Array.from({ length: 4 }, (_, k) => (rigid ? palette[0] : palette[r.u8(p + 12 + k)])),
        color:
          vd.stride === 48
            ? Array.from({ length: 4 }, (_, k) => r.u8(p + 44 + k) / 255)
            : [1, 1, 1, 1],
      };
    });
    const indices = Array.from({ length: ind.count }, (_, j) => r.u16(ind.data + j * 2));
    const binding = r.u16(offset + 0x30),
      texture = r.u16(h.textureTypeOffset + binding * 0x50 + 0x0e);
    return { offset, vd, ind, palette, vertices, indices, texture };
  });
  return { header: h, bones, names, packets };
}
