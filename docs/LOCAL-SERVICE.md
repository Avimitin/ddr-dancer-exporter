# Static frontend and Blender backend

## Runtime architecture

The launcher **always opens `web/index.html` as a static file**. The same bundle
works without a backend for PMX import, texture conversion, arm retargeting,
KTMDL writing, validation, ZIP download and live animation comparison.

The page polls `http://127.0.0.1:8765/api/capabilities`. It enables the Blender
adapter only after a successful authenticated response. A missing backend never
disables PMX. Dropping `.blend` without it displays an error and an official
Blender installation link. A newly connected backend enables the format without
navigating away from the page.

The optional backend consists of **Blender plus the bridge**, not a separate
system Python installation. `Launch.ps1` attempts to start
`service/blender_bridge.py` with Blender's embedded Python. The bridge exposes
an import API only; it does not serve or replace the webpage. Each import runs
another background Blender process so scene loading cannot corrupt service
state. Imported geometry and diffuse images return to the browser, which
performs DDR conversion through the same library used for PMX.

No Python or Node.js runtime is bundled. Node.js is a developer build dependency
only. Blender remains an optional installed application. The existing desktop
Python scripts and MP4 viewer remain available for development and regression
comparison; the new browser uses live GPU skinning rather than generating MP4s.

## DDR reference discovery

`web/lib/references.js` discovers uploaded `.model` files by extension and reads
their contents. The conversion picker checks the supported writer layout and
same-stem `.b2it`/`.grp2it` files, plus the texture names stored inside the model.
It reports missing filenames without requiring users to inspect binary metadata.
The writer still requires its existing 33-bone, nine-packet, five-texture layout
with 48-byte vertices and a shared palette; generic filenames do not broaden
that binary support.

Comparison candidates are independent of writer compatibility. Readable body
models are listed regardless of character name; separate face files are attached
by matching basename. Animation skeleton compatibility is checked on selection.
Original stock archives can be selected directly or extracted first. Uploaded
DDR assets currently share a flat filename namespace; loading a file with an
existing filename replaces that file.

## Adapter contract

`web/lib/adapters.js` defines the registry and current adapters. An adapter has:

- `id` and `extensions` for discovery;
- `available(capabilities)` for dependency gating;
- asynchronous `import(context)` returning a common model representation.

The import context supplies a `Map<string, Uint8Array>` of files, the selected
model name, an optional source-to-DDR bone map, and a bridge callback. The common
representation contains:

```text
vertices: position[3], normal[3], uv[2], weights[[sourceBoneIndex, weight], ...]
indices: flattened triangle indices
source: bones, materials, textures, triangle count, optional origin/arm_bind
mapping: source bone name -> DDR bone name
base: relative directory for texture lookup
files: optional replacement file map (used for Blender-generated PNGs)
```

Adapters normalize data into the existing PMX-oriented intermediate coordinate
convention. `exporter.js` handles DDR facing, global height fitting, arm rest
transforms, twist weights, packet construction and validation. A new format
adapter should not write DDR packets or implement another retargeter. Register
it in `registry()` and add import/geometry regression fixtures.

`exporter.js`, the binary readers and animation parser are independent of the
DOM and service. Texture decoding/encoding is a separate browser adapter using
canvas and Three.js loaders. DDS output uses full BGRA8 mip chains; canvas
resampling may differ from the legacy Pillow renderer. Source PNG/JPEG and TGA
are supported, as are uncompressed RGBA DDS textures. Compressed DDS source
textures must first be converted to PNG. Preview DDS loading also supports
formats handled by Three.js and the browser GPU.

## Local bridge

The launcher searches `DDR_BLENDER`, PATH, `blender/blender.exe`, standard Blender
Foundation installation directories, and the project's local `tools/` folder.
Unusual installation locations can use `DDR_BLENDER`. After installation, rerun
the launcher to start the bridge. The browser cannot launch native applications
or discover executables itself; it detects backend availability through the API.

The bridge binds only to loopback. A random credential in the ignored
`.bridge-token` file is passed to the static page in its URL fragment, then
removed from the address bar and retained in session storage. Every API request
requires that bearer credential. CORS explicitly supports the `null` origin of
local static files and the bridge's own loopback origins; arbitrary website
origins and unexpected Host headers are rejected. The preflight response does
not expose model data. Browser local-network permission may need to be allowed.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/capabilities` | Confirm Blender availability |
| POST | `/api/jobs` | Create an import with credits and selected relative model path |
| PUT | `/api/jobs/<id>` | Upload a ZIP of the model and textures |
| GET | `/api/jobs/<id>` | Read status and bounded log tail |
| GET | `/api/jobs/<id>/result` | Download common geometry and texture ZIP |
| DELETE | `/api/jobs/<id>` | Cancel queued/running import |
| POST | `/api/shutdown` | Disconnect and stop the bridge |

Imports run serially, with a 30-minute timeout, process-tree cancellation, a
512 MiB upload limit, a 1 GiB unpacked ZIP limit, and 10,000-entry cap. Archive
traversal, duplicate paths and symlinks are rejected. Automatic Blender script
execution is disabled. This is a local application, not a sandbox for hostile
Blender files or a service intended for public network exposure.

Each imported Blender model has its own ignored `dancers/web-<id>/` directory
with source, configuration, intermediate data and logs. Browser-only inputs
remain in memory and may be remembered through IndexedDB on the current browser
origin. Downloads are saved through the browser. Model assets and per-model
configuration are never part of the release ZIP.

## Building a release

Developers need Node.js and npm; end users do not.

```powershell
npm ci
npm run build
npm test
npm run release
```

`npm run build` produces a classic, self-contained `web/app.bundle.js`. It runs
from `file://`, without module-fetch CORS issues, a development server, a CDN,
or network downloads. `npm run release` writes
`dist/ddr-dancer-exporter-windows.zip`, containing the webpage, launcher, optional
Blender bridge, source and dependency license notices. It includes no runtimes,
private tokens, model assets, or per-model JSON files.

Tests using existing local fixtures:

```powershell
.\.venv\Scripts\python.exe tests/test_bridge.py
.\.venv\Scripts\python.exe tests/test_frontend.py
```

The first checks HTTP/archive boundaries without Blender. The second requires
private Tomorin/Nailong/Miku assets, animation archives, local Blender and
Playwright Chromium. It starts from a static `file://` page with no backend,
exports PMX, then starts Blender and verifies live capability detection and
Blender conversion on that same page. These test tools are not release runtime
dependencies. The JS test suite skips private geometry regressions when those
fixtures are absent.
