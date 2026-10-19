import { registry } from './lib/adapters.js';
import { assert } from './lib/binary.js';
import { exportModel } from './lib/exporter.js';
import { readFiles, resolveFile, packageZip, unzip } from './lib/files.js';
import { decodeImage, encodeDDS } from './lib/textures.js';
import { parseKtmdl } from './lib/ktmdl.js';
import { parseMotion } from './lib/motion.js';
import { extractArc } from './lib/arc.js';
import { Comparison } from './preview.js';
import { Matrix4, Vector3 } from 'three';
const $ = (id) => document.getElementById(id),
  adapters = registry(),
  assets = new Map(),
  dancers = [];
let files = new Map(),
  mapping = null,
  capabilities = {},
  session = new URLSearchParams(location.hash.slice(1)).get('session'),
  job = null,
  comparison = null,
  busy = false;
const bridgeURL = 'http://127.0.0.1:8765';
const status = (text, error = false) => {
  $('status').textContent = text;
  $('status').dataset.error = String(error);
};
const yieldUI = () => new Promise((resolve) => setTimeout(resolve, 0));
try {
  if (session) {
    sessionStorage.setItem('ddr-session', session);
    history.replaceState(null, '', location.pathname);
  } else session = sessionStorage.getItem('ddr-session');
} catch {}
async function api(path, options = {}) {
  assert(session, 'Open Start Exporter.cmd to connect to Blender');
  const response = await fetch(bridgeURL + '/api/' + path, {
    ...options,
    headers: { Authorization: 'Bearer ' + session, ...options.headers },
  });
  if (!response.ok) {
    let message = 'Local service unavailable';
    try {
      message = (await response.json()).error || message;
    } catch {}
    throw new Error(message);
  }
  return response;
}
async function checkBlender() {
  const wasAvailable = !!capabilities.blender;
  try {
    capabilities = await (await api('capabilities', { signal: AbortSignal.timeout(1500) })).json();
    $('connection').textContent = 'PMX · browser / Blender · connected';
    $('stop').hidden = false;
  } catch {
    capabilities = {};
    $('connection').textContent = 'PMX · browser / Blender · not connected';
    $('stop').hidden = true;
  }
  if (wasAvailable !== !!capabilities.blender) {
    checkModel();
    if (capabilities.blender && /\.blend$/i.test($('model-choice').value))
      status('Blender connected. Your model is ready to convert.');
  }
}
function checkModel() {
  const name = $('model-choice').value || '',
    isBlend = /\.blend$/i.test(name);
  $('blender-help').hidden = !(isBlend && !capabilities.blender);
  $('convert').disabled = busy || (isBlend && !capabilities.blender);
  if (isBlend && !capabilities.blender)
    status(
      'Cannot import .blend: Blender is not connected. Install Blender and reopen Start Exporter.cmd.',
      true,
    );
}
const asset = (name) => {
  const entry = [...assets].find(([n]) => n.toLowerCase() === name.toLowerCase());
  assert(entry, 'Missing DDR reference file: ' + name);
  return entry[1];
};
function refreshAssets() {
  const ready = ['pl_miku00.model', 'pl_miku00.b2it', 'pl_miku00.grp2it'].every((n) =>
    assets.has(n),
  );
  $('asset-status').textContent =
    (ready ? 'DDR template loaded.' : 'DDR template still needed.') +
    ' ' +
    [...assets.keys()].filter((n) => /\.anm$/i.test(n)).length +
    ' animations available.';
  const current = $('animation').value;
  $('animation').replaceChildren(new Option('Rest pose', ''));
  for (const n of [...assets.keys()].filter((n) => /\.anm$/i.test(n)).sort())
    $('animation').add(
      new Option(
        n
          .replace(/^mc_/, '')
          .replace(/_exec\.anm$/, '')
          .replaceAll('_', ' / ')
          .toUpperCase(),
        n,
      ),
    );
  $('animation').value = current;
}
async function loadAssets(list) {
  try {
    status('Loading DDR reference files…');
    const selected = [...list].filter((f) =>
      /^(pl_miku00\.(model|b2it|grp2it)|mk_.*\.dds|pl_emi00.*\.(arc|model|b2it|grp2it)|mdx_emi.*\.dds|mc_.*\.(arc|anm)|.*\.zip)$/i.test(
        f.name,
      ),
    );
    assert(selected.length, 'No supported DDR reference files found');
    const input = await readFiles(selected);
    for (const [path, bytes] of input) {
      if (/\.arc$/i.test(path)) {
        for (const [n, b] of extractArc(bytes)) assets.set(n, b);
      } else assets.set(path.split('/').pop(), bytes);
    }
    refreshAssets();
    await remember();
    status('Reference files ready.');
    if (dancers.length) showPreview();
  } catch (e) {
    status(e.message, true);
  }
}
async function chooseModels(list) {
  try {
    files = await readFiles(list);
    const names = adapters.models(files);
    assert(
      names.length,
      'Choose a PMX or .blend model with its textures, or a ZIP containing one.',
    );
    $('model-choice').replaceChildren(...names.map((n) => new Option(n, n)));
    if (!$('label').value)
      $('label').value = names[0]
        .split('/')
        .pop()
        .replace(/\.[^.]+$/, '');
    const embedded = [...files].find(([n]) => n.split('/').pop() === 'bone-map.json');
    mapping = embedded ? JSON.parse(new TextDecoder().decode(embedded[1])) : null;
    status('Model loaded. Add credits, then convert.');
    checkModel();
    await remember();
  } catch (e) {
    status(e.message, true);
  }
}
async function bridgeImport(context) {
  const response = await api('jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credits: $('credits').value, model: context.name }),
  });
  job = (await response.json()).id;
  $('cancel').hidden = false;
  try {
    await api('jobs/' + job, { method: 'PUT', body: packageZip(context.files) });
    while (true) {
      await new Promise((r) => setTimeout(r, 750));
      const state = await (await api('jobs/' + job)).json();
      status('Blender: ' + state.status);
      $('log-box').hidden = false;
      $('log').textContent = state.log || '';
      if (['failed', 'cancelled'].includes(state.status))
        throw new Error(state.error || 'Import cancelled');
      if (state.status === 'complete') break;
    }
    const result = unzip(
      new Uint8Array(await (await api('jobs/' + job + '/result')).arrayBuffer()),
    );
    const model = JSON.parse(new TextDecoder().decode(result.get('model.json')));
    model.files = result;
    return model;
  } finally {
    job = null;
    $('cancel').hidden = true;
  }
}
async function convert() {
  if (busy) return;
  busy = true;
  $('convert').disabled = true;
  try {
    const name = $('model-choice').value,
      credits = $('credits').value.trim(),
      label = $('label').value.trim();
    assert(files.has(name), 'Choose a model first');
    assert(credits, 'Please fill in the required 借物表 / credits');
    assert(label, 'Enter a dancer name');
    const adapter = adapters.resolve(name);
    if (!adapter.available(capabilities)) {
      checkModel();
      throw new Error('Blender is not connected. Follow the installation instructions above.');
    }
    const template = asset('pl_miku00.model'),
      lookup = asset('pl_miku00.b2it'),
      groups = asset('pl_miku00.grp2it');
    status('Importing ' + adapter.id + '…');
    await yieldUI();
    await remember();
    const model = await adapter.import({ files, name, mapping, bridge: bridgeImport });
    status('Converting geometry and fitting arm joints…');
    await yieldUI();
    const result = exportModel(model, template, lookup);
    const textureFiles = new Map(),
      input = model.files || files;
    status('Converting textures…');
    await yieldUI();
    for (let i = 0; i < result.decoded.names.length; i++) {
      let image;
      if (i < model.source.textures.length) {
        const texture = model.source.textures[i].path;
        image = await decodeImage(resolveFile(input, model.base + texture), texture);
      } else {
        image = document.createElement('canvas');
        image.width = image.height = 4;
        const ctx = image.getContext('2d');
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, 4, 4);
      }
      textureFiles.set(result.decoded.names[i], encodeDDS(image));
    }
    const id = 'web' + crypto.getRandomValues(new Uint32Array(2)).join('').slice(0, 12),
      folder = label.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/, '') || 'Dancer',
      prefix = folder + '/pl_' + id + '/',
      output = new Map([
        [prefix + 'pl_' + id + '.model', result.data],
        [prefix + 'pl_' + id + '.b2it', lookup],
        [prefix + 'pl_' + id + '.grp2it', groups],
        [folder + '/chara_resources.rlist.txt', id + ', pl, F, A, 0.9, 0.75, 0.0\n'],
        [folder + '/借物表.txt', credits + '\n'],
      ]);
    for (const [n, b] of textureFiles) output.set(prefix + n, b);
    for (const [n, b] of files) if (/\.txt$/i.test(n)) output.set(folder + '/source-notes/' + n, b);
    status('Building downloadable package…');
    await yieldUI();
    const zip = packageZip(output);
    dancers.push({
      name: label,
      credits,
      model: result.decoded,
      textures: textureFiles,
      zip,
      folder,
      report: result.report,
    });
    $('dancer').replaceChildren(...dancers.map((d, i) => new Option(d.name, String(i))));
    $('dancer').value = String(dancers.length - 1);
    $('download').disabled = false;
    showPreview();
    status('Converted and validated. Preview the moves, then download your dancer.');
  } catch (e) {
    status(e.message, true);
  } finally {
    busy = false;
    checkModel();
  }
}
function showPreview() {
  const dancer = dancers[Number($('dancer').value)];
  if (!dancer) return;
  $('preview-credit').textContent = '借物表 — ' + dancer.name + '\n' + dancer.credits;
  $('dancer-name').textContent = dancer.name;
  try {
    const miku = $('reference').value === 'miku',
      name = miku ? 'pl_miku00.model' : 'pl_emi00.model',
      model = parseKtmdl(asset(name));
    if (!miku && assets.has('pl_emi00_face01.model')) {
      const face = parseKtmdl(asset('pl_emi00_face01.model')),
        head = new Matrix4().fromArray(model.bones[16].matrix),
        offset = model.names.length;
      for (const p of face.packets) {
        p.texture += offset;
        for (const v of p.vertices) {
          v.position = new Vector3(...v.position).applyMatrix4(head).toArray();
          v.ids = [16, 16, 16, 16];
          v.weights = [1, 0, 0, 0];
        }
        model.packets.push(p);
      }
      model.names.push(...face.names);
    }
    const reference = { model, textures: new Map(model.names.map((n) => [n, asset(n)])) };
    $('reference-name').textContent = miku ? 'Original Hatsune Miku' : 'Stock Emi';
    comparison ||= new Comparison($('preview'));
    comparison.set(reference, dancer);
    selectAnimation();
    comparison.onTime = (time) => {
      if (comparison.motion && document.activeElement !== $('seek'))
        $('seek').value = String(((time * 60) / comparison.motion.last) * 1000);
    };
  } catch (e) {
    status('Package is ready. Preview: ' + e.message, true);
  }
}
function selectAnimation() {
  if (!comparison) return;
  try {
    const name = $('animation').value,
      motion = name ? parseMotion(asset(name)) : null;
    if (motion)
      for (const entry of comparison.scenes) {
        if (entry.asset)
          assert(
            motion.parents.length === entry.asset.model.bones.length &&
              motion.parents.every((p, i) => p === entry.asset.model.bones[i].parent),
            'Animation does not match the selected reference skeleton',
          );
      }
    comparison.motion = motion;
    comparison.time = 0;
  } catch (e) {
    comparison.motion = null;
    status(e.message, true);
  }
}
function download() {
  const dancer = dancers[Number($('dancer').value)];
  if (!dancer) return;
  const url = URL.createObjectURL(new Blob([dancer.zip], { type: 'application/zip' })),
    a = document.createElement('a');
  a.href = url;
  a.download = dancer.folder + '.zip';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
// Remember inputs on this browser origin so reconnecting does not require setup again.
async function database() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('ddr-dancer-exporter', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('workspace');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function remember() {
  try {
    const db = await database();
    await new Promise((resolve, reject) => {
      const tx = db.transaction('workspace', 'readwrite');
      tx.objectStore('workspace').put(
        {
          assets: [...assets],
          files: [...files],
          mapping,
          label: $('label').value,
          credits: $('credits').value,
        },
        'latest',
      );
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    /* Storage may be unavailable on file:// or full; conversion still works. */
  }
}
async function restore() {
  try {
    const db = await database(),
      saved = await new Promise((resolve, reject) => {
        const r = db.transaction('workspace').objectStore('workspace').get('latest');
        r.onsuccess = () => resolve(r.result);
        r.onerror = () => reject(r.error);
      });
    db.close();
    if (saved) {
      for (const [n, b] of saved.assets) assets.set(n, b);
      files = new Map(saved.files);
      mapping = saved.mapping;
      $('label').value = saved.label;
      $('credits').value = saved.credits;
      $('model-choice').replaceChildren(...adapters.models(files).map((n) => new Option(n, n)));
      refreshAssets();
    }
  } catch {}
  checkModel();
}
$('assets').onchange = (e) => loadAssets(e.target.files);
$('assets-folder').onchange = (e) => loadAssets(e.target.files);
$('models').onchange = (e) => chooseModels(e.target.files);
$('model-folder').onchange = (e) => chooseModels(e.target.files);
$('model-choice').onchange = checkModel;
$('drop').ondragover = (e) => {
  e.preventDefault();
  $('drop').classList.add('over');
};
$('drop').ondragleave = () => $('drop').classList.remove('over');
$('drop').ondrop = (e) => {
  e.preventDefault();
  $('drop').classList.remove('over');
  chooseModels(e.dataTransfer.files);
};
$('drop').onkeydown = (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    $('models').click();
  }
};
$('mapping').onchange = async (e) => {
  try {
    mapping = JSON.parse(await e.target.files[0].text());
    status('Custom bone map loaded.');
  } catch (error) {
    status(error.message, true);
  }
};
$('convert').onclick = convert;
$('download').onclick = download;
$('dancer').onchange = showPreview;
$('reference').onchange = showPreview;
$('animation').onchange = selectAnimation;
$('cancel').onclick = async () => {
  try {
    if (job) await api('jobs/' + job, { method: 'DELETE' });
  } catch (e) {
    status(e.message, true);
  }
};
$('play').onclick = () => {
  if (comparison) {
    comparison.playing = !comparison.playing;
    $('play').textContent = comparison.playing ? 'Pause' : 'Play';
  }
};
$('speed').onchange = () => {
  if (comparison) comparison.speed = Number($('speed').value);
};
$('seek').oninput = () => {
  if (comparison?.motion)
    comparison.time = ((Number($('seek').value) / 1000) * comparison.motion.last) / 60;
};
$('stop').onclick = async () => {
  try {
    await api('shutdown', { method: 'POST' });
    capabilities = {};
    $('connection').textContent = 'PMX · browser / Blender · disconnected';
    $('stop').hidden = true;
    checkModel();
  } catch (e) {
    status(e.message, true);
  }
};
restore().then(checkBlender);
setInterval(checkBlender, 3000);
