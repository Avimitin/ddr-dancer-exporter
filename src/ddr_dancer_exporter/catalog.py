"""Combine completed dancer previews without losing other models."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def rebuild():
    models=[]
    for p in sorted((ROOT/'dancers').glob('*/preview/manifest.json')):
        m=json.loads(p.read_text(encoding='utf-8'))
        if not m['converted'].get('credit','').strip(): raise ValueError(f'Missing credits: {p}')
        config=json.loads((p.parents[1]/'dancer.json').read_text(encoding='utf-8'))
        m['converted']['kind']=config.get('preview_kind') or ('BLEND to DDR' if config.get('input_type')=='blend' else 'PMX to DDR')
        if config.get('input_type')=='blend':
            m['notes']+=' Base-color textures and mapped source skin weights; Blender cloth, shader effects, hair physics and facial morphs are omitted.'
        if config.get('kind')=='template':
            m['notes']+=' Original custom-mod model and textures, copied byte-for-byte; this entry has not passed through the converter. The supplied mod folder does not identify its model/mod author.'
        if config.get('arm_retarget'):
            m['notes']+=' Arm rest poses and joint pivots are aligned to DDR; roll weights are included. Broad bodies and wings can still intersect the torso because no collision solver is used.'
        models.append(m)
    if not models: raise ValueError('No rendered models')
    catalog={**models[0],'models':models}
    (ROOT/'preview/manifest.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'preview/manifest.js').write_text('window.DDR_PREVIEW = '+json.dumps(catalog,ensure_ascii=False)+';\n',encoding='utf-8')
if __name__=='__main__': rebuild()
