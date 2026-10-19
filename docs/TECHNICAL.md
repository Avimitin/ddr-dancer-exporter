# Technical reference

## Export backend

The writer rebuilds KTMDL geometry using the local `template-miku/model/pl_miku00.model` layout. It retains the reference's 33-bone rig, inverse-bind matrices, shader identifiers, texture names, and nine packet slots. It is not a general writer for arbitrary DDR templates.

- At most five referenced source textures; material texture indices must fit slots 0–4.
- At most nine populated material groups; smaller groups are split to fill nine packets.
- Fewer than 65,536 distinct vertices in each packet.
- Up to four skin influences per vertex, normalized after merging or reduction.
- DDS textures use uncompressed BGRA8, power-of-two dimensions capped at 1024, and full mip chains.
- Height and facing are normalized. Arm/collar geometry is fitted to DDR's rest frames; other body proportions are not comprehensively retargeted.

Outputs keep DDR's residual first-weight convention. Validation reparses the written model and checks positions, weights, index and buffer ranges, finite UVs, normals, and DDS payloads.

## Bone mapping

`bone-map.json` maps source bone names to DDR names. `compare_ddr.py` requires a target for every weighted source bone and verifies targets against the local B2IT lookup.

Core destinations include `Hips`, `Spine`, `Spine1`, `Spine2`, `Neck`, `Head`, and the left/right versions of `Collar`, `Arm`, `ArmRoll`, `ForeArm`, `ForeArmRoll`, `Hand`, `UpLeg`, `UpLegRoll`, `Leg`, `LegRoll`, `Foot`, and `ToeBase`. Consult the actual template lookup for the complete list. Do not assign weighted geometry to `Reference1`, which is outside the template packet palette.

Map hair/eyes to `Head` and fingers to the corresponding `Hand` where those simplified behaviors are acceptable. The target rig has no independent finger or facial-animation bones. Unweighted controls can be omitted except the anatomical anchors required by the arm rebind.

Arm retargeting is enabled by default. `arm_twist_weights` may be `source` or `spatial`; if omitted, the exporter chooses based on whether mapped roll weights exist. `arm_retarget: false` retains the old unaligned behavior and is intended for diagnostics. See [arm retargeting](ARM-RETARGETING.txt).

## Blender import

`scripts/import_blend.py` depends on Blender's `bpy` runtime. It selects the first armature and visible, render-enabled meshes. It disables deformation/physics modifiers, evaluates mirror, limited subdivision, and non-outline solidify geometry, and reads the rest mesh with its skin weights.

The importer selects base-color image candidates and groups triangles by texture. This is not a material baking engine. Normal maps, toon effects, cloth and hair physics, facial morphs, and outline effects are omitted. More than five texture groups requires preparation outside this importer.

World-space arm anchors are retained for retargeting. The intermediate filenames remain `pmx-inspection.json` and `pmx-geometry.json` for shared backend compatibility; `input_format` identifies Blender inputs.

## Preview pipeline

The renderer decodes local DDR ANM files and assumes a source rate of 60 Hz. The default output is 640×640 H.264 MP4 at 30 fps. Stock Emi includes a separate face mesh attached to `Head`. CPU skinning and two-sided alpha-tested rasterization approximate game rendering.

Each dancer owns `preview/manifest.json`. The catalog combines completed manifests into `preview/manifest.json` and `manifest.js`, allowing the HTML viewer to run directly from disk without a server. Cached stock videos are reused when frame count, resolution, and fps match.

All assets, configurations, generated manifests, reports, and videos are local and Git-ignored. The checked-in `preview/` files contain only the viewer UI. The original custom Miku can be added as a reference using a local template profile with `model`, `model_id`, `credits`, and `preview_kind`; it is not a converted output.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing `dancer.json` | Create the local profile and pass its exact folder name with `--dancer` |
| Missing source rest joint | Supply the collar, upper-arm, forearm, and wrist anchors on both sides; re-import older Blender intermediates |
| Weighted source bone has no target | Complete the PMX bone map or adapt the Blender mapping |
| Missing texture or too many material groups | Restore relative paths and reduce texture/material groups to the backend limits |
| Missing template, stock mesh, or animation | Follow [local asset setup](SETUP.md#local-ddr-assets) |
| Wrong-looking Blender material | Inspect the chosen base-color image; unsupported shader nodes are not baked |
| Intersections despite valid output | Review proportions, skin weights, and rest alignment; there is no collision solver |
| No videos after cloning | Supply local assets and run `build_previews.py`; media is not distributed |

## Dependencies and provenance

KTMDL and ANM parsers come from `moth1995/pes2008-2013-tools` under GPL-3.0-or-later. The ARC LZ77 decoder comes from `DragonMinded/bemaniutils` under the Unlicense, with a local import adaptation. See [upstream notes](../tools/UPSTREAM.txt), [parser license](../tools/LICENSE.upstream), and [decoder license](../tools/LICENSE.bemaniutils).

Tool licensing does not supply rights to model or game assets. Keep model-specific credits and usage terms with local inputs and exported packages.
