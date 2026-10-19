import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseKtmdl } from '../../web/lib/ktmdl.js';
import { exportModel } from '../../web/lib/exporter.js';
import { parsePmx, registry } from '../../web/lib/adapters.js';
import { parseMotion, pose } from '../../web/lib/motion.js';
import { unzip, packageZip } from '../../web/lib/files.js';
import { extractArc } from '../../web/lib/arc.js';
import { inspectReferences } from '../../web/lib/references.js';
import { zipSync } from 'fflate';
test('ZIP reader normalizes Windows separators', () => {
  const bytes = zipSync({ 'folder\\texture.png': new Uint8Array([1]) });
  assert.ok(unzip(bytes).has('folder/texture.png'));
});
const root = fileURLToPath(new URL('../../', import.meta.url)),
  read = async (p) => new Uint8Array(await readFile(root + p)),
  json = async (p) => JSON.parse(await readFile(root + p, 'utf8'));
test(
  'references use file contents and matching sidecars, not character names',
  { skip: !existsSync(root + 'dancers/template-miku/model/pl_miku00.model') },
  async () => {
    const assets = new Map();
    for (const name of await readdir(root + 'dancers/template-miku/model')) {
      assets.set(
        name.replace('pl_miku00', 'pl_reference'),
        await read('dancers/template-miku/model/' + name),
      );
    }
    let ref = inspectReferences(assets)[0];
    assert.equal(ref.name, 'pl_reference.model');
    assert.equal(ref.ready, true);
    const texture = ref.model.names[0],
      bytes = assets.get(texture);
    assets.delete(texture);
    ref = inspectReferences(assets)[0];
    assert.equal(ref.ready, false);
    assert.deepEqual(ref.missingTextures, [texture]);
    assets.set(texture, bytes);
    assets.delete('pl_reference.b2it');
    ref = inspectReferences(assets)[0];
    assert.equal(ref.ready, false);
    assert.deepEqual(ref.missingLookups, ['pl_reference.b2it']);
    assets.set('pl_other.model', await read('dancers/stock-emi/model/pl_emi00.model'));
    ref = inspectReferences(assets).find((r) => r.name === 'pl_other.model');
    assert.ok(ref.model, 'Stock model remains available to the preview');
    assert.equal(ref.compatible, false, 'Stock layout cannot bypass writer constraints');
  },
);
test('adapters resolve formats and reject unknown inputs', () => {
  assert.equal(registry().resolve('A.PMX').id, 'pmx');
  assert.equal(registry().resolve('A.blend').id, 'blend');
  assert.throws(() => registry().resolve('a.fbx'), /Unsupported/);
  assert.equal(registry().resolve('a.blend').available({}), false);
});
test('malformed geometry and ZIP paths fail explicitly', () => {
  assert.throws(() => parsePmx(new Uint8Array(20)), /PMX/);
  assert.throws(() => packageZip(new Map([['../escape.txt', 'bad']])), /Unsafe/);
  const bytes = packageZip(new Map([['Dancer/借物表.txt', 'Creator / AIGC']]));
  assert.equal(new TextDecoder().decode(unzip(bytes).get('Dancer/借物表.txt')), 'Creator / AIGC');
});
test('ZIP reader rejects traversal supplied by another writer', () => {
  const bytes = zipSync({ '../escape': new Uint8Array([1]) });
  assert.throws(() => unzip(bytes), /Unsafe/);
});
test(
  'local ARC decoder matches extracted animation bytes',
  { skip: !existsSync(root + 'animations/archives/mc_female.arc') },
  async () => {
    const files = extractArc(await read('animations/archives/mc_female.arc'));
    let checked = 0;
    for (const [name, bytes] of files) {
      if (existsSync(root + 'animations/motions/' + name)) {
        assert.deepEqual(bytes, await read('animations/motions/' + name));
        checked++;
      }
      if (name.endsWith('.anm')) assert.ok(parseMotion(bytes).tracks.length > 0);
    }
    assert.ok(checked >= 10);
  },
);
test(
  'local stock body and face vertex layouts',
  { skip: !existsSync(root + 'dancers/stock-emi/model/pl_emi00.model') },
  async () => {
    const body = parseKtmdl(await read('dancers/stock-emi/model/pl_emi00.model')),
      face = parseKtmdl(await read('dancers/stock-emi/face/pl_emi00_face01.model'));
    assert.equal(body.packets[0].vd.stride, 44);
    assert.equal(face.packets[0].vd.stride, 28);
    assert.ok(face.packets[0].vertices.every((v) => v.position.every(Number.isFinite)));
  },
);
for (const name of ['adelie-tomorin', 'ano', 'nailong'])
  test(
    'local regression: ' + name,
    { skip: !existsSync(root + 'dancers/' + name + '/analysis/pmx-geometry.json') },
    async () => {
      const base = 'dancers/' + name + '/',
        source = await json(base + 'analysis/pmx-inspection.json'),
        geometry = await json(base + 'analysis/pmx-geometry.json'),
        mapping = await json(base + 'bone-map.json'),
        config = await json(base + 'dancer.json');
      const model = { ...geometry, source, mapping };
      if (source.input_format !== 'blend') {
        const parsed = parsePmx(new Uint8Array(await readFile(source.file)));
        assert.equal(parsed.vertices.length, geometry.vertices.length);
        assert.deepEqual(parsed.indices, geometry.indices);
        assert.deepEqual(parsed.vertices[0], geometry.vertices[0]);
      }
      const result = exportModel(
        model,
        await read('dancers/template-miku/model/pl_miku00.model'),
        await read('dancers/template-miku/model/pl_miku00.b2it'),
      );
      const old = parseKtmdl(
        await read(
          base +
            'output/' +
            config.package_name +
            '/pl_' +
            config.model_id +
            '/pl_' +
            config.model_id +
            '.model',
        ),
      );
      let max = 0;
      for (let p = 0; p < old.packets.length; p++) {
        const a = old.packets[p],
          b = result.decoded.packets[p];
        assert.deepEqual(a.indices, b.indices);
        assert.equal(a.vertices.length, b.vertices.length);
        for (let i = 0; i < a.vertices.length; i++) {
          for (let k = 0; k < 4; k++)
            if (a.vertices[i].weights[k] > 1e-6 || b.vertices[i].weights[k] > 1e-6)
              assert.equal(a.vertices[i].ids[k], b.vertices[i].ids[k]);
          for (let k = 0; k < 3; k++)
            max = Math.max(max, Math.abs(a.vertices[i].position[k] - b.vertices[i].position[k]));
          for (let k = 0; k < 4; k++)
            assert.ok(Math.abs(a.vertices[i].weights[k] - b.vertices[i].weights[k]) < 1e-6);
        }
      }
      assert.ok(max < 2e-6, `Geometry changed by ${max}`);
      const animation = await read('animations/motions/mc_female_ht01_exec.anm'),
        motion = parseMotion(animation);
      for (const frame of [0, 150, motion.last])
        assert.ok(
          pose(result.decoded, motion, frame).every((m) => m.elements.every(Number.isFinite)),
        );
      await mkdir(root + 'analysis/js-validation', { recursive: true });
      await writeFile(root + 'analysis/js-validation/' + name + '.model', result.data);
    },
  );
