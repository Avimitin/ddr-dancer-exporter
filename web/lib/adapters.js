import { assert, Reader } from './binary.js';

export class AdapterRegistry {
  constructor() {
    this.adapters = [];
  }
  register(adapter) {
    assert(
      !this.adapters.some((a) => a.extensions.some((e) => adapter.extensions.includes(e))),
      'Duplicate adapter',
    );
    this.adapters.push(adapter);
    return this;
  }
  resolve(name) {
    const found = this.adapters.find((a) =>
      a.extensions.some((e) => name.toLowerCase().endsWith(e)),
    );
    assert(found, 'Unsupported model format: ' + name);
    return found;
  }
  models(files) {
    return [...files.keys()].filter((n) =>
      this.adapters.some((a) => a.extensions.some((e) => n.toLowerCase().endsWith(e))),
    );
  }
}

export function parsePmx(bytes) {
  const r = new Reader(bytes);
  assert(new TextDecoder().decode(bytes.subarray(0, 4)) === 'PMX ', 'Not a PMX file');
  const version = r.f32(4);
  assert(version >= 1.99 && version <= 2.11, 'Unsupported PMX version');
  r.pos = 8;
  const settings = Array.from({ length: r.take('u8', 1) }, () => r.take('u8', 1));
  assert(settings.length >= 8, 'Invalid PMX settings');
  const text = () => {
    const size = r.count();
    r.check(r.pos, size);
    const s = new TextDecoder(settings[0] === 0 ? 'utf-16le' : 'utf-8').decode(
      bytes.subarray(r.pos, r.pos + size),
    );
    r.pos += size;
    return s;
  };
  const idx = (kind) => {
    const size =
      settings[{ vertex: 2, texture: 3, material: 4, bone: 5, morph: 6, rigid: 7 }[kind]];
    assert([1, 2, 4].includes(size), 'Invalid index width');
    const p = r.pos;
    r.skip(size);
    return kind === 'vertex'
      ? size === 1
        ? r.u8(p)
        : size === 2
          ? r.u16(p)
          : r.u32(p)
      : size === 1
        ? r.view.getInt8(p)
        : size === 2
          ? r.view.getInt16(p, true)
          : r.i32(p);
  };
  const floats = (n) => {
    const v = r.floats(r.pos, n);
    r.pos += n * 4;
    return v;
  };
  const names = Array.from({ length: 4 }, text),
    vertices = [],
    weighted = new Map();
  for (let i = 0, n = r.count(); i < n; i++) {
    const position = floats(3),
      normal = floats(3),
      uv = floats(2);
    r.skip(settings[1] * 16);
    const type = r.take('u8', 1);
    let weights;
    if (type === 0) weights = [[idx('bone'), 1]];
    else if (type === 1 || type === 3) {
      const a = idx('bone'),
        b = idx('bone'),
        w = floats(1)[0];
      weights = [
        [a, w],
        [b, 1 - w],
      ];
      if (type === 3) r.skip(36);
    } else if (type === 2 || type === 4) {
      const ids = Array.from({ length: 4 }, () => idx('bone')),
        w = floats(4);
      weights = ids.map((b, j) => [b, w[j]]);
    } else throw new Error('Unsupported PMX skinning type ' + type);
    for (const [bone, w] of weights) if (w > 0) weighted.set(bone, (weighted.get(bone) || 0) + 1);
    vertices.push({ position, normal, uv, weights });
    r.skip(4);
  }
  const indices = Array.from({ length: r.count() }, () => idx('vertex'));
  assert(
    indices.length % 3 === 0 && indices.every((i) => i < vertices.length),
    'Invalid PMX triangles',
  );
  const textures = Array.from({ length: r.count() }, () => ({ path: text() })),
    materials = [];
  for (let i = 0, n = r.count(); i < n; i++) {
    const name = text();
    text();
    const diffuse = floats(4);
    r.skip(12 + 4 + 12 + 1 + 20);
    const texture = idx('texture');
    idx('texture');
    r.skip(1);
    const shared = r.take('u8', 1);
    if (shared) r.skip(1);
    else idx('texture');
    text();
    const count = r.count();
    assert(count % 3 === 0, 'Invalid material triangle count');
    materials.push({ name, diffuse, texture, triangles: count / 3 });
  }
  const bones = [];
  for (let i = 0, n = r.count(); i < n; i++) {
    const name = text(),
      english = text(),
      position = floats(3),
      parent = idx('bone');
    r.skip(4);
    const flags = r.take('u16', 2);
    if (flags & 1) idx('bone');
    else r.skip(12);
    if (flags & 0x300) {
      idx('bone');
      r.skip(4);
    }
    if (flags & 0x400) r.skip(12);
    if (flags & 0x800) r.skip(24);
    if (flags & 0x2000) r.skip(4);
    if (flags & 0x20) {
      idx('bone');
      r.skip(8);
      for (let j = 0, n = r.count(); j < n; j++) {
        idx('bone');
        if (r.take('u8', 1)) r.skip(24);
      }
    }
    bones.push({
      index: i,
      name,
      english,
      position,
      parent,
      weighted_vertices: weighted.get(i) || 0,
    });
  }
  // Morphs, display frames and physics are intentionally not transferred.
  assert(
    materials.reduce((n, m) => n + m.triangles, 0) * 3 === indices.length,
    'Material ranges do not cover geometry',
  );
  return {
    vertices,
    indices,
    source: {
      names,
      bones,
      textures,
      materials,
      triangles: indices.length / 3,
      input_format: 'pmx',
    },
  };
}

export function suggestMapping(bones) {
  const mapping = Object.create(null),
    direct = {
      下半身: 'Hips',
      腰: 'Hips',
      上半身: 'Spine',
      上半身2: 'Spine2',
      首: 'Neck',
      頭: 'Head',
      左目: 'Head',
      右目: 'Head',
    };
  for (const [side, prefix] of [
    ['左', 'Left'],
    ['右', 'Right'],
  ])
    for (const [part, target] of Object.entries({
      肩: 'Collar',
      腕: 'Arm',
      腕捩: 'ArmRoll',
      ひじ: 'ForeArm',
      手捩: 'ForeArmRoll',
      手首: 'Hand',
      足: 'UpLeg',
      ひざ: 'Leg',
      足首: 'Foot',
      つま先: 'ToeBase',
      足先EX: 'ToeBase',
    }))
      direct[side + part] = prefix + target;
  const resolve = (index, seen = new Set()) => {
    if (index < 0 || index >= bones.length || seen.has(index)) return null;
    const b = bones[index];
    if (mapping[b.name]) return mapping[b.name];
    seen.add(index);
    const target = direct[b.name] || resolve(b.parent, seen);
    if (target) mapping[b.name] = target;
    return target;
  };
  bones.forEach((b, i) => resolve(i));
  return mapping;
}

export const pmxAdapter = {
  id: 'pmx',
  extensions: ['.pmx'],
  available: () => true,
  async import({ files, name, mapping }) {
    const model = parsePmx(files.get(name));
    model.mapping = mapping || suggestMapping(model.source.bones);
    model.base = name.slice(0, name.lastIndexOf('/') + 1);
    return model;
  },
};
export const blenderAdapter = {
  id: 'blend',
  extensions: ['.blend'],
  available: (capabilities) => !!capabilities.blender,
  async import(context) {
    assert(context.bridge, 'Blender import requires the local Node.js bridge and Blender.');
    return context.bridge(context);
  },
};
export function registry() {
  return new AdapterRegistry().register(pmxAdapter).register(blenderAdapter);
}
