# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental PMX -> DDR KTMDL exporter using the local Miku template.

Rebuilds geometry, not topology-preserving patching. Retains the reference's
33-bone rig, shader identifiers, texture names, 9 packets and metadata layout.
This narrow template backend deliberately refuses unsupported input layouts.
"""
import _bootstrap  # Local src/ discovery for direct invocation.
from pathlib import Path
import json,struct,sys,shutil,hashlib
import numpy as np
from PIL import Image
from ddr_dancer_exporter.project import PROJECT,DANCER,TEMPLATE,MOTIONS,CAMERA,CONFIG,output_model_dir,require_credits
ROOT=DANCER
sys.path.insert(0,str(PROJECT/'tools'))
import ktmdl
from ddr_dancer_exporter.retarget_arms import retarget

def load(name):return json.loads((ROOT/'analysis'/name).read_text(encoding='utf-8'))
def dds(image,path):
    """Legacy uncompressed A8R8G8B8 DDS with complete mip chain."""
    image=image.convert('RGBA');w,h=image.size;levels=[]
    while True:
        levels.append(image.tobytes('raw','BGRA'))
        if image.size==(1,1):break
        image=image.resize((max(1,image.width//2),max(1,image.height//2)),Image.Resampling.LANCZOS)
    hdr=struct.pack('<7I',124,0x2100F,h,w,w*4,0,len(levels))+bytes(44)
    hdr+=struct.pack('<8I',32,0x41,0,32,0xFF0000,0xFF00,0xFF,0xFF000000)
    hdr+=struct.pack('<5I',0x401008,0,0,0,0)
    assert len(hdr)==124
    path.write_bytes(b'DDS '+hdr+b''.join(levels))

def main():
    credits=require_credits(CONFIG)
    src=load('pmx-inspection.json');geo=load('pmx-geometry.json');mapping=load('rig-comparison.json')
    template=TEMPLATE/'pl_miku00.model';original=template.read_bytes();ref=ktmdl.parse_bytes(original)
    h=ref['header'];assert h['packetCount']==9 and h['boneCount']==33
    palette=ref['packets'][0]['bonePalette']
    assert all(p['bonePalette']==palette and p['vertexDescriptor']['stride']==48 for p in ref['packets'])
    bone_ids={b['name']:b['index'] for b in mapping['ddr_bones']}
    source_to_target={b['source_index']:bone_ids[b['target_candidate']] for b in mapping['mapping'] if b['target_candidate']}
    pos=np.array([v['position'] for v in geo['vertices']],dtype=float)
    # Establish the global height/facing fit before the arm-specific rebind.
    refpos=np.array([v['POSITION'] for p in ref['packets'] for v in p['vertices']])
    scale=float(np.ptp(refpos[:,1])/np.ptp(pos[:,1]))
    origin=np.array(src['origin'] if 'origin' in src else [0,pos[:,1].min(),src['bones'][6]['position'][2]])
    pos=(pos-origin)*scale
    pos[:,2]*=-1  # PMX face points -Z; DDR camera/reference use +Z as front.
    normals=np.array([v['normal'] for v in geo['vertices']])
    normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
    normals[:,2]*=-1
    weights=[];ids=[]
    for v in geo['vertices']:
        merged={}
        for bi,w in v['weights']:
            if w<=0:continue
            target=source_to_target[bi];merged[target]=merged.get(target,0)+w
        pairs=sorted(merged.items(),key=lambda x:-x[1]);assert 1<=len(pairs)<=4
        total=sum(w for _,w in pairs);pairs=[(b,w/total) for b,w in pairs]
        pairs += [(pairs[0][0],0)]*(4-len(pairs))
        ids.append([b for b,w in pairs]);weights.append([w for b,w in pairs])
    ids=np.array(ids);weights=np.array(weights)
    arm_report=None
    if CONFIG.get('arm_retarget',True):
        pos,normals,ids,weights,arm_report=retarget(pos,normals,ids,weights,src,mapping,ref,scale,origin,CONFIG)
        (ROOT/'analysis/arm-retarget.json').write_text(json.dumps(arm_report,indent=2),encoding='utf-8')
    allfaces=np.array(geo['indices'],dtype=np.int64).reshape(-1,3)
    allfaces=allfaces[:,[0,2,1]]  # Preserve winding after the Z reflection.
    assert allfaces.max()<len(pos)
    chunks=[];start=0
    for m in src['materials']:
        n=m['triangles'];faces=allfaces[start:start+n];start+=n
        if n:chunks.append((m,faces))
    if len(chunks)>9:raise ValueError('More than 9 materials: import using the diffuse atlas option first')
    # Fit the fixed metadata table by splitting populated materials, preserving
    # per-material order. The Blender importer can atlas many materials to one.
    while len(chunks)<9:
        split=max(range(len(chunks)),key=lambda i:len(chunks[i][1]))
        material,faces=chunks[split];assert len(faces)>=2
        mid=len(faces)//2;chunks[split:split+1]=[(material,faces[:mid]),(material,faces[mid:])]
    assert len(chunks)==9
    outdir=output_model_dir();outdir.mkdir(parents=True,exist_ok=True)
    data=bytearray(original[:h['streamDataOffset']])
    def pack(off,fmt,*values):struct.pack_into('<'+fmt,data,off,*values)
    def append(blob):
        data.extend(bytes((-len(data))%16));off=len(data);data.extend(blob);return off
    packet_summary=[]
    for pi,(material,faces) in enumerate(chunks):
        p=ref['packets'][pi];vd=p['vertexDescriptor'];ind=p['indexDescriptor']
        unique,local=np.unique(faces.reshape(-1),return_inverse=True)
        assert len(unique)<65536
        vb=bytearray()
        for vi in unique:
            # DDR template stores residual weight in slot 0, explicit weights 1..3.
            blend=[palette.index(int(b)) for b in ids[vi]]
            uv=geo['vertices'][int(vi)]['uv']
            color=[round(min(1,max(0,c))*255) for c in material['diffuse']]
            vb+=struct.pack('<3f4B3f3f2e4B',*pos[vi],*blend,*weights[vi][1:],*normals[vi],*uv,*color)
        vo=append(vb);io=append(local.astype('<u2').tobytes())
        pack(vd['offset'],'iI',vo-vd['offset'],len(unique))
        pack(ind['offset'],'iI',io-ind['offset'],len(local))
        tex=material['texture'];assert 0<=tex<5
        pack(p['offset']+4,'I',tex)
        pack(p['offset']+0x30,'H',tex)
        center=(pos[unique].max(0)+pos[unique].min(0))/2
        radius=float(np.linalg.norm(pos[unique]-center,axis=1).max())
        pack(p['offset']+0x50,'4f',*center,radius)
        packet_summary.append(dict(packet=pi,source_material=material['name'],texture_slot=tex,vertices=len(unique),triangles=len(faces)))
    # Conservative global bounds in bind pose; per-bone bounds are bone-local.
    lo,hi=pos.min(0),pos.max(0)
    for key,count in [('groupOffset',h['groupCount']),('boundingOffset',h['boundingCount'])]:
        for j in range(count):
            off=h[key]+j*48;pack(off+16,'3f',*hi);pack(off+32,'3f',*lo)
    for b in ref['bones']:
        mask=np.any((ids==b['index'])&(weights>0),axis=1)
        if mask.any():
            points=np.c_[pos[mask],np.ones(mask.sum())]@np.array(b['invertMatrix'])
            blo,bhi=points[:,:3].min(0),points[:,:3].max(0)
        else:blo=bhi=np.zeros(3)
        pack(b['offset']+0x90,'3f',*bhi);pack(b['offset']+0xa0,'3f',*blo)
    data.extend(bytes((-len(data))%16));pack(0x74,'I',len(data)-h['streamDataOffset']);pack(0x90,'I',len(data))
    model=outdir/('pl_'+CONFIG['model_id']+'.model');model.write_bytes(data)
    for ext in ('b2it','grp2it'):shutil.copyfile(TEMPLATE/f'pl_miku00.{ext}',outdir/f"pl_{CONFIG['model_id']}.{ext}")
    sourcedir=Path(src['file']).parent
    texture_report=[]
    for i,name in enumerate(ref['names']['textureNames']):
        im=Image.open(sourcedir/src['textures'][i]['path'].replace('\\','/')) if i<len(src['textures']) else Image.new('RGBA',(4,4),'white')
        original_size=im.size
        # Match the reference's modest legacy DDS sizes and avoid NPOT surfaces.
        size=tuple(min(1024,1<<(max(1,d)-1).bit_length()) for d in im.size)
        if im.size!=size:im=im.resize(size,Image.Resampling.LANCZOS)
        dds(im,outdir/name)
        texture_report.append(dict(name=name,original_size=original_size,exported_size=size))
    (outdir.parent/'chara_resources.rlist.txt').write_text(CONFIG['model_id']+', pl, F, A, 0.9, 0.75, 0.0\n',encoding='ascii')
    notes=list((ROOT/'source').rglob('*.txt'))
    if notes:shutil.copyfile(notes[0],outdir.parent/'SOURCE-NOTES.txt')
    (ROOT/'借物表.txt').write_text(credits.strip()+'\n',encoding='utf-8')
    (outdir.parent/'借物表.txt').write_text(credits.strip()+'\n',encoding='utf-8')
    np.savez_compressed(ROOT/'analysis/export-geometry.npz',positions=pos,normals=normals,indices=ids,weights=weights,triangles=allfaces)
    reread=ktmdl.parse_bytes(bytes(data))
    assert sum(len(p['triangles']) for p in reread['packets'])==src['triangles']
    for p in reread['packets']:
        assert max(p['indices'])<len(p['vertices'])
        for v in p['vertices']:
            assert np.isfinite(v['POSITION']).all()
            assert max(v['BLENDINDICES'])<len(p['bonePalette'])
            assert -.000001<=sum(v['BLENDWEIGHT'])<=1.000001
    for b in reread['bones']:
        assert np.allclose(np.array(b['matrix'])@np.array(b['invertMatrix']),np.eye(4),atol=1e-5)
    report=dict(model=str(model),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),scale=scale,source_origin=origin.tolist(),z_reflected=True,textures=texture_report,packets=packet_summary,triangles=src['triangles'],rig='Unchanged Miku bind matrices and bone identifiers; no limb alignment',weight_convention='slot0 residual',validation='Reparsed all packets, checked index ranges, weights, finite coordinates and inverse bind matrices',runtime_status='NOT tested in DDR')
    if arm_report:
        report['rig']='DDR rig retained; source arm/collar rest geometry aligned and twist weights rebuilt'
        report['arm_retarget']=arm_report
    (ROOT/'analysis/export-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
