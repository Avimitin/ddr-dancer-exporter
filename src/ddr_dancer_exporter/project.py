"""Shared paths and per-dancer selection for the DDR Dancer Exporter tools."""
from pathlib import Path
import argparse,json,os
PROJECT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--dancer',default=os.environ.get('DDR_DANCER','adelie-tomorin'))
options,_=parser.parse_known_args()
if Path(options.dancer).name!=options.dancer or options.dancer in ('.','..'):
    raise ValueError('Dancer must be a folder name beneath dancers/')
DANCER=PROJECT/'dancers'/options.dancer
CONFIG=json.loads((DANCER/'dancer.json').read_text(encoding='utf-8'))
def require_credits(config):
    value=config.get('credits')
    if not isinstance(value,str) or not value.strip():
        raise ValueError('Every converted input model MUST have a non-empty 借物表: set credits in dancer.json')
    return value.strip()
TEMPLATE=PROJECT/'dancers'/CONFIG.get('template','template-miku')/'model'
MOTIONS=PROJECT/'animations/motions'
CAMERA=PROJECT/'animations/camera/movie_st01_1p.camanm'

def output_model_dir():
    return DANCER/'output'/CONFIG['package_name']/('pl_'+CONFIG['model_id'])
