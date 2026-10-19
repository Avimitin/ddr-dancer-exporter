raise SystemExit("Archived migration; not intended for the current project layout.")
"""Finish the copied legacy layout migration and isolate model-specific mappings."""
from pathlib import Path
import json
p=Path(__file__).resolve().parents[1]
f=p/'scripts/compare_ddr.py';s=f.read_text(encoding='utf-8')
if 'mapping={' in s:
    start=s.index('mapping={');end=s.index('\nrows=[]',start)
    report=json.loads((p/'dancers/adelie-tomorin/analysis/rig-comparison.json').read_text(encoding='utf-8'))
    mapping={b['source_name']:b['target_candidate'] for b in report['mapping'] if b['target_candidate']}
    (p/'dancers/adelie-tomorin/bone-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    s=s[:start]+"mapping=json.loads((root/'bone-map.json').read_text(encoding='utf-8'))"+s[end:]
    s='\n'.join(line for line in s.split('\n') if not line.strip().startswith("if b['name'].startswith('Sl_Hair')"))
    f.write_text(s,encoding='utf-8')
(p/'scripts/extract_motion.py').write_text('''"""Extract shared animation archives, including compressed entries."""
import json
from extract_arc import extract
from project import PROJECT,MOTIONS
rows=[]
for path in sorted((PROJECT/'animations/archives').glob('*.arc')):
    rows.extend(dict(archive=path.name,**row) for row in extract(path,MOTIONS))
out=PROJECT/'animations/analysis';out.mkdir(exist_ok=True)
(out/'archive-manifest.json').write_text(json.dumps(rows,indent=2))
print('Extracted',len(rows),'entries into',MOTIONS)
''',encoding='utf-8')
print('Moved bone mapping into per-dancer configuration; updated animation extraction.')
