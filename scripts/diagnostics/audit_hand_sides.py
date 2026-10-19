"""Audit actual KTMDL palette-resolved weights and HT01 bone transforms."""
import _bootstrap  # Local src/ discovery for direct invocation.
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from ddr_dancer_exporter.rendering import load_model,frame,read_motion,pose
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'analysis/arm-bind-diagnosis'
def read(path):return json.loads(path.read_text(encoding='utf8'))
motion=read_motion(ROOT/'animations/motions/mc_female_ht01_exec.anm')
ref=load_model(ROOT/'dancers/template-miku/model','pl_miku00.model')
report={};ano=None
for name in ['ano','nailong','adelie-tomorin','template-miku','stock-emi']:
    root=ROOT/'dancers'/name;c=read(root/'dancer.json')
    directory=root/'model' if name in ['template-miku','stock-emi'] else root/'output'/c['package_name']/('pl_'+c['model_id'])
    filename='pl_emi00.model' if name=='stock-emi' else 'pl_'+c['model_id']+'.model'
    a=ref if name=='template-miku' else load_model(directory,filename)
    if name=='ano':ano=a
    rows=[]
    for label,bi,sign in [('LeftArm',17,1),('RightArm',18,-1),('LeftForeArm',25,1),('RightForeArm',26,-1),('LeftHand',31,1),('RightHand',32,-1)]:
        w=np.sum(a['weights']*(a['ids']==bi),axis=1)
        # Ignore only float round-off residuals, not genuine low-weight vertices.
        mask=w>1e-6;p=a['pos'][mask];ww=w[mask]
        wrong=float(ww[p[:,0]*sign<0].sum()/ww.sum())
        rows.append(dict(bone=label,index=bi,weighted_vertices=int(mask.sum()),wrong_side_weight_fraction=wrong,centroid=np.average(p,axis=0,weights=ww).tolist(),x_range=[float(p[:,0].min()),float(p[:,0].max())]))
        assert wrong<1e-5,(name,label,wrong)
    bind=np.array([b['matrix'] for b in a['model']['bones']]);reference_bind=np.array([b['matrix'] for b in ref['model']['bones']])
    diff=float(np.abs(bind-reference_bind).max())
    sampled={str(t):float(np.abs(pose(a['model'],motion,t*60)-pose(ref['model'],motion,t*60)).max()) for t in [0,4,8,12,16,19]}
    if name!='stock-emi':assert diff<1e-6 and max(sampled.values())<1e-6
    print(name,'bind delta',diff,'motion delta',max(sampled.values()),flush=True)
    assert [b['parentNo'] for b in a['model']['bones']]==[n['parentIndex'] for n in motion['hierarchy']['nodes']]
    report[name]=dict(sides=rows,max_bind_difference_from_miku=diff,max_ht01_transform_differences=sampled)
    print(name,'PASS: no material opposite-side arm/hand weights; same HT01 bone transforms as Miku',flush=True)
# Counterfactual: swap the entire arm chains, including collars and twist joints.
swapped_ids=ano['ids'].copy()
for left,right in [(12,13),(17,18),(21,22),(25,26),(29,30),(31,32)]:
    swapped_ids[ano['ids']==left]=right;swapped_ids[ano['ids']==right]=left
swapped={**ano,'ids':swapped_ids}
sheet=Image.new('RGB',(1200,800));draw=ImageDraw.Draw(sheet)
for row,t in enumerate([0,16]):
    for col,(label,asset) in enumerate([('Original Miku',ref),('Ano current mapping',ano),('Ano deliberately swapped',swapped)]):
        pic=Image.fromarray(frame(asset,motion,t*60,800)).crop((150,130,650,630)).resize((400,400))
        sheet.paste(pic,(col*400,row*400));draw.text((col*400+8,row*400+8),f'{label} | HT01 {t}s',fill='white')
sheet.save(OUT/'ht01-side-swap-test.jpg',quality=95)
(OUT/'hand-side-audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
