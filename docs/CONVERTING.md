# Convert a model into a DDR dancer

Complete [setup](SETUP.md) first. The current pipeline expects a weighted rigged model; it does not automatically rig an unweighted mesh.

## Create a local dancer

Use a short folder name such as `my-dancer`. Extract the model archive into `source/`, preserving relative texture paths:

```powershell
New-Item -ItemType Directory -Force dancers/my-dancer/source, dancers/my-dancer/analysis
```

Create `dancers/my-dancer/dancer.json` with this configuration, substituting your own names and credits:

```json
{
  "id": "my-dancer",
  "label": "My Dancer",
  "kind": "converted",
  "input_type": "pmx",
  "credits": "Original model creator / other required credits",
  "template": "template-miku",
  "package_name": "My Dancer",
  "model_id": "mydancer00",
  "arm_retarget": true
}
```

Use `"input_type": "blend"` for Blender. Pick a unique, simple ASCII `model_id` and a package name without path separators. The folder name and `id` should match. These files stay local; do not add model-specific configuration to the repository.

`credits` is the mandatory **借物表**. Fill it with the source creator's required attribution. Add an AIGC note for AI-generated models. The exporter writes the credit sidecars automatically and the viewer displays the same text. Keep the original readme and usage terms with the source; conversion does not change those terms.

## PMX models

1. Put one intended `.pmx` file and its textures under `source/`. The inspector takes the first PMX it finds.
2. Inspect it:

   ```powershell
   .\.venv\Scripts\python.exe scripts\inspect_pmx.py --dancer my-dancer
   ```

3. Review `analysis/pmx-inspection.json`, then create `bone-map.json` beside `dancer.json`. Keys are the **exact source bone names**; values are DDR bone names.

   ```json
   {
     "下半身": "Hips",
     "上半身": "Spine",
     "上半身2": "Spine2",
     "首": "Neck",
     "頭": "Head",
     "左肩": "LeftCollar",
     "左腕": "LeftArm",
     "左ひじ": "LeftForeArm",
     "左手首": "LeftHand",
     "右肩": "RightCollar",
     "右腕": "RightArm",
     "右ひじ": "RightForeArm",
     "右手首": "RightHand"
   }
   ```

   This is an **illustrative fragment**, not a complete map. Add all weighted source bones, including legs, hair, fingers, and any twist helpers. See [mapping rules](TECHNICAL.md#bone-mapping). Arm retargeting also requires the collar, upper-arm, forearm, and hand anchor bones on each side, even if an anchor itself has no weighted vertices.

The PMX parser and exporter support the layouts exercised by this project; they do not guarantee full PMX 2.0/2.1 feature coverage. Resolve missing textures, unsupported sections, and material limits before export.

## Blender models

The importer reads visible mesh objects and an armature, evaluates supported geometry modifiers in the rest pose, and writes the intermediate geometry and bone map. It does not save the original `.blend` file.

Prepare a dedicated scene containing only the intended visible model meshes and one armature. Hide or remove unrelated meshes from that preparation copy. Ensure textures are available and vertices have armature weights.

Recognized arm chains use these exact names:

| Rig convention | Left chain | Right chain |
| --- | --- | --- |
| MMD-style | `肩.L → 腕.L → ひじ.L → 手首.L` | Same names ending in `.R` |
| Rigify-style subset | `shoulder.L → upper_arm.L → forearm.L → hand.L` | Same names ending in `.R` |

This is a naming subset, not support for every generated Rigify rig. Other names, control rigs, and unfamiliar bone hierarchies require adaptation in `scripts/import_blend.py`. Unknown bones fall back through their parents, so review `analysis/source-bone-map.json` rather than assuming a successful import means a correct mapping.

```powershell
& "C:\Path\To\Blender\blender.exe" --disable-autoexec --factory-startup `
  -b "dancers\my-dancer\source\model.blend" --python-exit-code 1 `
  --python scripts/import_blend.py -- --dancer my-dancer
```

Inspect the generated mapping and texture choices before proceeding. Materials use selected base-color images; node-based shading is not baked automatically. See [import limits](TECHNICAL.md#blender-import).

## FBX, VRM, and VRChat assets

There is no direct importer for these formats, and `.unitypackage` is not accepted as a model input. An upstream preparation workflow must produce a compatible Blender scene with the meshes, textures, armature, skin weights, and recognized bone names described above.

Saving an arbitrary imported avatar as `.blend` is not sufficient. Unity-specific shaders, components, and physics do not transfer through this pipeline. Format-specific preparation and additional importer adapters remain future work.

## Build and validate the package

Both input routes converge here:

```powershell
.\.venv\Scripts\python.exe scripts\compare_ddr.py --dancer my-dancer
.\.venv\Scripts\python.exe scripts\export_ddr.py --dancer my-dancer
.\.venv\Scripts\python.exe scripts\validate_export.py --dancer my-dancer
```

Stop on an error and resolve it before continuing. Your package appears under:

```text
dancers/my-dancer/output/My Dancer/
  chara_resources.rlist.txt
  借物表.txt
  pl_mydancer00/
    pl_mydancer00.model
    pl_mydancer00.b2it
    pl_mydancer00.grp2it
    *.dds
```

The exporter also copies a discovered source `.txt` readme as `SOURCE-NOTES.txt` when available. Retain any additional usage terms yourself. This stage creates a package directory; it does not universally create a ZIP.

## Preview and install

```powershell
.\.venv\Scripts\python.exe scripts\build_previews.py --dancer my-dancer --all
```

Double-click **Open Preview.cmd**, choose your dancer and animation, and inspect the arms, shoulders, feet, and body intersections. Use **Space** to play/pause and **← / →** to step frames. Previews use matching motion samples and a shared camera.

Without `--all`, the renderer builds six selected clips. For a shorter check, use `--clips mc_female_ht01_exec`. Each build replaces that dancer's preview manifest with the selected set; rebuild with `--all` to restore its full animation menu. Other dancers remain in the shared catalog.

Copy the entire `My Dancer` package folder to `data_mods/custom_models/dancers/` in your DDR installation. Keep the registration file, model subfolder, credits, and source notes together. Restart DDR and test in-game; binary checks and offline previews do not establish runtime compatibility.
