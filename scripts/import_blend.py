"""Blender rest mesh -> common exporter intermediate. Never saves the blend."""
import sys
from pathlib import Path
import bpy,sys,json
from pathlib import Path
from collections import defaultdict
args=sys.argv[sys.argv.index('--')+1:];name=args[args.index('--dancer')+1]
root=Path(args[args.index('--workdir')+1]) if '--workdir' in args else Path(__file__).resolve().parents[1]/'dancers'/name
config=json.loads((root/'dancer.json').read_text(encoding='utf8'))
if not isinstance(config.get('credits'),str) or not config['credits'].strip():
    raise ValueError('Every converted input requires a non-empty credit / 借物表')
out=root/'analysis';out.mkdir(exist_ok=True)
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
rig.data.pose_position='REST'
objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.visible_get() and not o.hide_render]
direct={'spine':'Hips','spine.001':'Spine','spine.002':'Spine1','spine.003':'Spine2','spine.004':'Neck','spine.005':'Head','spine.006':'Head','下半身':'Hips','腰':'Hips','上半身':'Spine','上半身2':'Spine2','首':'Neck','頭':'Head'}
for side,prefix in [('L','Left'),('R','Right')]:
    for source,target in {'shoulder':'Collar','upper_arm':'Arm','forearm':'ForeArm','hand':'Hand','thigh':'UpLeg','shin':'Leg','foot':'Foot','toe':'ToeBase','肩':'Collar','腕':'Arm','腕捩':'Arm','ひじ':'ForeArm','手捩':'ForeArm','手首':'Hand','足':'UpLeg','ひざ':'Leg','足首':'Foot','足首先':'ToeBase','足先EX':'ToeBase'}.items(): direct[source+'.'+side]=prefix+target
def target(b):
    for side,prefix in [('L','Left'),('R','Right')]:
        if b.name.startswith('腕捩.'+side):return prefix+'ArmRoll'
        if b.name=='手捩.'+side or b.name=='ひじ.'+side+'.003':return prefix+'ForeArmRoll'
    if b.name in direct:return direct[b.name]
    return target(b.parent) if b.parent else 'Hips'
targets=sorted(set(target(b) for b in rig.data.bones));indices={n:i for i,n in enumerate(targets)}
source_map={b.name:target(b) for b in rig.data.bones}
textures=[];texkeys={};materials=[];faces=defaultdict(list);vertices=[];counts=defaultdict(int);warnings=[]
def texture(mat):
    images=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if mat and mat.use_nodes else []
    images=[i for i in images if not any(t in i.name.lower() for t in ['shadow','highli','normal'])]
    im=images[0] if images else None
    key=im.name if im else 'white'
    if key not in texkeys:
        idx=len(textures);texkeys[key]=idx;path=out/f'diffuse-{idx}.png'
        if im:
            stem=Path(im.filepath.replace('\\','/')).name
            candidates=[p for p in (root/'source').rglob('*') if p.is_file() and (p.name==stem or p.stem==Path(im.name).stem or (key=='facial.png' and p.name=='ano_facial.png'))]
            if candidates:im=bpy.data.images.load(str(candidates[0]),check_existing=False)
            if not len(im.pixels):raise ValueError('Missing image '+key)
            im.save_render(str(path))
        else:
            im=bpy.data.images.new('export_white',width=4,height=4);im.generated_color=(1,1,1,1);im.save_render(str(path))
        textures.append(dict(path=path.name,exists=True))
        materials.append(dict(index=idx,name=key,diffuse=[1,1,1,1],texture=idx,triangles=0))
    return texkeys[key]
for o in objects:
    for mod in o.modifiers:
        mod.show_viewport=mod.type in {'MIRROR','SUBSURF','SOLIDIFY'} and 'OUTLINE' not in mod.name.upper()
        if mod.type=='SUBSURF':mod.levels=min(mod.levels,1)
bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
for o in objects:
    ev=o.evaluated_get(deps);mesh=ev.to_mesh(preserve_all_data_layers=True,depsgraph=deps);mesh.calc_loop_triangles()
    normalmat=o.matrix_world.to_3x3().inverted().transposed();uvs=mesh.uv_layers.active
    if not uvs:raise ValueError('Missing UVs '+o.name)
    groupnames={g.index:g.name for g in o.vertex_groups};cache={}
    for tri in mesh.loop_triangles:
        mat=mesh.materials[tri.material_index] if mesh.materials else None
        if mat and 'Outline' in mat.name:continue
        ti=texture(mat);face=[]
        for li in tri.loops:
            loop=mesh.loops[li];v=mesh.vertices[loop.vertex_index];uv=uvs.data[li].uv
            key=(v.index,round(uv.x,7),round(uv.y,7))
            if key not in cache:
                p=o.matrix_world@v.co;n=(normalmat@v.normal).normalized();weights=defaultdict(float)
                for g in v.groups:
                    gn=groupnames.get(g.group)
                    if gn in source_map:weights[indices[source_map[gn]]]+=g.weight
                if not weights:weights[indices['Hips']]=1
                pairs=sorted(weights.items(),key=lambda w:-w[1])[:4];total=sum(w for _,w in pairs)
                if total<=0:pairs=[(indices['Hips'],1)];total=1
                pairs=[(i,w/total) for i,w in pairs if w>0]
                for i,w in pairs:counts[i]+=1
                cache[key]=len(vertices);vertices.append(dict(position=[p.x,p.z,p.y],normal=[n.x,n.z,n.y],uv=[uv.x,1-uv.y],weights=pairs))
            face.append(cache[key])
        faces[ti].extend([face[0],face[2],face[1]])
    ev.to_mesh_clear()
for m in materials:m['triangles']=len(faces[m['index']])//3
assert len(textures)<=5
positions=[v['position'] for v in vertices];lo=[min(p[i] for p in positions) for i in range(3)];hi=[max(p[i] for p in positions) for i in range(3)]
report=dict(file=str(out/'intermediate.blend'),input_format='blend',source_file=bpy.data.filepath,vertices=len(vertices),triangles=sum(m['triangles'] for m in materials),origin=[0,lo[1],0],bounds=dict(min=lo,max=hi),textures=textures,materials=materials,bones=[dict(index=i,name=n,position=[0,0,0],parent=-1,weighted_vertices=counts[i]) for i,n in enumerate(targets)],morphs=[],remaining_bytes=0,limitations=['Base color textures only; Blender shader nodes omitted','Cloth, rigid bodies, facial morphs and hair physics omitted','Source skin weights mapped semantically; no anatomical alignment'],objects=[o.name for o in objects])
report['arm_bind']={}
for side,prefix in [('L','Left'),('R','Right')]:
    for candidates,part in [(['肩','shoulder'],'Collar'),(['腕','upper_arm'],'Arm'),(['ひじ','forearm'],'ForeArm'),(['手首','hand'],'Hand')]:
        bone=next((rig.data.bones.get(n+'.'+side) for n in candidates if rig.data.bones.get(n+'.'+side)),None)
        if bone is None:continue
        head=rig.matrix_world@bone.head_local;tail=rig.matrix_world@bone.tail_local
        report['arm_bind'][prefix+part]=dict(head=[head.x,head.z,head.y],tail=[tail.x,tail.z,tail.y])
(out/'pmx-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
(out/'pmx-geometry.json').write_text(json.dumps(dict(vertices=vertices,indices=[i for m in materials for i in faces[m['index']]])),encoding='utf8')
(root/'bone-map.json').write_text(json.dumps({n:n for n in targets}),encoding='utf8')
(out/'source-bone-map.json').write_text(json.dumps(source_map,ensure_ascii=False,indent=2),encoding='utf8')
print('IMPORTED',name,len(vertices),'vertices',report['triangles'],'triangles',len(textures),'textures')
