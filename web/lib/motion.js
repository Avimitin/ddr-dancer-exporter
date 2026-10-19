// SPDX-License-Identifier: GPL-3.0-or-later
// DDR curve subset from tools/anm.py; see tools/UPSTREAM.txt.
import { Matrix4, Quaternion, Vector3 } from 'three';
import { Reader, half, assert } from './binary.js';
export function parseMotion(bytes) {
  const r = new Reader(bytes);
  let core = -1;
  for (let p = 0; p + 28 < bytes.length; p += 4)
    if (r.u32(p) === 0xff010001) {
      const h = p + r.u32(p + 16),
        a = p + r.u32(p + 20);
      if (
        h + 16 < bytes.length &&
        a + 12 < bytes.length &&
        r.u32(h) === 0xff010003 &&
        r.u32(a) === 0xff010002
      ) {
        core = p;
        break;
      }
    }
  assert(core >= 0, 'Unsupported ANM file');
  const a = core + r.u32(core + 20),
    h = core + r.u32(core + 16),
    count = r.u32(h + 4),
    nodes = h + r.u32(h + 8),
    end = r.u32(a + 8);
  assert(count < 512 && end >= 12 && (end - 12) % 4 === 0, 'Invalid animation table');
  const parents = Array.from({ length: count }, (_, i) => r.view.getInt8(nodes + i * 2 + 1)),
    offsets = [];
  if (r.u16(a + end) === 28) offsets.push(end);
  for (let p = 12; p < end; p += 4) {
    const offset = r.u32(a + p);
    if (offset && !offsets.includes(offset)) offsets.push(offset);
  }
  const tracks = offsets.map((offset) => {
    const p = a + offset,
      type = r.u16(p),
      n = r.u16(p + 4),
      bone = r.u16(p + 6),
      key = r.u32(p + 8),
      value = p + r.u32(p + 12);
    assert([28, 29, 30, 31].includes(type) && bone < count && n > 0, 'Unsupported animation track');
    const keys = Array.from({ length: n }, (_, i) => (key ? r.u16(p + key + i * 2) : i)),
      values = Array.from({ length: n }, (_, i) => {
        if (type === 28) {
          const start = value + i * 6;
          let bits = 0n;
          for (let j = 0; j < 6; j++) bits |= BigInt(r.u8(start + j)) << BigInt(j * 8);
          const missing = Number(bits & 3n),
            stored = [32n, 17n, 2n].map(
              (s) => (Number((bits >> s) & 32767n) - 16383.5) / 23169.767578125,
            ),
            absent = Math.sqrt(Math.max(0, 1 - stored.reduce((n, v) => n + v * v, 0)));
          let j = 0;
          const q = Array.from({ length: 4 }, (_, k) => (k === missing ? absent : stored[j++]));
          return new Quaternion(...q).normalize().toArray();
        }
        if (type === 29) return r.floats(value + i * 12, 3);
        const base = type === 31 ? r.floats(value, 3) : [0, 0, 0];
        return base.map((b, j) => b + half(r.u16(value + (type === 31 ? 12 : 0) + i * 6 + j * 2)));
      });
    return { type, bone, keys, values };
  });
  return { last: r.u16(core + 4), parents, tracks };
}
export function pose(model, motion, frame) {
  const rest = model.bones.map((b) => new Matrix4().fromArray(b.matrix)),
    local = rest.map((m, i) =>
      model.bones[i].parent >= 0
        ? rest[model.bones[i].parent].clone().invert().multiply(m)
        : m.clone(),
    );
  if (motion) {
    assert(
      motion.parents.length === model.bones.length &&
        motion.parents.every((p, i) => p === model.bones[i].parent),
      'Animation skeleton does not match dancer',
    );
    for (const t of motion.tracks) {
      let i = 0;
      while (i < t.keys.length - 2 && t.keys[i + 1] < frame) i++;
      const a = t.values[i],
        b = t.values[Math.min(i + 1, t.values.length - 1)],
        f = Math.min(
          1,
          Math.max(0, (frame - t.keys[i]) / Math.max(1, (t.keys[i + 1] ?? t.keys[i]) - t.keys[i])),
        ),
        m = local[t.bone];
      if (t.type === 28) {
        const sign = a.reduce((n, v, j) => n + v * b[j], 0) < 0 ? -1 : 1,
          q = new Quaternion(...a.map((v, j) => v * (1 - f) + b[j] * sign * f)).normalize(),
          position = new Vector3().setFromMatrixPosition(m);
        m.makeRotationFromQuaternion(q).setPosition(position);
      } else m.setPosition(new Vector3(...a.map((v, j) => v * (1 - f) + b[j] * f)));
    }
  }
  const world = [];
  for (let i = 0; i < local.length; i++) {
    const p = model.bones[i].parent;
    assert(p < i, 'Unordered skeleton');
    world.push(p >= 0 ? world[p].clone().multiply(local[i]) : local[i]);
  }
  return world;
}
