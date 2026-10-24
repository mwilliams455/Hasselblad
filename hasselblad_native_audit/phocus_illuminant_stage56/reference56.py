"""Independent NumPy white-point oracle and scalar bracketed solution.

Uses public Robertson data already cited in the repository; no vendor data.
The accepted renderer requires equal camera-calibration matrices, so DNG's
separate interpolation and the SDK's precomposed interpolation agree here.
"""
import re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'phone_input_20261021/hb_phone_temperature.c').read_text()
rows=re.findall(r'\{([^{}]+)\}',s.split('isotemperature[31][4] = {')[1].split('};')[0])
TABLE=np.array([[float(v.strip().removesuffix('f')) for v in row.split(',')] for row in rows])
NORMAL=np.c_[np.ones(31),TABLE[:,3]];NORMAL/=np.linalg.norm(NORMAL,axis=1)[:,None]

def temperature(xy):
    u,v=np.array([2*xy[0],3*xy[1]])/(1.5-xy[0]+6*xy[1])
    d=(v-TABLE[:,2])*NORMAL[:,0]-(u-TABLE[:,1])*NORMAL[:,1]
    stop=np.flatnonzero(d[1:]<=0);i=int(stop[0]+1) if len(stop) else 30
    f=0 if i==1 else -min(d[i],0)/(d[i-1]-min(d[i],0))
    k=1e6/(TABLE[i-1,0]*f+TABLE[i,0]*(1-f))
    locus=f*TABLE[i-1,1:3]+(1-f)*TABLE[i,1:3]
    normal=f*NORMAL[i-1]+(1-f)*NORMAL[i];normal/=np.linalg.norm(normal)
    return k,float((np.array([u,v])-locus)@normal*-3000)

def xy_from_temperature(k,tint):
    r=1e6/k;i=int(np.clip(np.searchsorted(TABLE[:,0],r,side='right')-1,0,29))
    f=(TABLE[i+1,0]-r)/(TABLE[i+1,0]-TABLE[i,0])
    normal=f*NORMAL[i]+(1-f)*NORMAL[i+1];normal/=np.linalg.norm(normal)
    u,v=f*TABLE[i,1:3]+(1-f)*TABLE[i+1,1:3]+normal*tint/-3000
    return np.array([1.5*u,v])/(u-4*v+2)

def normalize(m):
    m=np.array(m,float).reshape(3,3);scale=np.max(m@np.array([.9642,1,.8249]))
    if scale<.99 or scale>1.01:m=m/scale
    return np.floor(m*10000+.5)/10000

def matrix(c1,c2,cc,ab,t1,t2,k):
    w=np.clip((1/k-1/t2)/(1/t1-1/t2),0,1)
    return np.diag(ab)@cc@(w*c1+(1-w)*c2)

def solve(c1,c2,cc,ab,n,t1=6500,t2=2850):
    c1,c2=normalize(c1),normalize(c2)
    def point(k):
        xyz=np.linalg.solve(matrix(c1,c2,cc,ab,t1,t2,k),n)
        if not np.all(xyz>0):raise ValueError('nonpositive white')
        return xyz[:2]/xyz.sum()
    low,high=1667.,100000.
    assert temperature(point(low))[0]-low>=0 and temperature(point(high))[0]-high<=0
    for _ in range(80):
        middle=(low+high)*.5
        if temperature(point(middle))[0]>middle:low=middle
        else:high=middle
    xy=point((low+high)*.5);k,tint=temperature(xy)
    return k,tint,xy

def quantize(k):
    k=max(2000,min(50000,int(k+.5)))
    for low,high,step in ((2000,8000,50),(8000,10000,100),(10000,20000,1000),(20000,50000,5000)):
        if k<=high:return low+int(float(np.float32((k-low)/step))+.5)*step
