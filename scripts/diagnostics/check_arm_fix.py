"""Validate the exported arm correction and render HT01 before/after evidence."""
import _bootstrap  # Local src/ discovery for direct invocation.
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from ddr_dancer_exporter.rendering import load_model,frame,read_motion,pose
from ddr_dancer_exporter.fast_renderer import deform
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'analysis/arm-fix';OUT.mkdir(parents=True,exist_ok=True)
motion=read_motion(ROOT/'animations/motions/mc_female_ht01_exec.anm')
sheet=Image.new('RGB',(1600,1200));draw=ImageDraw.Draw(sheet);report={}
def read(p):return json.loads(p.read_text(encoding='utf8'))
for row,name in enumerate(['ano','nailong','adelie-tomorin']):
    root=ROOT/'dancers'/name;old=ROOT/'backups/before-arm-fix/dancers'/name;cfg=read(root/'dancer.json')
    path=Path('output')/cfg['package_name']/('pl_'+cfg['model_id']);fn='pl_'+cfg['model_id']+'.model'
    before=load_model(old/path,fn);after=load_model(root/path,fn)
    alignment=read(root/'analysis/arm-retarget.json')
    assert max(j.get('endpoint_error_after',0) for j in alignment['joints'])<1e-7
    assert max(j['direction_error_after'] for j in alignment['joints'])<1e-7
    assert all(v>0 for v in alignment['roll_weight_sums'].values())
    # Audit source data against decoder; this checks actual packed handedness.
    for bi,sign in [(31,1),(32,-1)]:
        w=np.sum(after['weights']*(after['ids']==bi),axis=1);mask=w>.1
        assert np.all(after['pos'][mask,0]*sign>0)
    metrics=[]
    for label,a in [('before',before),('after',after)]:
        ids=a['ids'];w=a['weights'];pos=a['pos'];f=a['faces']
        arm=np.sum(w*np.isin(ids,[17,18,21,22,25,26,29,30,31,32]),axis=1)>.5
        edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
        lengths=np.linalg.norm(pos[edges[:,0]]-pos[edges[:,1]],axis=1)
        valid=(lengths>.001)&arm[edges].all(axis=1);edges=edges[valid];lengths=lengths[valid]
        worst=0.;radii={};handmasks={bi:np.sum(w*(ids==bi),axis=1)>.9 for bi in [31,32]}
        for sample in np.linspace(0,motion['header']['lastSampleIndex'],65):
            world=pose(a['model'],motion,sample);p=deform(pos,ids,w,a['inv']@world);assert np.isfinite(p).all()
            ratio=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1)/lengths
            worst=max(worst,float(np.percentile(ratio,99)))
            for bi,mask in handmasks.items():
                radius=float(np.median(np.linalg.norm(p[mask]-world[bi,3,:3],axis=1)))
                radii[bi]=max(radii.get(bi,0),radius)
        metrics.append(dict(version=label,max_arm_edge_stretch_p99=worst,hand_center_distance_to_wrist=radii,poses_checked=65))
    for col,(label,a,t) in enumerate([('Before',before,0),('Fixed',after,0),('Before',before,16),('Fixed',after,16)]):
        pic=Image.fromarray(frame(a,motion,t*60,800)).crop((150,130,650,630)).resize((400,400))
        sheet.paste(pic,(col*400,row*400));draw.text((col*400+8,row*400+8),f'{name} | {label} | HT01 {t}s',fill='white')
    assert metrics[1]['max_arm_edge_stretch_p99'] < metrics[0]['max_arm_edge_stretch_p99']
    for bi in [31,32]:assert metrics[1]['hand_center_distance_to_wrist'][bi] < metrics[0]['hand_center_distance_to_wrist'][bi]
    report[name]=dict(status='PASS',metrics=metrics,alignment=alignment)
    print(name,json.dumps(metrics),flush=True)
sheet.save(OUT/'ht01-before-after.jpg',quality=95)
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
