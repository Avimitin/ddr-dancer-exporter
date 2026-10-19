# Set up a local conversion workspace

Run commands in PowerShell from the repository root. These instructions describe the current desktop workflow.

## Python

The existing Windows workflow was tested with Python 3.10. Create an environment and install the pinned dependencies:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Blender is additionally required for `.blend` input. Point the import command at your own `blender.exe`; a portable Blender installation is not included. The existing importer was tested with Blender 4.5.9. A file saved by a newer Blender may need compatibility work.

## Local DDR assets

The current exporter uses a specific Miku custom-mod template. Arbitrary DDR dancer templates are not interchangeable with it. Supply your own compatible template files in:

```text
dancers/template-miku/model/
  pl_miku00.model
  pl_miku00.b2it
  pl_miku00.grp2it
  mk_acc.dds
  mk_bdy.dds
  mk_chr.dds
  mk_ehl.dds
  mk_eye.dds
```

Copy files from your local installation; the repository does not download them. See the [template constraints](TECHNICAL.md#export-backend) before substituting a different model.

The comparison renderer also needs stock Emi and DDR animation data:

```text
dancers/stock-emi/model/       pl_emi00.model, mdx_emi01.dds, lookup files
dancers/stock-emi/face/        pl_emi00_face01.model, mdx_emi01_face01.dds
animations/archives/         mc_female.arc, mc_bpm120.arc
animations/motions/          extracted .anm files and lookup files
```

If you have the stock archives, extract them with the supplied utility:

```powershell
.\.venv\Scripts\python.exe scripts\extract_arc.py "C:\YourAssets\pl_emi00.arc" "dancers\stock-emi\model"
.\.venv\Scripts\python.exe scripts\extract_arc.py "C:\YourAssets\pl_emi00_face01.arc" "dancers\stock-emi\face"
```

After creating your local dancer configuration in the [conversion guide](CONVERTING.md#create-a-local-dancer), extract the animation archives:

```powershell
.\.venv\Scripts\python.exe scripts\extract_motion.py --dancer my-dancer
```

The regular MP4 viewer uses a fixed comparison camera. `animations/camera/movie_st01_1p.camanm` is only needed for the older camera diagnostics, not the normal MP4 workflow.

## What stays local

All of `dancers/`, `animations/`, `analysis/`, and `backups/` is ignored by Git. This includes model configurations, bone maps, credits, textures, intermediate geometry, exports, and videos. Portable tools and generated preview catalogs are ignored too.

A source checkout will not have a working video library until you supply the reference assets and build previews. The preview HTML is a viewer, not a browser converter.
