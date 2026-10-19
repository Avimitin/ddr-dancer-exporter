"""Run inside Blender with --disable-autoexec; inspect without saving the source."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # Blender does not add the script directory to sys.path.
import bpy,json,sys
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:];dancer=args[args.index('--dancer')+1]
root=Path(__file__).resolve().parents[1]/'dancers'/dancer
def custom(obj):
    return {k:str(obj[k])[:3000] for k in obj.keys() if k!='_RNA_UI'}
objects=[]
for o in bpy.data.objects:
    row=dict(name=o.name,type=o.type,hide_render=o.hide_render,hide_viewport=o.hide_viewport,visible=o.visible_get(),parent=o.parent.name if o.parent else None,location=list(o.location),scale=list(o.scale),dimensions=list(o.dimensions),custom=custom(o))
    if o.type=='MESH':
        row.update(vertices=len(o.data.vertices),polygons=len(o.data.polygons),materials=[m.name if m else None for m in o.data.materials],groups=[g.name for g in o.vertex_groups],modifiers=[dict(name=m.name,type=m.type,show_render=m.show_render,show_viewport=m.show_viewport) for m in o.modifiers])
    if o.type=='ARMATURE':
        row['bones']=[dict(name=b.name,parent=b.parent.name if b.parent else None,head=list(b.head_local),tail=list(b.tail_local),deform=b.use_deform) for b in o.data.bones]
    objects.append(row)
materials=[]
for m in bpy.data.materials:
    nodes=[]
    if m.use_nodes:
        for n in m.node_tree.nodes:
            nodes.append(dict(name=n.name,type=n.type,image=n.image.name if n.type=='TEX_IMAGE' and n.image else None,inputs={s.name:str(s.default_value) for s in n.inputs if hasattr(s,'default_value')},links=[dict(input=l.to_socket.name,source=l.from_node.name,output=l.from_socket.name) for s in n.inputs for l in s.links]))
    materials.append(dict(name=m.name,color=list(m.diffuse_color),nodes=nodes))
report=dict(file=bpy.data.filepath,blender=bpy.app.version_string,objects=objects,materials=materials,images=[dict(name=i.name,path=i.filepath,size=list(i.size),packed=bool(i.packed_file)) for i in bpy.data.images],texts=[dict(name=t.name,text=t.as_string()) for t in bpy.data.texts],scene_custom=custom(bpy.context.scene))
(root/'analysis/blend-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('INSPECTED',dancer,'objects',len(objects),'materials',len(materials),'texts',len(report['texts']))
