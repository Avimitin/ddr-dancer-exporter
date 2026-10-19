# DDR Dancer Exporter

**Bring your model to the DDR dance floor.**

Convert a rigged model into a DDR dancer package, compare its moves with a reference dancer, and copy the result into your custom-models folder.

**Import → Credit → Convert → Preview → Install**

[Get started](docs/SETUP.md) · [Conversion guide](docs/CONVERTING.md) · [Format limits](docs/TECHNICAL.md) · [Browser version proposal](docs/STATIC-FRONTEND.md)

## Choose your starting point

| Your model | Route | Current support |
| --- | --- | --- |
| **MMD / PMX** | `.pmx` + textures → exporter | Experimental; supply a bone map |
| **Blender** | Rigged `.blend` + textures → Blender importer → exporter | Experimental; recognized MMD/Rigify-style arm names |
| **FBX, VRM, VRChat assets** | Prepare a compatible rigged Blender model first | No direct import; saving as `.blend` alone is not enough |

ZIP/RAR downloads must be extracted first. Keep the model's textures and original readme together.

## Make your first dancer

### 1. Set up your workspace

Follow the [one-time setup](docs/SETUP.md), then create a local dancer folder with its model, configuration, and credits. The [conversion guide](docs/CONVERTING.md#create-a-local-dancer) includes a configuration you can copy.

Models, DDR reference assets, animations, and generated videos are **not included** in this repository. Everything under `dancers/` stays local, including configuration files and credits.

### 2. Import your model

Run commands in PowerShell from the project folder. Replace `my-dancer` with your dancer's folder name.

**Starting with PMX:**

```powershell
.\.venv\Scripts\python.exe scripts\inspect_pmx.py --dancer my-dancer
```

Then [map its bones](docs/CONVERTING.md#pmx-models) to the DDR rig.

**Starting with Blender:**

```powershell
& "C:\Path\To\Blender\blender.exe" --disable-autoexec --factory-startup `
  -b "dancers\my-dancer\source\model.blend" --python-exit-code 1 `
  --python scripts/import_blend.py -- --dancer my-dancer
```

The Blender importer creates the bone map for recognized rigs. See [Blender preparation](docs/CONVERTING.md#blender-models) before importing a new model.

### 3. Convert and preview

```powershell
.\.venv\Scripts\python.exe scripts\compare_ddr.py --dancer my-dancer
.\.venv\Scripts\python.exe scripts\export_ddr.py --dancer my-dancer
.\.venv\Scripts\python.exe scripts\validate_export.py --dancer my-dancer
.\.venv\Scripts\python.exe scripts\build_previews.py --dancer my-dancer --all
```

Double-click **Open Preview.cmd**. Pick a dancer and an animation, then play both sides together. The offline viewer supports smooth MP4 playback, shared seeking, speed control, looping, and frame stepping.

### 4. Install your dancer

Copy the **whole package folder** from:

```text
dancers/my-dancer/output/My Dancer/
```

into your DDR installation's:

```text
data_mods/custom_models/dancers/My Dancer/
```

Keep `chara_resources.rlist.txt`, the model subfolder, and the **借物表** together. Restart DDR and test the dancer in-game.

> **Credits travel with the model.** Every conversion requires a non-empty 借物表. Include creator credits and an AIGC note where applicable, and retain the source model's usage terms.

## What to expect

This is an experimental converter. Arm alignment and twist weights are fitted to DDR, but broad bodies and wings can still intersect. Cloth physics and facial animation are not transferred. The preview is an approximation; successful export is not proof of correct in-game behavior.

The current converter runs locally with Python and, for `.blend`, Blender. A drag-and-drop browser converter is [a proposed next step](docs/STATIC-FRONTEND.md), not an existing feature.

For implementation details, testing, and troubleshooting, start with the [documentation index](docs/README.md).
