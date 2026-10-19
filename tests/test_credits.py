"""Regression checks for the mandatory converted-model 借物表."""
import _bootstrap  # Local src/ discovery for direct invocation.
from ddr_dancer_exporter.project import require_credits,CONFIG,DANCER,output_model_dir
for value in (None,'','  \n\t',[],False,123):
    try:require_credits({'credits':value})
    except ValueError:pass
    else:raise AssertionError(f'Accepted invalid credits: {value!r}')
try:require_credits({})
except ValueError:pass
else:raise AssertionError('Accepted missing credits')
import json
from ddr_dancer_exporter.project import PROJECT
for path in (PROJECT/'dancers').glob('*/dancer.json'):
    config=json.loads(path.read_text(encoding='utf8'))
    if config.get('kind')!='converted':continue
    expected=require_credits(config)
    for sidecar in [path.parent/'借物表.txt',path.parent/'output'/config['package_name']/'借物表.txt']:
        assert sidecar.read_text(encoding='utf8').strip()==expected
print('PASS: invalid credits rejected; all converted model sidecars match their configuration.')
