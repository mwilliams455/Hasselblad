#!/usr/bin/env python3
"""Synthetic Bayer edges with known RGB; no photos or private profiles required."""
import ctypes as c,json,sys
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
W=Path(sys.argv[1]);lib=c.CDLL(str(W/'libhbframe96.so'))
U=c.POINTER(c.c_uint16)
base=[U,c.c_size_t,c.c_int,c.c_int,c.c_int,c.c_int,U,c.c_size_t]
lib.hb77_render_band.argtypes=base
lib.hb96_render_band.argtypes=base+[c.c_double,c.c_double]
def ptr(a):return a.ctypes.data_as(U)
def render(raw,n=None):
 h,w=raw.shape;dst=np.empty((h-64,w-64,3),np.uint16)
 for y in range(0,h-64,64):
  anchor=min(y,h-128);rows=min(64,h-64-y);a=np.ascontiguousarray(raw[anchor:anchor+128]);b=dst[y:y+rows]
  args=[ptr(a),a.size,w,y-anchor,rows,4,ptr(b),b.size]
  code=lib.hb77_render_band(*args) if n is None else lib.hb96_render_band(*args,n[0]/n[1],n[2]/n[1])
  assert code==0
 return dst
def phocus(raw):return render(raw)
def noise(raw,n):return render(raw,n)
y,x=np.mgrid[:192,:192];records=[]
for ni,n in enumerate([np.array([1.,1.,1.]),np.array([.315,1.,.678]),np.array([.6,1.,.25]),np.array([1.5,1.,.7])]):
 for angle in [0,23,45,73,90]:
  d=(x-96)*np.cos(np.deg2rad(angle))+(y-96)*np.sin(np.deg2rad(angle))
  for sigma in [0,.6,1.2]:
   mask=gaussian_filter((d>0).astype(float),sigma) if sigma else (d>0).astype(float)
   for ci,(a,b) in enumerate([([.03]*3,[.55]*3),([.5,.04,.04],[.04,.5,.04]),([.04,.08,.5],[.5,.4,.04])]):
    truth=(np.array(a)+(np.array(b)-np.array(a))*mask[:,:,None])*n*50000
    raw=np.empty((192,192),np.uint16)
    raw[::2,::2]=np.rint(truth[::2,::2,0]);raw[1::2,1::2]=np.rint(truth[1::2,1::2,2]);raw[::2,1::2]=np.rint(truth[::2,1::2,1]);raw[1::2,::2]=np.rint(truth[1::2,::2,1])
    target=truth[32:-32,32:-32];edge=np.abs(d[32:-32,32:-32])<8
    row={'neutral':ni,'angle':angle,'sigma':sigma,'colour':ci}
    for mode,fn in [('phocus',lambda:phocus(raw)),('noise',lambda:noise(raw,n))]:
     out=fn().astype(float);error=(out-target)/n/50000
     chroma=(error[:,:,0]-error[:,:,1])**2+(error[:,:,2]-error[:,:,1])**2
     row[mode]={'rmse':float(np.sqrt(np.mean(error[edge]**2))),'chroma_rmse':float(np.sqrt(np.mean(chroma[edge]))),'mae':float(np.abs(error[edge]).mean())}
    records.append(row)
for ci in range(3):
 rows=[r for r in records if r['colour']==ci]
 print('colour',ci,{k:float(np.mean([r[k]['chroma_rmse'] for r in rows])) for k in ['phocus','noise']},flush=True)
 for k in ['noise']:
  worse=[r for r in rows if r[k]['rmse']>r['phocus']['rmse']*1.05+1e-4]
  print(k,'worse',len(worse),'of',len(rows),flush=True)


summary={}
for ci,name in enumerate(['neutral','red_green','blue_yellow']):
 rows=[r for r in records if r['colour']==ci]
 old=float(np.mean([r['phocus']['chroma_rmse'] for r in rows]));new=float(np.mean([r['noise']['chroma_rmse'] for r in rows]))
 regressions=sum(r['noise']['rmse']>r['phocus']['rmse']*1.05+1e-4 for r in rows)
 summary[name]={'baseline_mean_chroma_rmse':old,'adapted_mean_chroma_rmse':new,'rgb_rmse_regressions':regressions,'cases':len(rows)}
 assert new<=old,summary[name]
 if ci==0:assert new<old*.65 and regressions==0
# A bound on known colour-edge tradeoffs, not a claim of pointwise improvement.
assert max(r['noise']['rmse']-r['phocus']['rmse'] for r in records)<.0045
for n in [np.array([1.,1,1]),np.array([.315,1,.678]),np.array([.6,1,.25]),np.array([1.5,1,.7])]:
 for level in [0,32,2000,20000,40000]:
  target=np.rint(n*level).astype(np.uint16);raw=np.full((192,192),target[1],np.uint16);raw[::2,::2]=target[0];raw[1::2,1::2]=target[2]
  assert np.abs(noise(raw,n).astype(int)-target).max()<=2
(W/'STAGE96_QUALITY_VALIDATION.json').write_text(json.dumps({'status':'PASS_HOST_ONLY','summary':summary,'flat_neutral_cases':20,'records':records},indent=2)+'\n')
print(json.dumps(summary),flush=True)
