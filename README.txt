DDR Dancer Exporter
===================

Open preview/index.html (or double-click Open Preview.cmd).
The viewer works directly from disk. It uses local H.264 MP4 files, with
no CDN, server, network connection or additional browser library required.

Preview features
----------------
Choose Tomorin, Nailong, Ano, or the original Hatsune Miku custom mod against stock Emi at 30 fps.
The library contains 15 animations for each dancer (75 MP4 files), at 640x640
per dancer, covering each clip's full duration rather than short excerpts.
Select a converted dancer (preserving the current animation), select a DDR animation, play/pause both dancers, seek, restart, change speed,
loop, or step one frame. Space toggles playback; arrow keys step frames.
Both models use the same animation sample, scale, camera and ground line.
Stock Emi includes her separate default face attached to the Head bone.
Each MP4 contains newly rendered frames from the actual animation data;
it is not a re-encoding or interpolation of the old sparse GIF previews.

Layout
------
dancers/
  adelie-tomorin/
    dancer.json          Model identity, template, output name and credits
    bone-map.json        Model-specific source -> DDR bone mapping
    借物表.txt            Required model credits
    source/              Extracted original PMX, textures and readme
    analysis/            Inspection, conversion and validation reports
    output/              Staged DDR package and ZIP
    preview/mp4/         Converted model's animation previews
  stock-emi/
    dancer.json
    model/               Extracted stock body, skeleton and texture
    face/                Extracted stock default face attachment
    preview/mp4/         Stock comparison animation previews
  template-miku/
    dancer.json
    model/               Known KTMDL/B2IT template used by exporter
animations/
  archives/              Read-only copies of DDR animation ARC files
  motions/               Extracted .anm files and motion lookup tables
  camera/                Copied camera animation
scripts/                 Shared inspection, export, render and test tools
tools/                   Third-party format parsers and their licenses
preview/                 Shared HTML comparison viewer and manifest

Credits are mandatory
---------------------
EVERY converted input model MUST have a non-empty "credits" string in its
dancer.json. This is its 借物表. Missing, blank or non-string values are rejected
before export or preview generation. The viewer also refuses a converted
model without credits. The exporter writes the credits to BOTH:
  dancers/<id>/借物表.txt
  dancers/<id>/output/<package>/借物表.txt
The viewer displays the same credits beneath the converted dancer.

For Adelie Tomorin the exact required credit is:
Bushiroad Games/オキアミ

The original source readme is retained alongside these mandatory credits.
Stock Emi is identified as KONAMI / DDR game assets, not as a converted input.

Commands (PowerShell, from this project directory)
------------------------------------------------
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\inspect_pmx.py --dancer adelie-tomorin
.\.venv\Scripts\python.exe scripts\compare_ddr.py --dancer adelie-tomorin
.\.venv\Scripts\python.exe scripts\export_ddr.py --dancer adelie-tomorin
.\.venv\Scripts\python.exe scripts\validate_export.py --dancer adelie-tomorin
.\.venv\Scripts\python.exe scripts\build_previews.py --dancer adelie-tomorin --all

build_previews.py without --all renders six representative clips.
Use --clips <clip_stem> <clip_stem> to select specific clips.
Each dancer has preview/manifest.json. Rendering updates that dancer's set;
all completed sets are combined into the shared catalog by scripts/catalog.py.
Stock MP4s are reused when their frame count, resolution and fps match.

To register another converted model, create dancers/<id>/ with dancer.json,
source/ and bone-map.json. The configuration needs id, label, kind="converted",
credits, template="template-miku", package_name, and model_id. The PMX and
mapping must satisfy the current export backend's limitations below.
Use --dancer <id> with the shared scripts. A folder alone is not a converter.

Export limitations
------------------
The current KTMDL backend still depends on the Miku template, 33-bone DDR
skeleton, nine packet slots and up to five source textures. Materials are
split to fit nine packets. The Blender importer groups surfaces by diffuse
texture and maps existing skin weights to the DDR bones. Arbitrary FBX or
VRChat input is not supported.
Hair/eyes follow Head; PMX physics and facial morphs are omitted.
Body proportions are retained; arm/collar rest poses and twist weights are fitted to DDR.
Known motion issues include torso folding, intersections and ground penetration.

These are offline previews, not footage captured in DDR. CPU skinning uses
decoded DDR ANM data; source animation sample rate is assumed to be 60 Hz.
The renderer approximates materials with two-sided, alpha-tested surfaces.
Actual DDR loading, shaders, culling and runtime registration remain untested.
Old GIF and camera diagnostics are retained in the model's preview directory.

The old D:\Share\ddr-adelie-tomorin directory was retained as a backup because
Windows blocked renaming it. All current work lives in ddr-dancer-exporter.
No live DDR installation files were changed.

Tool provenance
---------------
KTMDL and ANM parsers: moth1995/pes2008-2013-tools, GPL-3.0-or-later.
ARC LZ77 decoder: DragonMinded/bemaniutils, Unlicense. Local adaptation removes
its package-relative import; optional native loading is not used here.
See tools/UPSTREAM.txt, LICENSE.upstream, and LICENSE.bemaniutils.
The tool licenses do not grant redistribution rights to game/model assets.

Development validation
----------------------
Install requirements-dev.txt, then run python -m playwright install chromium.
tests/test_viewer.py tests the local-file viewer in an isolated headless
browser, including MP4 decoding, sync, selection, seeking and visible credits.
tests/test_credits.py tests mandatory-credit enforcement.

Blender additions
-----------------
dancers/nailong and dancers/ano follow the same per-model layout.
Nailong credits: bingloe（AIGC / AI-generated） (AI status confirmed by user).
Ano credits: 很ying的哈呵 (from the included readme; Liope is the uploader).
Ano's readme prohibits redistribution; its local output includes SOURCE-NOTES.txt.
No packages were published or copied into the live game.

Use tools/blender-4.5.9-windows-x64/blender.exe --disable-autoexec
--factory-startup -b <source.blend> --python-exit-code 1
--python scripts/import_blend.py -- --dancer <id>, then run compare_ddr.py,
export_ddr.py, validate_export.py and build_previews.py --all for that id.
The importer writes the shared pmx-named intermediate JSON files for reuse
by the export backend; input_format records that the original is Blender.
It never saves the original blend. It exports visible meshes, mirror and
limited subdivision, base color textures and existing bone weights.
Blender cloth, toon shaders, normal maps, hair physics and morphs are omitted.
Nailong was saved by Blender 5.0; Blender 4.5 reports a version warning.
Its mesh/UV/weights were extracted and validated, but full Blender scene
compatibility is not claimed. Both new models remain experimental in DDR.

Original custom-mod reference
----------------------------
Hatsune Miku is selectable as an unconverted custom-mod reference. It uses
byte-identical model, lookup and DDS files copied from the installed mod;
see dancers/template-miku/analysis/source-verification.json. The supplied
folder has no model/mod author attribution, which is stated in the viewer.

Arm correction
--------------
All three converted exports now align their arm/collar rest geometry to DDR
joint pivots, with bone-axis length correction and roll weights. The Blender
importer retains actual source rest anchors and maps Ano twist groups to DDR
roll bones; sources without those groups get gradual spatial roll weights.
See analysis/arm-fix/README.txt, validation.json and ht01-before-after.jpg.
The original faulty exports and videos are in backups/before-arm-fix/.
Historic diagnostic files under analysis/arm-bind-diagnosis describe the old
exports. The correction is now applied to output models and rebuilt MP4s.
Broad-body and wing intersections remain possible; no collision solver runs.

Source layout and version control
--------------------------------
Shared implementation lives in src/ddr_dancer_exporter/. Command scripts stay
in scripts/, investigations in scripts/diagnostics/, and tests in tests/.
See docs/DEVELOPMENT.txt for setup and validation. Generated media, outputs,
assets, backups and portable tools remain local and are excluded from Git.
