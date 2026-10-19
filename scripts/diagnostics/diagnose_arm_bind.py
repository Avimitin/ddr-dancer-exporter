"""Read-only diagnosis; counterfactual arm alignment never replaces exports."""
import _bootstrap  # Local src/ discovery for direct invocation.
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from ddr_dancer_exporter.rendering import load_model,frame,read_motion
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'analysis/arm-bind-diagnosis';OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf8'))
def align(a,b):
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b);v=np.cross(a,b);c=a@b
    k=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return (np.eye(3)+k+k@k/(1+c)).T
motion=read_motion(ROOT/'animations/motions/mc_female_ht01_exec.anm')
report={};sheet=Image.new('RGB',(1600,1200));draw=ImageDraw.Draw(sheet)
for row,name in enumerate(['ano','nailong','adelie-tomorin']):
    root=ROOT/'dancers'/name;cfg=read(root/'dancer.json');exp=read(root/'analysis/export-report.json')
    asset=load_model(root/'output'/cfg['package_name']/('pl_'+cfg['model_id']),'pl_'+cfg['model_id']+'.model')
    ids={b['name']:b['index'] for b in read(root/'analysis/rig-comparison.json')['ddr_bones']}
    rest=np.array([b['matrix'] for b in asset['model']['bones']]);anchors={};tails={}
    if name=='adelie-tomorin':
        source={b['name']:b['position'] for b in read(root/'analysis/pmx-inspection.json')['bones']}
        for side,prefix in [('左','Left'),('右','Right')]:
            for s,t in [('腕','Arm'),('ひじ','ForeArm'),('手首','Hand')]:anchors[prefix+t]=np.array(source[side+s])
    else:
        source=read(root/'analysis/source-hand-joints.json')['joints']
        for side,prefix in [('L','Left'),('R','Right')]:
            for s,t in ([('腕','Arm'),('ひじ','ForeArm'),('手首','Hand')] if name=='ano' else [('upper_arm','Arm'),('forearm','ForeArm'),('hand','Hand')]):
                b=source[s+'.'+side];anchors[prefix+t]=np.array(b['head'])[[0,2,1]];tails[prefix+t]=np.array(b['tail'])[[0,2,1]]
    for dic in (anchors,tails):
        for key,value in dic.items():dic[key]=(value-np.array(exp['source_origin']))*exp['scale']*np.array([1,1,-1])
    corrections={};rows=[]
    for prefix in ['Left','Right']:
        for part,nextpart in [('Arm','ForeArm'),('ForeArm','Hand'),('Hand',None)]:
            key=prefix+part;src=anchors[key];dest=rest[ids[key],3,:3]
            if nextpart:
                a=anchors[prefix+nextpart]-src;b=rest[ids[prefix+nextpart],3,:3]-dest
                scale=np.linalg.norm(b)/np.linalg.norm(a)
            else:
                a=tails[key]-src if key in tails else src-anchors[prefix+'ForeArm']
                b=rest[ids[key],3,:3]-rest[ids[prefix+'ForeArm'],3,:3];scale=1
            rot=align(a,b)*scale;corrections[ids[key]]=(src,dest,rot)
            rows.append(dict(bone=key,source_joint=src.tolist(),ddr_joint=dest.tolist(),pivot_error=float(np.linalg.norm(src-dest)),direction_difference_degrees=float(np.degrees(np.arccos(np.clip(a@b/np.linalg.norm(a)/np.linalg.norm(b),-1,1))))))
    corrected=np.zeros_like(asset['pos'])
    for k in range(4):
        moved=asset['pos'].copy()
        for bi,(src,dest,rot) in corrections.items():
            mask=asset['ids'][:,k]==bi;moved[mask]=(moved[mask]-src)@rot+dest
        corrected+=moved*asset['weights'][:,k,None]
    variant={**asset,'pos':corrected}
    # Identical motion, weights, shader, camera. Only rest geometry is adjusted.
    for col,(label,a,sec) in enumerate([('Original',asset,0),('Arm alignment experiment',variant,0),('Original',asset,16),('Arm alignment experiment',variant,16)]):
        pic=Image.fromarray(frame(a,motion,sec*60,800)).crop((150,130,650,630)).resize((400,400))
        sheet.paste(pic,(col*400,row*400));draw.text((col*400+8,row*400+8),f'{name} | {label} | {sec}s',fill='white')
    report[name]=rows
sheet.save(OUT/'ht01-before-after.jpg',quality=95)
(OUT/'joint-mismatch.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({n:[{'bone':r['bone'],'pivot_error':round(r['pivot_error'],4),'angle':round(r['direction_difference_degrees'],1)} for r in rows] for n,rows in report.items()},indent=2))
