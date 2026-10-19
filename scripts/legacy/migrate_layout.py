raise SystemExit("Archived migration; not intended for the current project layout.")
"""One-time migration of the copied legacy workspace. Only touches this project."""
from pathlib import Path
import json,shutil
P=Path(__file__).resolve().parents[1]
def move(src,dst):
    src,dst=P/src,P/dst
    assert src.resolve().is_relative_to(P) and dst.resolve().is_relative_to(P)
    if not src.exists():return
    dst.parent.mkdir(parents=True,exist_ok=True)
    assert not dst.exists(),dst
    shutil.move(str(src),str(dst))
for name in ('pl_miku00.model','pl_miku00.b2it','pl_miku00.grp2it'):
    move('reference/'+name,'dancers/template-miku/model/'+name)
for name in ('mc_female.arc','mc_bpm120.arc'):move('reference/'+name,'animations/archives/'+name)
move('reference/motions','animations/motions')
move('reference/movie_st01_1p.camanm','animations/camera/movie_st01_1p.camanm')
if (P/'reference').exists() and not list((P/'reference').iterdir()):(P/'reference').rmdir()
nested=P/'dancers/adelie-tomorin/preview/preview'
if nested.exists():
    for file in nested.iterdir():move(str(file.relative_to(P)),str(file.parent.parent.relative_to(P)/file.name))
    nested.rmdir()
for name in ('inspect_pmx.py','export_ddr.py','validate_export.py','preview_motion.py','compare_ddr.py'):
    path=P/'scripts'/name;s=path.read_text(encoding='utf-8')
    s=s.replace("ROOT = pathlib.Path(__file__).resolve().parents[1]","from project import PROJECT,DANCER,TEMPLATE,MOTIONS,CAMERA,CONFIG,output_model_dir\nROOT = DANCER")
    s=s.replace("ROOT=Path(__file__).resolve().parents[1]","from project import PROJECT,DANCER,TEMPLATE,MOTIONS,CAMERA,CONFIG,output_model_dir\nROOT=DANCER")
    s=s.replace("root=pathlib.Path(__file__).resolve().parents[1]","from project import PROJECT,DANCER,TEMPLATE\nroot=DANCER")
    s=s.replace("str(ROOT/'tools')","str(PROJECT/'tools')")
    s=s.replace("ROOT/'reference/pl_miku00.model'","TEMPLATE/'pl_miku00.model'")
    s=s.replace("ROOT/f'reference/pl_miku00.{ext}'","TEMPLATE/f'pl_miku00.{ext}'")
    s=s.replace("root/'reference/pl_miku00.b2it'","TEMPLATE/'pl_miku00.b2it'")
    s=s.replace("root/'reference/pl_miku00.grp2it'","TEMPLATE/'pl_miku00.grp2it'")
    s=s.replace("(root/'reference').iterdir()","TEMPLATE.iterdir()")
    s=s.replace("ROOT/'output/Adelie Tomorin/pl_tomorin00'","output_model_dir()")
    s=s.replace("'pl_tomorin00.model'","('pl_'+CONFIG['model_id']+'.model')")
    s=s.replace("f'pl_tomorin00.{ext}'","f\"pl_{CONFIG['model_id']}.{ext}\"")
    s=s.replace("'tomorin00, pl, F, A, 0.9, 0.75, 0.0\\n'","CONFIG['model_id']+', pl, F, A, 0.9, 0.75, 0.0\\n'")
    s=s.replace("ROOT/'reference/movie_st01_1p.camanm'","CAMERA")
    s=s.replace("ROOT/'reference/motions'","MOTIONS")
    s=s.replace("ROOT/'reference/motions/mc_female_sf02_exec.anm'","MOTIONS/'mc_female_sf02_exec.anm'")
    path.write_text(s,encoding='utf-8')
# Source paths in regenerated inspection output will use the new workspace.
print('Migrated model assets and script paths.')
