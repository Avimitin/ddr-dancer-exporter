"""Read source joint locations and weighted group use, without saving the blend."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # Blender does not add the script directory to sys.path.
import bpy,json,sys
from pathlib import Path
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
dancer=args[args.index('--dancer')+1] if '--dancer' in args else 'ano'
root=Path(__file__).resolve().parents[2]/'dancers'/dancer/'analysis'
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
counts={};weighted={};orphans={}
for o in bpy.context.scene.objects:
    if o.type!='MESH' or not o.visible_get() or o.hide_render:continue
    for v in o.data.vertices:
        for g in v.groups:
            if g.weight<=0:continue
            if g.group>=len(o.vertex_groups):
                orphans[o.name]=orphans.get(o.name,0)+1
                continue
            name=o.vertex_groups[g.group].name
            counts[name]=counts.get(name,0)+1
            weighted[name]=weighted.get(name,0)+g.weight
report=dict(orphan_group_entries=orphans,joints={b.name:dict(head=list(rig.matrix_world@b.head_local),tail=list(rig.matrix_world@b.tail_local),parent=b.parent.name if b.parent else None,weighted_vertices=counts.get(b.name,0),weight_sum=weighted.get(b.name,0)) for b in rig.data.bones})
(root/'source-hand-joints.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('Saved source-hand-joints.json')
