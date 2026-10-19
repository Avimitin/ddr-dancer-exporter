"""Render synchronized 30fps H.264 MP4s and an offline comparison manifest."""
import _bootstrap  # Local src/ discovery for direct invocation.
import argparse,json,time
from ddr_dancer_exporter.catalog import rebuild
import numpy as np
from PIL import Image
from ddr_dancer_exporter.project import PROJECT,DANCER,CONFIG,output_model_dir,MOTIONS,require_credits
from ddr_dancer_exporter.motion import read_motion

from ddr_dancer_exporter.rendering import load_model, frame, encoder

DEFAULT=['mc_female_sf02_exec','mc_female_hh01_exec','mc_female_ht02_exec','mc_female_br01_exec','mc_female_ja01_exec','mc_bpm120_start01_exec']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dancer',default='adelie-tomorin');ap.add_argument('--all',action='store_true');ap.add_argument('--clips',nargs='+');ap.add_argument('--size',type=int,default=640);ap.add_argument('--fps',type=int,default=30);ap.add_argument('--test-frames',type=int,default=0)
    args=ap.parse_args()
    credits=require_credits(CONFIG)
    stockdir=PROJECT/'dancers/stock-emi';stock=load_model(stockdir/'model','pl_emi00.model',stockdir/'face')
    directory=(DANCER/CONFIG['model']).parent if CONFIG.get('kind')=='template' else output_model_dir()
    converted=load_model(directory,'pl_'+CONFIG['model_id']+'.model')
    names=args.clips or ([p.stem for p in sorted(MOTIONS.glob('*.anm'))] if args.all else DEFAULT)
    records=[];start=time.monotonic()
    for name in names:
        motion=read_motion(MOTIONS/(name+'.anm'));last=motion['header']['lastSampleIndex']
        count=int(np.floor(last*args.fps/60))+1
        if args.test_frames:count=min(count,args.test_frames)
        files=[stockdir/'preview/mp4'/(name+'.mp4'),DANCER/'preview/mp4'/(name+'.mp4')]
        cachepath=stockdir/'preview'/f'{name}.cache.json'
        signature=dict(size=args.size,fps=args.fps,frames=count)
        cached=cachepath.exists() and json.loads(cachepath.read_text())==signature and files[0].exists()
        assets=[converted] if cached else [stock,converted]
        directories=[DANCER] if cached else [stockdir,DANCER]
        procs=[encoder(p,args.size,args.fps) for p in (files[1:] if cached else files)]
        try:
            for i in range(count):
                for asset,proc,directory in zip(assets,procs,directories):
                    pixels=frame(asset,motion,i*60/args.fps,args.size)
                    proc.stdin.write(pixels.tobytes())
                    if i==0:
                        Image.fromarray(pixels).save(directory/'preview'/f'{name}.jpg',quality=90)
                if i%180==0:print(f'{name}: {i}/{count} frames, elapsed {time.monotonic()-start:.1f}s',flush=True)
        finally:
            for proc in procs:
                proc.stdin.close();err=proc.stderr.read().decode();code=proc.wait()
                if code:raise RuntimeError(err)
        cachepath.write_text(json.dumps(signature))
        records.append(dict(id=name,label=name.replace('mc_female_','Female / ').replace('mc_bpm120_','120 BPM / ').replace('_exec','').upper(),fps=args.fps,frames=count,duration=count/args.fps,source_samples=last+1,stock='../'+files[0].relative_to(PROJECT).as_posix(),converted='../'+files[1].relative_to(PROJECT).as_posix(),stockPoster='../'+(stockdir/'preview'/f'{name}.jpg').relative_to(PROJECT).as_posix(),convertedPoster='../'+(DANCER/'preview'/f'{name}.jpg').relative_to(PROJECT).as_posix()))
        print('Finished',name,flush=True)
    manifest=dict(title='DDR Dancer Exporter',stock=dict(id='stock-emi',name='Emi',kind='Stock DDR dancer',credit='KONAMI · DDR game assets'),converted=dict(id=CONFIG['id'],name=CONFIG['label'],kind='BLEND to DDR' if CONFIG.get('input_type')=='blend' else 'PMX to DDR',credit=credits.strip()),animations=records,notes='Offline preview, not captured in DDR. Same motion sample and camera on both sides. Source motion rate is assumed to be 60 Hz; rendered at 30 fps.')
    (DANCER/'preview/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    rebuild()
    print('Complete:',len(records),'comparisons in',round(time.monotonic()-start,1),'seconds',flush=True)

if __name__=='__main__':main()
