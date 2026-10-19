"""Extract shared animation archives, including compressed entries."""
import _bootstrap  # Local src/ discovery for direct invocation.
import json
from extract_arc import extract
from ddr_dancer_exporter.project import PROJECT,MOTIONS
rows=[]
for path in sorted((PROJECT/'animations/archives').glob('*.arc')):
    rows.extend(dict(archive=path.name,**row) for row in extract(path,MOTIONS))
out=PROJECT/'animations/analysis';out.mkdir(exist_ok=True)
(out/'archive-manifest.json').write_text(json.dumps(rows,indent=2))
print('Extracted',len(rows),'entries into',MOTIONS)
