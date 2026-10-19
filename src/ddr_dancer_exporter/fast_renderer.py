"""Numba CPU rasterizer for smooth offline MP4 previews (no Blender required)."""
import math
import numpy as np
from numba import njit

@njit(cache=True)
def raster(pos,uv,faces,texids,textures,size):
    canvas=np.empty((size,size,3),np.uint8);canvas[:,:,0]=22;canvas[:,:,1]=28;canvas[:,:,2]=39
    zbuf=np.full((size,size),1e20)
    screen=np.empty((len(pos),2));scale=size/3.5
    for i in range(len(pos)):
        screen[i,0]=size*.5+pos[i,0]*scale
        screen[i,1]=size*.68-pos[i,1]*scale
    floor=int(size*.68)
    for y in range(floor,size):
        for x in range(size):
            canvas[y,x,0]=25;canvas[y,x,1]=33;canvas[y,x,2]=44
    for x in range(size):
        canvas[floor,x,0]=61;canvas[floor,x,1]=74;canvas[floor,x,2]=91
    for fi in range(len(faces)):
        ia,ib,ic=faces[fi];a=screen[ia];b=screen[ib];c=screen[ic]
        x0=max(0,int(math.floor(min(a[0],b[0],c[0]))));x1=min(size-1,int(math.ceil(max(a[0],b[0],c[0]))))
        y0=max(0,int(math.floor(min(a[1],b[1],c[1]))));y1=min(size-1,int(math.ceil(max(a[1],b[1],c[1]))))
        den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-8 or x1<x0 or y1<y0:continue
        edge1=pos[ib]-pos[ia];edge2=pos[ic]-pos[ia]
        nx=edge1[1]*edge2[2]-edge1[2]*edge2[1];ny=edge1[2]*edge2[0]-edge1[0]*edge2[2];nz=edge1[0]*edge2[1]-edge1[1]*edge2[0]
        shade=.7+.3*abs(.3*nx+.5*ny+.8*nz)/max(math.sqrt(nx*nx+ny*ny+nz*nz),1e-10)
        ti=texids[fi];th=textures.shape[1];tw=textures.shape[2]
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                w0=((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/den
                w1=((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/den;w2=1-w0-w1
                if w0<0 or w1<0 or w2<0:continue
                z=-(w0*pos[ia,2]+w1*pos[ib,2]+w2*pos[ic,2])
                if z>=zbuf[y,x]:continue
                u=w0*uv[ia,0]+w1*uv[ib,0]+w2*uv[ic,0];v=w0*uv[ia,1]+w1*uv[ib,1]+w2*uv[ic,1]
                tx=max(0,min(tw-1,int(u*tw)));ty=max(0,min(th-1,int(v*th)))
                if textures[ti,ty,tx,3]<100:continue
                for ch in range(3):canvas[y,x,ch]=min(255,int(textures[ti,ty,tx,ch]*shade))
                zbuf[y,x]=z
    return canvas

@njit(cache=True)
def deform(pos,ids,weights,matrices):
    out=np.zeros((len(pos),3))
    for i in range(len(pos)):
        for k in range(4):
            w=weights[i,k]
            if w==0:continue
            m=matrices[ids[i,k]]
            for j in range(3):out[i,j]+=w*(pos[i,0]*m[0,j]+pos[i,1]*m[1,j]+pos[i,2]*m[2,j]+m[3,j])
    return out
