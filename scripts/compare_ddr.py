"""Inspect copied DDR lookup tables and generate a provisional rig mapping."""
import _bootstrap  # Local src/ discovery for direct invocation.
import json, struct, pathlib, hashlib
from ddr_dancer_exporter.project import PROJECT,DANCER,TEMPLATE
root=DANCER
pmx=json.loads((root/'analysis/pmx-inspection.json').read_text(encoding='utf-8'))
def table(path):
    b=path.read_bytes()
    assert b[:4]==b'B2IT'
    count,offset,ids=struct.unpack_from('<3I',b,16)
    out=[]
    for i in range(count):
        p=struct.unpack_from('<I',b,offset+4*i)[0]
        name=b[p:b.index(0,p)].decode('ascii')
        out.append(dict(name=name,index=struct.unpack_from('<I',b,ids+4*i)[0]))
    return out
bones=table(TEMPLATE/'pl_miku00.b2it')
groups=table(TEMPLATE/'pl_miku00.grp2it')
assert len(bones)==33
assert sum(m['triangles'] for m in pmx['materials'])==pmx['triangles']
assert pmx['remaining_bytes']==0
assert all(t['exists'] for t in pmx['textures'])
mapping=json.loads((root/'bone-map.json').read_text(encoding='utf-8'))
rows=[]
for b in pmx['bones']:
    target=mapping.get(b['name'])
    if target: assert target in {x['name'] for x in bones}
    rows.append(dict(source_index=b['index'],source_name=b['name'],target_candidate=target,weighted_vertices=b['weighted_vertices'],note='Provisional semantic mapping only; rest poses and weights must be rebuilt. Unweighted controls may be omitted.'))
assert all(r['target_candidate'] for r in rows if r['weighted_vertices'])
result=dict(ddr_bones=bones,ddr_groups=groups,mapping=rows,warning='Semantic mapping used by the experimental exporter; no anatomical alignment.',reference_files=[dict(name=p.name,size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in TEMPLATE.iterdir() if p.is_file()])
(root/'analysis/rig-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Validated PMX section consumption, material triangle totals, texture presence, and candidate coverage of every weighted source bone.')
print('DDR bone lookup:',bones)
print('Source morph types:',sorted({m['type'] for m in pmx['morphs']}))
