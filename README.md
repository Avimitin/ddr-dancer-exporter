# DDR Dancer Exporter

**Bring your model to the DDR dance floor.**

Drop a model, compare its moves, and download an installable DDR dancer package.

**Open → Drop → Credit → Convert → Dance**

## Get started

1. Extract the Windows release ZIP into a writable folder.
2. Double-click **Start Exporter.cmd**. Your browser opens the exporter.
3. Under **Add your DDR reference files**, choose your compatible Hatsune Miku custom-mod folder. The template must contain `pl_miku00.model`, `.b2it`, `.grp2it`, and its DDS textures. These assets are not included.
4. Drop your model and textures, or a ZIP containing them.
5. Enter the dancer name and **借物表 / credits**, then click **Convert dancer**.
6. Preview the result and click **Download DDR dancer ZIP**.

No Python or Node.js installation is needed to use the release.

## Choose your model

| Input | What to do |
| --- | --- |
| **MMD / PMX** | Drop the PMX and its textures together, choose their folder, or use a ZIP. Common MMD bone names are mapped automatically. |
| **Blender / .blend** | [Install Blender](https://www.blender.org/download/), then run **Start Exporter.cmd**. The page enables Blender import when its local backend connects. Include external textures with the model. |
| **Other formats** | Direct FBX, VRM and Unity/VRChat project import is not available yet. Prepare a compatible rigged Blender scene first. |

Extract RAR archives before importing. If a ZIP contains multiple models, select the one you want in the **Model** dropdown. Unusual PMX rigs may need a `bone-map.json`; choose it under **Advanced: bone mapping**. See the [bone mapping reference](docs/TECHNICAL.md#bone-mapping).

If a `.blend` file is dropped while Blender is unavailable, the page shows installation instructions. After installing Blender, rerun the launcher; the page checks for the backend automatically. Portable Blender can be placed at `blender/blender.exe` beside the launcher.

## Compare the moves

Add your DDR `.anm` files, or `mc_female.arc` and `mc_bpm120.arc`, through the reference-file picker. To compare with stock Emi, also add `pl_emi00.arc` and `pl_emi00_face01.arc`.

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
