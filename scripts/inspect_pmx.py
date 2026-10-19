"""Read-only PMX 2.0/2.1 structural inspection; no third-party modules."""
import _bootstrap  # Local src/ discovery for direct invocation.
import struct, json, pathlib, collections, hashlib

from ddr_dancer_exporter.project import PROJECT,DANCER,TEMPLATE,MOTIONS,CAMERA,CONFIG,output_model_dir
ROOT = DANCER
path = next((ROOT / 'source').rglob('*.pmx'))
data = path.read_bytes()
pos = 0
def read(fmt):
    global pos
    vals = struct.unpack_from('<' + fmt, data, pos)
    pos += struct.calcsize('<' + fmt)
    return vals[0] if len(vals) == 1 else vals
def skip(n):
    global pos
    pos += n
    assert pos <= len(data)
assert read('4s') == b'PMX '
version = read('f')
settings = read(str(read('B')) + 'B')
encoding = 'utf-16-le' if settings[0] == 0 else 'utf-8'
def txt():
    return read(str(read('i')) + 's').decode(encoding)
def idx(kind):
    size = settings[{'vertex':2,'texture':3,'material':4,'bone':5,'morph':6,'rigid':7}[kind]]
    return read({1:'B',2:'H',4:'I'}[size] if kind == 'vertex' else {1:'b',2:'h',4:'i'}[size])
names = [txt() for _ in range(4)]
vertices = read('i'); bounds = [[float('inf')]*3, [float('-inf')]*3]
deforms = collections.Counter(); weighted = collections.Counter(); positions=[]; geometry=[]
for _ in range(vertices):
    xyz = read('3f'); positions.append(xyz)
    for j in range(3):
        bounds[0][j] = min(bounds[0][j], xyz[j]); bounds[1][j] = max(bounds[1][j], xyz[j])
    normal=read('3f'); uv=read('2f'); skip(settings[1]*16)
    deform = read('B'); deforms[deform] += 1
    if deform == 0: pairs=[(idx('bone'),1)]
    elif deform in (1,3):
        a,b=idx('bone'),idx('bone'); w=read('f'); pairs=[(a,w),(b,1-w)]
        if deform == 3: skip(36)
    elif deform in (2,4):
        ids=[idx('bone') for _ in range(4)]; ws=read('4f'); pairs=list(zip(ids,ws))
    else: raise ValueError(deform)
    for bone,w in pairs:
        if w > 0: weighted[bone]+=1
    geometry.append(dict(position=xyz,normal=normal,uv=uv,weights=pairs))
    skip(4)
index_count=read('i'); indices=[idx('vertex') for _ in range(index_count)]
textures=[txt() for _ in range(read('i'))]
materials=[]
for i in range(read('i')):
    name,en=txt(),txt(); diffuse=read('4f'); skip(12+4+12); flags=read('B'); skip(20)
    tex,sphere=idx('texture'),idx('texture'); sphere_mode=read('B'); shared=read('B')
    toon=read('B') if shared else idx('texture'); memo=txt(); count=read('i')
    materials.append(dict(index=i,name=name,english=en,diffuse=diffuse,flags=flags,texture=tex,sphere=sphere,sphere_mode=sphere_mode,toon_shared=shared,toon=toon,memo=memo,triangles=count//3))
bones=[]
for i in range(read('i')):
    name,en=txt(),txt(); xyz=read('3f'); parent=idx('bone'); layer=read('i'); flags=read('H')
    tail=idx('bone') if flags&1 else read('3f')
    if flags&0x300: idx('bone'); skip(4)
    if flags&0x400: skip(12)
    if flags&0x800: skip(24)
    if flags&0x2000: skip(4)
    ik=None
    if flags&0x20:
        target=idx('bone'); loops=read('i'); angle=read('f'); links=[]
        for _ in range(read('i')):
            link=idx('bone'); limited=read('B'); limits=read('6f') if limited else None
            links.append(dict(bone=link,limits=limits))
        ik=dict(target=target,loops=loops,angle=angle,links=links)
    bones.append(dict(index=i,name=name,english=en,position=xyz,parent=parent,flags=flags,weighted_vertices=weighted[i],ik=ik))
morphs=[]
for i in range(read('i')):
    name,en=txt(),txt(); panel=read('B'); kind=read('B'); count=read('i')
    sizes={0:settings[6]+4,1:settings[2]+12,2:settings[5]+28,3:settings[2]+16,4:settings[2]+16,5:settings[2]+16,6:settings[2]+16,7:settings[2]+16,8:settings[4]+113,9:settings[6]+4,10:settings[7]+25}
    skip(count*sizes[kind]); morphs.append(dict(name=name,english=en,type=kind,entries=count))
frames=read('i')
for _ in range(frames):
    txt();txt();skip(1)
    for _ in range(read('i')): idx('morph' if read('B') else 'bone')
rigids=[]
for _ in range(read('i')):
    name,en=txt(),txt(); bone=idx('bone'); skip(1+2+1+36+20); mode=read('B');rigids.append(dict(name=name,bone=bone,mode=mode))
joints=[]
for _ in range(read('i')):
    name,en=txt(),txt(); kind=read('B'); a,b=idx('rigid'),idx('rigid');skip(96);joints.append(dict(name=name,type=kind,a=a,b=b))
report=dict(file=str(path),sha256=hashlib.sha256(data).hexdigest(),version=version,names=names,vertices=vertices,triangles=index_count//3,bounds=bounds,deforms=dict(deforms),textures=[dict(path=t,exists=(path.parent/t.replace('\\','/')).is_file()) for t in textures],materials=materials,bones=bones,morphs=morphs,display_frames=frames,rigid_bodies=rigids,joints=joints,parsed_bytes=pos,total_bytes=len(data),remaining_bytes=len(data)-pos)
(ROOT/'analysis'/'pmx-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'analysis'/'pmx-geometry.json').write_text(json.dumps(dict(vertices=geometry,indices=indices)),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('version','names','vertices','triangles','bounds','deforms','textures','parsed_bytes','total_bytes','remaining_bytes')},ensure_ascii=True,indent=2))
print('Materials:',len(materials),'Bones:',len(bones),'Morphs:',len(morphs),'Rigid bodies:',len(rigids),'Joints:',len(joints))
for b in bones: print(b['index'],ascii(b['name']),ascii(b['english']),b['weighted_vertices'],'IK' if b['ik'] else '',b['position'])
