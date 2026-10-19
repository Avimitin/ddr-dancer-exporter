# SPDX-License-Identifier: GPL-3.0-or-later
"""Check decoded output against source geometry, independent of the write loop."""
import _bootstrap  # Local src/ discovery for direct invocation.
from pathlib import Path
import json,struct,sys
import numpy as np
from PIL import Image
from ddr_dancer_exporter.project import PROJECT,DANCER,TEMPLATE,MOTIONS,CAMERA,CONFIG,output_model_dir,require_credits
ROOT=DANCER;sys.path.insert(0,str(PROJECT/'tools'))
import ktmdl
def main():
    directory=output_model_dir()
    credits=require_credits(CONFIG)
    assert (directory.parent/'借物表.txt').read_text(encoding='utf-8').strip()==credits
    assert (ROOT/'借物表.txt').read_text(encoding='utf-8').strip()==credits
    b=(directory/('pl_'+CONFIG['model_id']+'.model')).read_bytes();model=ktmdl.parse_bytes(b)
    with np.load(ROOT/'analysis/export-geometry.npz') as archive:
        expected={k:archive[k] for k in archive.files}
    # Look up the expected influences by float32 position/UV. Vertex positions
    # alone may coincide across material boundaries, so retain all candidates.
    positions=expected['positions'].astype(np.float32);by_position={}
    for i,v in enumerate(positions):by_position.setdefault(v.tobytes(),[]).append(i)
    checked=0
    for p in model['packets']:
        for v in p['vertices']:
            candidates=by_position[np.asarray(v['POSITION'],dtype=np.float32).tobytes()]
            ids=[p['bonePalette'][i] for i in v['BLENDINDICES']];ws=[1-sum(v['BLENDWEIGHT']),*v['BLENDWEIGHT']]
            assert any(np.array_equal(expected['indices'][i],ids) and np.allclose(expected['weights'][i],ws,atol=1e-6) for i in candidates)
            uv=struct.unpack('<2e',bytes.fromhex(v['TEXCOORD0']['rawHex']));assert np.isfinite(uv).all()
            assert abs(np.linalg.norm(v['NORMAL'])-1)<1e-5
            checked+=1
        for stream in (p['vertexDescriptor'],p['indexDescriptor']):
            start=stream['offset']+stream['streamOffset'];stride=stream['stride'] if stream['type']==0 else 2
            assert start>=model['header']['streamDataOffset'] and start+stream['numVertex']*stride<=len(b)
    assert sum(len(p['triangles']) for p in model['packets'])==len(expected['triangles'])
    dds_checks=[]
    for name in model['names']['textureNames']:
        data=(directory/name).read_bytes();assert data[:4]==b'DDS '
        h,w=struct.unpack_from('<2I',data,12);mips=struct.unpack_from('<I',data,28)[0]
        assert w&(w-1)==0 and h&(h-1)==0 and max(w,h)<=1024
        wanted=128;ww,hh=w,h
        for _ in range(mips):wanted+=ww*hh*4;ww=max(1,ww//2);hh=max(1,hh//2)
        assert len(data)==wanted
        im=Image.open(directory/name);assert im.size==(w,h)
        dds_checks.append(dict(name=name,width=w,height=h,mips=mips,bytes=len(data)))
    report=dict(status='PASS',decoded_vertices_checked=checked,triangles=len(expected['triangles']),checks=['Source positions and mapped skin weights survive binary encoding','Half UVs finite; normals unit length','Every stream falls inside rebuilt geometry section','All DDS files have valid power-of-two dimensions and full mip payloads'],textures=dds_checks)
    (ROOT/'analysis/export-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
