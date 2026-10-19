# DDR Dancer Exporter

Convert a PMX or Blender model into a DDR custom dancer, preview its movement, and download an installable ZIP.

## Get started

1. Extract the Windows release ZIP into a writable folder.
2. Double-click **Start Exporter.cmd**. Your browser opens the exporter.
3. Under **Your source model**, choose your model folder or drop a ZIP containing the model and its textures.
4. Under **DDR conversion reference**, choose a compatible DDR model folder containing its `.model`, matching `.b2it` and `.grp2it`, and all referenced `.dds` textures. The page checks compatibility and lists missing files.
5. Enter the dancer name and **借物表 / credits**, then click **Convert dancer**.
6. Preview the result and click **Download DDR dancer ZIP**.

No Python or Node.js installation is needed to use the release.

The conversion reference normally comes from an existing custom-dancer package under `data_mods/custom_models/dancers/<dancer>/pl_<id>/`. Select all reference files from the same dancer. Not every DDR model layout supports conversion; the page checks this automatically. Game and model assets are not included.

## Choose your model

| Input | What to do |
| --- | --- |
| **MMD / PMX** | Drop the PMX and its textures together, choose their folder, or use a ZIP. Common MMD bone names are mapped automatically. |
| **Blender / .blend** | [Install Blender](https://www.blender.org/download/), then run **Start Exporter.cmd**. The page enables Blender import when its local backend connects. Choose the `.blend` alone if textures are packed; otherwise include its texture folders. The scene needs a mesh with an armature and skin weights. |
| **Other formats** | Direct FBX, VRM and Unity/VRChat project import is not available yet. Prepare a compatible rigged Blender scene first. |

Extract RAR archives before importing. Keep texture filenames and subfolders unchanged. If a ZIP contains multiple models, select one in the **Source model** dropdown. Unusual PMX rigs may need a `bone-map.json`; choose it under **Optional: custom bone mapping**. See the [bone mapping reference](docs/TECHNICAL.md#bone-mapping).

If a `.blend` file is dropped while Blender is unavailable, the page shows installation instructions. After installing Blender, rerun the launcher; the page checks for the backend automatically. Portable Blender can be placed at `blender/blender.exe` beside the launcher.

## Compare the moves

Under **Preview files**, optionally add:

- **Animations:** dancer-motion archives (`mc_*.arc`) from the original game’s `data/` directory, or extracted `.anm` files. Modded installations may also have motions under `data_mods/background_dancers/`. Camera tracks and videos cannot animate the model.
- **Stock comparison:** any dancer archive (`pl_*.arc`) from the original `data/` directory and its subfolders, or an extracted `.model` with its `.dds` textures. Include matching face files if separate. Custom dancers can also be added for comparison.

The conversion reference is available for comparison without another upload. Without animation files, the preview shows the rest pose.

Select a reference dancer, converted dancer, and animation. Both sides share playback, seeking, speed, and camera controls. Drag the preview to orbit and scroll to zoom.

## Install in DDR

Unzip the download and copy the **whole dancer folder** into:

```text
data_mods/custom_models/dancers/
```

Keep its `chara_resources.rlist.txt`, model folder, and **借物表.txt** together. Restart DDR and test the dancer in-game.

> Every conversion requires credits. Include the original creator and rights holder, an AIGC note for AI-generated models, and retain the model's usage terms.

Conversion is experimental: some models may clip or deform unexpectedly. Cloth physics and facial animation are not transferred. The preview approximates game rendering.

[Troubleshooting and limits](docs/TECHNICAL.md) · [Building from source](docs/LOCAL-SERVICE.md#building-a-release)
