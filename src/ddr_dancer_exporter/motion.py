# SPDX-License-Identifier: GPL-3.0-or-later
"""CPU skinning and textured software previews from exported KTMDL + DDR ANM.
Offline validation, not a claim to reproduce the game's renderer exactly.
"""
from pathlib import Path
import sys,json,struct,math
import numpy as np
from PIL import Image,ImageDraw
from ddr_dancer_exporter.project import PROJECT,DANCER,TEMPLATE,MOTIONS,CAMERA,CONFIG,output_model_dir
ROOT=DANCER;sys.path.insert(0,str(PROJECT/'tools'))
import ktmdl,anm
PREVIEW=ROOT/'preview';PREVIEW.mkdir(exist_ok=True)

def quat(q):
    x,y,z,w=np.asarray(q)/np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]).T

def read_motion(path):
    r=anm.parse_file(str(path));b=path.read_bytes()
    for t in r['animation']['tracks']:
        if t['curveType']==30: # DDR half-float XYZ translation, no float base.
            off=t['absoluteOffset']+t['valueOffset']
            t['values']=[struct.unpack_from('<3e',b,off+i*6) for i in range(t['sampleCount'])]
            t['valueKind']='TRANSLATION_HALF3'
        if not t['values']:raise ValueError(f"Unsupported track {t['curveType']}")
    return r

def sample(t,frame):
    values=t['values'];keys=t['keyFrames']
    if len(values)==1:return values[0]
    keys=keys if keys else range(len(values))
    j=max(0,min(len(keys)-2,int(np.searchsorted(keys,frame)-1)))
    a,b=np.array(values[j]),np.array(values[j+1])
    f=np.clip((frame-keys[j])/max(1,keys[j+1]-keys[j]),0,1)
    if len(a)==4 and a@b<0:b=-b
    v=a*(1-f)+b*f
    if len(v)==4:v/=np.linalg.norm(v)
    return v

def pose(model,motion,frame):
    rest=np.array([b['matrix'] for b in model['bones']]);parents=[b['parentNo'] for b in model['bones']]
    local=np.array([rest[i]@np.linalg.inv(rest[p]) if p>=0 else rest[i] for i,p in enumerate(parents)])
    for t in motion['animation']['tracks']:
        i=t['nodeIndex'];v=sample(t,frame)
        if t['curveType']==28:local[i,:3,:3]=quat(v)
        else:local[i,3,:3]=v
    world=np.zeros_like(local)
    for i,p in enumerate(parents):world[i]=local[i]@world[p] if p>=0 else local[i]
    return world

def geometry(model):
    positions=[];normals=[];uvs=[];ids=[];weights=[];faces=[];texids=[];base=0
    for p in model['packets']:
        for v in p['vertices']:
            positions.append(v['POSITION']);normals.append(v['NORMAL'])
            uvs.append(struct.unpack('<2e',bytes.fromhex(v['TEXCOORD0']['rawHex'])))
            ids.append([p['bonePalette'][i] for i in v.get('BLENDINDICES',[0,0,0,0])])
            w=v.get('BLENDWEIGHT',[0,0,0]);weights.append([1-sum(w),*w])
        binding=p['tex'][0]['id']
        texture=model['textureTypes'][binding]['textureIndex']
        faces.extend([[i+base for i in f] for f in p['triangles']]);texids.extend([texture]*len(p['triangles']));base+=len(p['vertices'])
    return tuple(np.array(x) for x in (positions,normals,uvs,ids,weights,faces,texids))

def skin(pos,ids,weights,inv,world):
    matrices=inv@world
    hp=np.c_[pos,np.ones(len(pos))]
    result=np.zeros((len(pos),4))
    for k in range(4):result+=np.einsum('ni,nij->nj',hp,matrices[ids[:,k]])*weights[:,k,None]
    return result[:,:3]

def render(pos,uvs,faces,texids,textures,size=420,label='',camera=None):
    # Fixed front view, or an explicitly labelled camera-track approximation.
    if camera is None:
        projected=np.c_[size/2+pos[:,0]*size/2.7,size*.84-pos[:,1]*size/2.7]
        depth=-pos[:,2]
    else:
        rotation,translation,fov,aspect=camera
        p=(pos-translation)@rotation.T
        distance=-p[:,2];distance=np.maximum(distance,.01)
        focal=(size/2)/math.tan(math.radians(fov)/2)
        projected=np.c_[size/2+p[:,0]*focal/distance/aspect,size/2-p[:,1]*focal/distance]
        depth=distance
    canvas=np.zeros((size,size,3),dtype=np.uint8);canvas[:]=[27,32,44]
    zbuffer=np.full((size,size),np.inf)
    # Opaque/alpha-tested approximation; enough to inspect deformation, UVs and gaps.
    for face,ti in zip(faces,texids):
        xy=projected[face];x0=max(0,int(np.floor(xy[:,0].min())));x1=min(size-1,int(np.ceil(xy[:,0].max())))
        y0=max(0,int(np.floor(xy[:,1].min())));y1=min(size-1,int(np.ceil(xy[:,1].max())))
        if x1<x0 or y1<y0:continue
        a,b,c=xy;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-8:continue
        yy,xx=np.mgrid[y0:y1+1,x0:x1+1];xx=xx+.5;yy=yy+.5
        w0=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
        w1=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w2=1-w0-w1
        z=w0*depth[face[0]]+w1*depth[face[1]]+w2*depth[face[2]]
        destz=zbuffer[y0:y1+1,x0:x1+1];mask=(w0>=0)&(w1>=0)&(w2>=0)&(z<destz)
        if not mask.any():continue
        uv=w0[...,None]*uvs[face[0]]+w1[...,None]*uvs[face[1]]+w2[...,None]*uvs[face[2]]
        tex=textures[ti];tx=np.clip((uv[:,:,0]*tex.shape[1]).astype(int),0,tex.shape[1]-1);ty=np.clip((uv[:,:,1]*tex.shape[0]).astype(int),0,tex.shape[0]-1)
        rgba=tex[ty,tx];mask&=rgba[:,:,3]>100
        normal=np.cross(pos[face[1]]-pos[face[0]],pos[face[2]]-pos[face[0]])
        shade=.68+.32*abs(normal@np.array([.3,.5,.8]))/max(np.linalg.norm(normal),1e-10)
        rgb=np.clip(rgba[:,:,:3]*shade,0,255).astype(np.uint8)
        canvas[y0:y1+1,x0:x1+1][mask]=rgb[mask];destz[mask]=z[mask]
    image=Image.fromarray(canvas);draw=ImageDraw.Draw(image);draw.text((10,10),label,fill='white')
    return image

def read_camera():
    b=(CAMERA).read_bytes();base=24;tracks=[]
    for off in struct.unpack_from('<6I',b,32):
        at=base+off;kind,mode,n,node,key,val=struct.unpack_from('<4H2I',b,at)
        width=4 if kind in (1,4) else 1
        values=[struct.unpack_from('<'+str(width)+'f',b,at+val+i*width*4) for i in range(n)]
        tracks.append(dict(type=kind,mode=mode,count=n,values=values))
    report=dict(last_sample=struct.unpack_from('<I',b,4)[0],rate_field=struct.unpack_from('<I',b,8)[0],tracks=[dict(type=t['type'],count=t['count'],first=t['values'][0],last=t['values'][-1]) for t in tracks],interpretation='Camera quaternion, position float4, likely FOV/near/far/aspect; position scaled 0.01 for preview (inferred).')
    (ROOT/'analysis/camera-inspection.json').write_text(json.dumps(report,indent=2))
    return tracks

def main():
    directory=output_model_dir();model=ktmdl.parse_file(str(directory/('pl_'+CONFIG['model_id']+'.model')))
    pos,norm,uv,ids,weights,faces,texids=geometry(model)
    inv=np.array([b['invertMatrix'] for b in model['bones']]);rest=np.array([b['matrix'] for b in model['bones']])
    error=float(np.abs(skin(pos,ids,weights,inv,rest)-pos).max());assert error<1e-5
    textures=[np.array(Image.open(directory/name).convert('RGBA')) for name in model['names']['textureNames']]
    render(pos,uv,faces,texids,textures,label='Exported KTMDL - bind pose').save(PREVIEW/'bind-pose.png')
    camera=read_camera();results=[]
    edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
    lengths=np.linalg.norm(pos[edges[:,0]]-pos[edges[:,1]],axis=1);valid=lengths>.001
    allparents=[b['parentNo'] for b in model['bones']]
    for path in sorted((MOTIONS).glob('*.anm')):
        motion=read_motion(path)
        assert [n['parentIndex'] for n in motion['hierarchy']['nodes']]==allparents
        end=motion['header']['lastSampleIndex'];maxradius=0;maxedge=0;minfloor=1e9;worst=0;maxp99=0
        for frame in np.linspace(0,end,65):
            animated=skin(pos,ids,weights,inv,pose(model,motion,frame));assert np.isfinite(animated).all()
            radius=float(np.linalg.norm(animated-animated.mean(0),axis=1).max())
            ratio=np.linalg.norm(animated[edges[:,0]]-animated[edges[:,1]],axis=1)[valid]/lengths[valid]
            if radius>maxradius:maxradius=radius;worst=float(frame)
            maxedge=max(maxedge,float(ratio.max()));maxp99=max(maxp99,float(np.percentile(ratio,99)));minfloor=min(minfloor,float(animated[:,1].min()))
        results.append(dict(clip=path.name,last_sample=end,poses_checked=65,finite=True,max_radius=maxradius,max_edge_stretch=maxedge,max_p99_edge_stretch=maxp99,min_y=minfloor,worst_radius_sample=worst))
        print(path.name,'radius',round(maxradius,3),'p99 stretch',round(maxp99,2),flush=True)
    selected=read_motion(MOTIONS/'mc_female_sf02_exec.anm')
    frames=[];camera_frames=[];contact=[]
    for i,frame in enumerate(np.linspace(0,450,16)):
        animated=skin(pos,ids,weights,inv,pose(model,selected,frame))
        frames.append(render(animated,uv,faces,texids,textures,size=320,label=f'DDR sf02 | sample {frame:.0f}'))
        ci=int(frame);q=camera[0]['values'][ci];xyz=np.array(camera[1]['values'][ci][:3])*.01
        cam=(quat(q),xyz,camera[2]['values'][0][0],camera[5]['values'][0][0])
        camera_frames.append(render(animated,uv,faces,texids,textures,size=320,label='DDR camera | inferred units',camera=cam))
        if i%3==0:contact.append(frames[-1])
        print('Rendered preview',i+1,'/ 16',flush=True)
    frames[0].save(PREVIEW/'ddr-dance.gif',save_all=True,append_images=frames[1:],duration=500,loop=0)
    camera_frames[0].save(PREVIEW/'ddr-camera.gif',save_all=True,append_images=camera_frames[1:],duration=500,loop=0)
    camera_frames[8].save(PREVIEW/'camera-sample.png')
    sheet=Image.new('RGB',(960,640))
    for i,im in enumerate(contact):sheet.paste(im,((i%3)*320,(i//3)*320))
    sheet.save(PREVIEW/'dance-contact-sheet.png')
    (ROOT/'analysis/animation-validation.json').write_text(json.dumps(dict(bind_pose_max_error=error,clips=results,limitations=['Offline CPU skinning, not the DDR runtime','Camera units and FOV semantics inferred','GIF playback assumes 60 samples per second','Software renderer uses alpha testing and two-sided rasterization']),indent=2))
    print('Saved previews and motion validation.',flush=True)

if __name__=='__main__':main()
