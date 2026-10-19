# A browser-based DDR dancer exporter

**Status: architecture proposal, not an implemented feature.** The existing
preview is static HTML, but conversion and MP4 generation currently run locally
through Python and, for `.blend` files, Blender.

## What can be fully static?

A PMX converter can run entirely in a browser and be hosted on GitHub Pages or
another static host. Users would select or drop a model and its textures, supply
credits, inspect the conversion, and download a DDR dancer ZIP. No conversion
server is inherently needed. Browsers expose user-selected and dropped local
files through the [File API](https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications).

The app also needs user-supplied DDR reference assets: this exporter depends on
a particular Miku template and game animations. Those assets should be imported
locally, not bundled with the site or library. A stock dancer is additionally
needed for side-by-side comparison. Optional browser storage could remember
these imports, subject to storage limits and user consent.

| Input | Browser-only route | Remaining work |
| --- | --- | --- |
| PMX and textures | Direct import | Port parsing, mapping, retargeting and package writing |
| Blender scene | Export an intermediate package using Blender first | Create an add-on or export script |
| glTF / GLB | Potential direct import | Add a skin/material adapter and mapping workflow |
| VRM | Potential direct import | Add VRM-aware rig and material handling |
| Raw `.blend` | Not a straightforward library port | Reproduce or port Blender's scene evaluation |
| Unity / VRChat project | Prepare/export its underlying model first | Unity-specific features need separate handling |

These are proposed routes, not current format support. Merely parsing a file
does not reproduce its shaders, constraints, physics or evaluated geometry.

## Why Blender is different

Our Blender importer uses `bpy`, Blender's dependency graph and evaluated mesh
access to apply selected modifiers and obtain geometry. A `.blend` reader alone
would not reproduce this behavior. Bundling the current script therefore does
not provide raw `.blend` conversion in a browser.

The practical first solution is a Blender export bridge: evaluate the scene
inside Blender and write geometry, rest bones, weights, textures and metadata
into an intermediate ZIP. The static app then converts that package. This keeps
the website serverless, but requires a preprocessing step for Blender inputs.
A desktop helper or server could accept raw `.blend` files directly; that would
change the fully browser-only requirement. A faithful browser Blender runtime
would be a separate research project, not a promised extension of this port.

## Library and application boundary

```text
PMX / intermediate ZIP / future format adapters
                       |
                       v
Common model representation + credits + imported DDR reference assets
                       |
                       v
Bone mapping -> rest-pose retargeting -> material conversion -> validation
                       |
                       v
KTMDL / DDS / lookup and registration files / credits
                       |
                       +----> DDR dancer ZIP
                       +----> Decode exported data -> comparison preview
```

The common representation should carry positions, normals, UVs, material images,
bone hierarchy and rest transforms, skin weights, coordinate conventions and
credits. Format adapters should produce it without depending on the UI.

Expose the conversion library as byte-array inputs and outputs, with progress
and cancellation hooks. Keep file selection, browser storage, ZIP downloads and
UI state in separate adapters. The current `project.py` reads command-line
arguments and local configuration at import time, and entry scripts perform
filesystem operations; those dependencies must first be separated from the
conversion algorithms. This is a refactor and port, not just a bundler setting.

A TypeScript core is a reasonable starting point; expensive texture or geometry
operations can move to Rust/WebAssembly if profiling justifies it. Run conversion
in a worker so large models do not freeze the interface. Python via Pyodide is
another prototype route, but compatibility must be checked: browser Python has
[runtime constraints](https://pyodide.org/en/stable/usage/wasm-constraints.html),
and our Blender, Numba renderer and native FFmpeg process are not a drop-in web
stack. Do not port the CPU video pipeline just to provide interactive previews.

## User experience

1. Import the required local DDR reference assets during setup.
2. Drop a ZIP containing the model and textures, or select its files together.
3. Enter the mandatory **借物表** credits, including an AIGC note when applicable.
4. Review automatically suggested bone mappings and any unsupported materials.
5. Compare stock and converted dancers with synchronized animation, seeking,
   speed and camera controls. Allow switching among converted dancers.
6. Download a ZIP containing the installable dancer directory and credits.

Use a GPU-rendered live preview for smooth interaction without generating MP4s
for every clip. It should decode the exported KTMDL, so users inspect the actual
conversion result. It remains an approximation of game rendering and cannot
replace in-game testing. An optional downloadable offline preview can contain
the viewer and user-selected assets; MP4 export is a separate later feature
whose codec support and performance need testing.

The intended privacy model is local processing with no asset upload. Enforce
that in implementation, including third-party resources and telemetry. Handle
archive paths safely, preserve Japanese/Chinese filenames, resolve texture paths
consistently, and reject archive traversal. Bound memory use and decompressed
archive sizes, report missing textures, and provide cancellation.

## Suggested implementation order

1. Separate the existing conversion core from filesystem and CLI state. Record
   local regression fixtures for geometry, arm orientation, weights and output
   structure; do not publish model assets without permission.
2. Build the PMX browser path and DDR ZIP writer. Validate packet limits, bone
   palettes, texture output and credits against the desktop exporter.
3. Add synchronized live preview and animation selection. Include FEMALE/HT01
   and other challenging arm poses in regression checks.
4. Add the Blender intermediate export bridge, then glTF/VRM adapters as separate
   features with explicit supported subsets.

Start with PMX to establish a complete browser workflow. Keep the existing
desktop exporter available while browser output is compared with it and tested
in game.
