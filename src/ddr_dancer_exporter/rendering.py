"""Shared model loading, CPU frame rendering and MP4 encoding."""
import subprocess
import numpy as np
from PIL import Image
import imageio_ffmpeg
from .motion import ktmdl, geometry, pose, read_motion
from .fast_renderer import raster, deform

def load_model(directory,filename,face=None):
    m=ktmdl.parse_file(str(directory/filename));pos,norm,uv,ids,weights,faces,texids=geometry(m)
    textures=[Image.open(directory/n).convert('RGBA') for n in m['names']['textureNames']]
    if face:
        fm=ktmdl.parse_file(str(face/'pl_emi00_face01.model'));fp,fn,fu,fi,fw,ff,ft=geometry(fm)
        head=16;hp=np.c_[fp,np.ones(len(fp))]@np.array(m['bones'][head]['matrix'])
        faces=np.concatenate((faces,ff+len(pos)));texids=np.concatenate((texids,ft+len(textures)))
        pos=np.concatenate((pos,hp[:,:3]));uv=np.concatenate((uv,fu))
        ids=np.concatenate((ids,np.full_like(fi,head)));weights=np.concatenate((weights,fw))
        textures += [Image.open(face/n).convert('RGBA') for n in fm['names']['textureNames']]
    tex=np.array([np.array(im.resize((512,512),Image.Resampling.LANCZOS)) for im in textures])
    return dict(model=m,pos=pos,uv=uv,ids=ids.astype(np.int64),weights=weights,faces=faces.astype(np.int64),texids=texids.astype(np.int64),textures=tex,inv=np.array([b['invertMatrix'] for b in m['bones']]))

def frame(asset,motion,sample,size):
    world=pose(asset['model'],motion,sample)
    p=deform(asset['pos'],asset['ids'],asset['weights'],asset['inv']@world)
    assert np.isfinite(p).all()
    return raster(p,asset['uv'],asset['faces'],asset['texids'],asset['textures'],size)

def encoder(path,size,fps):
    path.parent.mkdir(parents=True,exist_ok=True)
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{size}x{size}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    return subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
