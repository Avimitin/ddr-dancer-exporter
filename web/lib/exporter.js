// SPDX-License-Identifier: GPL-3.0-or-later
import { Vector3, Quaternion, Matrix4 } from 'three';
import { assert, table, toHalf } from './binary.js';
import { parseKtmdl } from './ktmdl.js';
const v = (a) => new Vector3(...a),
  clamp = (x) => Math.min(1, Math.max(0, x));
function bounds(points) {
  const lo = [Infinity, Infinity, Infinity],
    hi = [-Infinity, -Infinity, -Infinity];
  for (const p of points)
    for (let i = 0; i < 3; i++) {
      lo[i] = Math.min(lo[i], p[i]);
      hi[i] = Math.max(hi[i], p[i]);
    }
  return { lo, hi };
}
function influences(pairs) {
  const merged = new Map();
  for (const [id, w] of pairs) {
    assert(Number.isInteger(id) && Number.isFinite(w) && w >= 0, 'Invalid skin influence');
    if (w > 0) merged.set(id, (merged.get(id) || 0) + w);
  }
  let sorted = [...merged].sort((a, b) => b[1] - a[1]).slice(0, 4);
  const total = sorted.reduce((n, p) => n + p[1], 0);
  assert(total > 0, 'Vertex has no mapped skin weights');
  sorted = sorted.map(([i, w]) => [i, w / total]);
  while (sorted.length < 4) sorted.push([sorted[0][0], 0]);
  return sorted;
}

export function fitGeometry(model, ref, boneTable, { armRetarget = true, twistMode } = {}) {
  const source = model.source,
    names = Object.fromEntries(boneTable.map((b) => [b.name, b.index])),
    mapping = model.mapping;
  const sourceIds = source.bones.map((b) => names[mapping[b.name]]);
  const all = model.vertices.map((x) => x.position),
    box = bounds(all),
    target = bounds(ref.packets.flatMap((p) => p.vertices.map((v) => v.position)));
  const scale = (target.hi[1] - target.lo[1]) / (box.hi[1] - box.lo[1]);
  assert(Number.isFinite(scale) && scale > 0, 'Model has no vertical extent');
  const origin = source.origin || [0, box.lo[1], source.bones[6]?.position[2] || 0];
  const fit = (p) => [
    (p[0] - origin[0]) * scale,
    (p[1] - origin[1]) * scale,
    -(p[2] - origin[2]) * scale,
  ];
  const vertices = model.vertices.map((x) => ({
    position: fit(x.position),
    normal: v([x.normal[0], x.normal[1], -x.normal[2]]).normalize().toArray(),
    uv: x.uv,
    pairs: influences(
      x.weights
        .filter(([, w]) => w > 0)
        .map(([i, w]) => {
          assert(
            sourceIds[i] !== undefined,
            'Unmapped weighted bone: ' + (source.bones[i]?.name || i),
          );
          return [sourceIds[i], w];
        }),
    ),
  }));
  if (!armRetarget) return { vertices, scale, origin };
  const anchors = {},
    tails = {},
    transforms = new Map(),
    joints = [];
  if (source.arm_bind)
    for (const [key, b] of Object.entries(source.arm_bind)) {
      anchors[key] = v(fit(b.head));
      tails[key] = v(fit(b.tail));
    }
  else
    for (const b of source.bones) {
      const name = mapping[b.name];
      if (/^(Left|Right)(Collar|Arm|ForeArm|Hand)$/.test(name)) anchors[name] = v(fit(b.position));
    }
  const rest = (name) => v(ref.bones[names[name]].matrix.slice(12, 15));
  for (const side of ['Left', 'Right'])
    for (const [part, next] of [
      ['Collar', 'Arm'],
      ['Arm', 'ForeArm'],
      ['ForeArm', 'Hand'],
      ['Hand', null],
    ]) {
      const key = side + part,
        head = anchors[key];
      assert(head, 'Missing source rest joint ' + key + '. Supply a bone map with arm anchors.');
      const dest = rest(key),
        end = next
          ? anchors[side + next]
          : tails[key] ||
            head
              .clone()
              .multiplyScalar(2)
              .sub(anchors[side + 'ForeArm']);
      assert(end, 'Missing source rest joint ' + side + next);
      const axis = end.clone().sub(head),
        targetAxis = next ? rest(side + next).sub(dest) : dest.clone().sub(rest(side + 'ForeArm'));
      assert(axis.length() > 1e-9 && targetAxis.length() > 1e-9, 'Zero-length arm bone ' + key);
      const lengthScale = next ? targetAxis.length() / axis.length() : 1,
        unit = axis.clone().normalize(),
        rotation = new Quaternion().setFromUnitVectors(unit, targetAxis.clone().normalize());
      const transform = { head, dest, unit, lengthScale, rotation };
      transforms.set(names[key], transform);
      if (part === 'Arm' || part === 'ForeArm') transforms.set(names[key + 'Roll'], transform);
      joints.push({ bone: key, lengthScale });
    }
  const rollIds = ['LeftArmRoll', 'RightArmRoll', 'LeftForeArmRoll', 'RightForeArmRoll'].map(
    (n) => names[n],
  );
  twistMode ||= vertices.some((x) => x.pairs.some(([i, w]) => w > 0 && rollIds.includes(i)))
    ? 'source'
    : 'spatial';
  assert(['source', 'spatial'].includes(twistMode), 'Invalid twist mode');
  for (const x of vertices) {
    const old = v(x.position),
      normal = v(x.normal),
      pos = new Vector3(),
      norm = new Vector3();
    for (const [id, w] of x.pairs) {
      if (!w) continue;
      const t = transforms.get(id);
      let p = old.clone(),
        n = normal.clone();
      if (t) {
        p.sub(t.head)
          .addScaledVector(t.unit, p.dot(t.unit) * (t.lengthScale - 1))
          .applyQuaternion(t.rotation)
          .add(t.dest);
        n.addScaledVector(t.unit, n.dot(t.unit) * (1 / t.lengthScale - 1)).applyQuaternion(
          t.rotation,
        );
      }
      pos.addScaledVector(p, w);
      norm.addScaledVector(n, w);
    }
    x.position = pos.toArray();
    x.normal = norm.normalize().toArray();
    if (twistMode === 'spatial') {
      const pairs = [];
      for (const [id, w] of x.pairs) {
        let split = false;
        for (const side of ['Left', 'Right'])
          for (const [part, next] of [
            ['Arm', 'ForeArm'],
            ['ForeArm', 'Hand'],
          ])
            if (id === names[side + part]) {
              const a = anchors[side + part],
                axis = anchors[side + next].clone().sub(a);
              let f = clamp(old.clone().sub(a).dot(axis) / axis.lengthSq());
              f = f * f * (3 - 2 * f);
              pairs.push([id, w * (1 - f)], [names[side + part + 'Roll'], w * f]);
              split = true;
            }
        if (!split) pairs.push([id, w]);
      }
      x.pairs = influences(pairs);
    }
  }
  return { vertices, scale, origin, armRetarget: { twistMode, joints } };
}

export function exportModel(model, template, lookup, options = {}) {
  const ref = parseKtmdl(template),
    h = ref.header,
    palette = ref.packets[0].palette;
  assert(
    h.boneCount === 33 && h.packetCount === 9 && ref.names.length === 5,
    'This DDR model cannot be used for conversion. Choose a compatible DDR dancer package.',
  );
  assert(
    ref.packets.every(
      (p) => p.vd.stride === 48 && JSON.stringify(p.palette) === JSON.stringify(palette),
    ),
    'Template vertex layouts or palettes differ',
  );
  const fitted = fitGeometry(model, ref, table(lookup), options),
    vertices = fitted.vertices;
  assert(
    vertices.every((x) => [...x.position, ...x.normal, ...x.uv].every(Number.isFinite)),
    'Non-finite geometry',
  );
  const chunks = [];
  let start = 0;
  for (const material of model.source.materials) {
    const count = material.triangles * 3,
      indices = model.indices.slice(start, start + count);
    start += count;
    assert(indices.length === count, 'Truncated material geometry');
    for (let i = 0; i < indices.length; i += 3)
      [indices[i + 1], indices[i + 2]] = [indices[i + 2], indices[i + 1]];
    if (count) chunks.push({ material, indices });
  }
  assert(
    start === model.indices.length && chunks.length > 0 && chunks.length <= 9,
    'The DDR template supports 1–9 populated materials',
  );
  while (chunks.length < 9) {
    let i = 0;
    for (let j = 1; j < chunks.length; j++)
      if (chunks[j].indices.length > chunks[i].indices.length) i = j;
    const c = chunks[i],
      mid = Math.floor(c.indices.length / 6) * 3;
    assert(mid > 0, 'At least nine triangles are required');
    chunks.splice(
      i,
      1,
      { material: c.material, indices: c.indices.slice(0, mid) },
      { material: c.material, indices: c.indices.slice(mid) },
    );
  }
  const head = template.slice(0, h.streamDataOffset),
    view = new DataView(head.buffer),
    pieces = [head];
  let length = head.length;
  const append = (bytes) => {
    const pad = (16 - (length % 16)) % 16;
    if (pad) {
      pieces.push(new Uint8Array(pad));
      length += pad;
    }
    const offset = length;
    pieces.push(bytes);
    length += bytes.length;
    return offset;
  };
  const floats = (offset, values) =>
    values.forEach((x, i) => view.setFloat32(offset + i * 4, x, true));
  chunks.forEach((chunk, index) => {
    const packet = ref.packets[index],
      unique = [...new Set(chunk.indices)].sort((a, b) => a - b),
      local = new Map(unique.map((id, i) => [id, i]));
    assert(unique.length < 65536, 'A material exceeds 65,535 vertices');
    const bytes = new Uint8Array(unique.length * 48),
      vd = new DataView(bytes.buffer);
    unique.forEach((id, i) => {
      assert(id >= 0 && id < vertices.length, 'Triangle vertex out of range');
      const x = vertices[id],
        at = i * 48;
      x.position.forEach((n, j) => vd.setFloat32(at + j * 4, n, true));
      x.pairs.forEach(([b, w], j) => {
        const slot = palette.indexOf(b);
        assert(slot >= 0, 'Weighted bone is outside DDR palette');
        vd.setUint8(at + 12 + j, slot);
        if (j) vd.setFloat32(at + 16 + (j - 1) * 4, w, true);
      });
      x.normal.forEach((n, j) => vd.setFloat32(at + 28 + j * 4, n, true));
      x.uv.forEach((n, j) => vd.setUint16(at + 40 + j * 2, toHalf(n), true));
      chunk.material.diffuse.forEach((n, j) =>
        vd.setUint8(at + 44 + j, Math.round(clamp(n) * 255)),
      );
    });
    const ib = new Uint8Array(chunk.indices.length * 2),
      iv = new DataView(ib.buffer);
    chunk.indices.forEach((id, i) => iv.setUint16(i * 2, local.get(id), true));
    const vo = append(bytes),
      io = append(ib);
    view.setInt32(packet.vd.offset, vo - packet.vd.offset, true);
    view.setUint32(packet.vd.offset + 4, unique.length, true);
    view.setInt32(packet.ind.offset, io - packet.ind.offset, true);
    view.setUint32(packet.ind.offset + 4, chunk.indices.length, true);
    const tex = chunk.material.texture;
    assert(
      Number.isInteger(tex) && tex >= 0 && tex < 5,
      'Only five diffuse texture slots are supported',
    );
    view.setUint32(packet.offset + 4, tex, true);
    view.setUint16(packet.offset + 0x30, tex, true);
    const b = bounds(unique.map((i) => vertices[i].position)),
      center = b.lo.map((n, j) => (n + b.hi[j]) / 2);
    let radius = 0;
    for (const id of unique)
      radius = Math.max(radius, v(vertices[id].position).distanceTo(v(center)));
    floats(packet.offset + 0x50, [...center, radius]);
  });
  const global = bounds(vertices.map((x) => x.position));
  for (const [offset, count] of [
    [h.groupOffset, h.groupCount],
    [h.boundingOffset, h.boundingCount],
  ])
    for (let i = 0; i < count; i++) {
      floats(offset + i * 48 + 16, global.hi);
      floats(offset + i * 48 + 32, global.lo);
    }
  for (const bone of ref.bones) {
    const inverse = new Matrix4().fromArray(bone.inverse),
      points = vertices
        .filter((x) => x.pairs.some(([i, w]) => i === bone.index && w > 0))
        .map((x) => v(x.position).applyMatrix4(inverse).toArray()),
      b = points.length ? bounds(points) : { lo: [0, 0, 0], hi: [0, 0, 0] };
    floats(bone.offset + 0x90, b.hi);
    floats(bone.offset + 0xa0, b.lo);
  }
  append(new Uint8Array());
  view.setUint32(0x74, length - h.streamDataOffset, true);
  view.setUint32(0x90, length, true);
  const data = new Uint8Array(length);
  let at = 0;
  for (const piece of pieces) {
    data.set(piece, at);
    at += piece.length;
  }
  const decoded = parseKtmdl(data);
  assert(
    decoded.packets.reduce((n, p) => n + p.indices.length, 0) === model.indices.length,
    'Export triangle validation failed',
  );
  for (const p of decoded.packets) {
    assert(
      p.indices.every((i) => i < p.vertices.length),
      'Export index validation failed',
    );
    assert(
      p.vertices.every(
        (x) =>
          x.ids.every(Number.isInteger) &&
          x.position.every(Number.isFinite) &&
          x.weights.every((w) => w >= -1e-6 && w <= 1.000001),
      ),
      'Export skin validation failed',
    );
  }
  return {
    data,
    decoded,
    report: {
      scale: fitted.scale,
      origin: fitted.origin,
      armRetarget: fitted.armRetarget,
      triangles: model.indices.length / 3,
      runtimeStatus: 'Not tested in DDR',
    },
  };
}
