import numpy as np,ctypes as C,json,sys
from pathlib import Path
from scipy.ndimage import gaussian_filter,maximum_filter
from native99 import candidate,configure
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'phocus_edges_stage97'))
from reference97 import filter_chroma
p=Path(sys.argv[1]);configure(p);lib=C.CDLL(str((p/'libhbframe97.so').resolve()));U=C.POINTER(C.c_uint16)
lib.hb96_render_band.argtypes=[U,C.c_size_t,C.c_int,C.c_int,C.c_int,C.c_int,U,C.c_size_t,C.c_double,C.c_double]
def render(raw,n):
 out=np.empty((128,128,3),np.uint16)
 for y in [0,64]:
  a=np.ascontiguousarray(raw[y:y+128]);b=out[y:y+64]
  assert lib.hb96_render_band(a.ctypes.data_as(U),a.size,192,0,64,4,b.ctypes.data_as(U),b.size,n[0],n[2])==0
 return out
y,x=np.mgrid[:192,:192];rng=np.random.default_rng(99001);records=[]
options={'candidate':{}}
colours=[([.55]*3,[.03]*3),([.5,.04,.04],[.04,.5,.04]),([.04,.08,.5],[.5,.4,.04]),([.5]*3,[.25,.02,.25]),([.5]*3,[.18,.15,.18]),([.5]*3,[.08,.06,.08]),([.35,.5,.7],[.03,.04,.02]),([.18,.4,.8],[.03,.04,.02]),([.2,.6,.75],[.03,.04,.02])]
def run(n,angle,width,blur,ci,noise=0,scale=50000):
 d=(x-96.3)*np.cos(np.deg2rad(angle))+(y-96.3)*np.sin(np.deg2rad(angle))
 mask=gaussian_filter((d>0).astype(float) if width==0 else (abs(d)<width/2).astype(float),blur)
 a,b=map(np.array,colours[ci]);truth=(a+(b-a)*mask[:,:,None])*n*scale
 raw=np.empty((192,192),float)
 for yy,xx,ch in [(0,0,0),(0,1,1),(1,0,1),(1,1,2)]:raw[yy::2,xx::2]=truth[yy::2,xx::2,ch]
 if noise:raw+=rng.normal(0,noise,raw.shape)
 raw=np.clip(np.floor(raw+.5),0,65535).astype(np.uint16);src=render(raw,n)
 guard=((raw==0)|maximum_filter(raw==65535,31))[32:-32,32:-32];baseguard=maximum_filter((raw==0)|(raw==65535),5)[32:-32,32:-32]
 base=filter_chroma(src,n);base[baseguard]=src[baseguard];target=truth[32:-32,32:-32];edge=abs(d[32:-32,32:-32])<8
 outputs={'stage97':base,'stage96':src,**{name:candidate(base,n,**opts) for name,opts in options.items()}}
 row={'n':n.tolist(),'angle':angle,'width':width,'blur':blur,'colour':ci,'noise':noise,'scale':scale}
 for name,out in outputs.items():
  if name not in ['stage97','stage96']:out[guard]=base[guard]
  err=(out-target)/n/scale
  row[name]={'rgb':float(np.sqrt(np.mean(err[edge]**2))),'chroma':float(np.sqrt(np.mean(((err[:,:,0]-err[:,:,1])**2+(err[:,:,2]-err[:,:,1])**2)[edge])))}
 records.append(row)
for n in map(np.array,[[1.,1,1.],[.35,1,.6],[.6,1,.25],[1.5,1,.7]]):
 for angle in [0,23,45,73,90]:
  for width in [0,1,2,4]:
   for blur in [.3,1.]:
    for ci in range(9):run(n,angle,width,blur,ci)
 print('completed neutral',n,len(records),flush=True)
for n in map(np.array,[[.2,1,.9],[.8,1,1.4]]):
 for angle in [11,37,61,87]:
  for ci in range(9):
   for noise,scale in [(0,50000),(100,50000),(200,5000),(0,150000)]:run(n,angle,2,.65,ci,noise,scale)
summary={}
for name in options:
 summary[name]=[]
 for ci in range(9):
  rows=[r for r in records if r['colour']==ci]
  summary[name].append({'colour':ci,'cases':len(rows),'regressions':sum(r[name]['rgb']>r['stage97']['rgb']*1.05+.0001 for r in rows),'stage97_chroma':float(np.mean([r['stage97']['chroma'] for r in rows])),'candidate_chroma':float(np.mean([r[name]['chroma'] for r in rows]))})
 print(name,json.dumps(summary[name]),flush=True)
(p/'STAGE99_EDGES_CASES.json').write_text(json.dumps(records));(p/'STAGE99_EDGES_SUMMARY.json').write_text(json.dumps(summary,indent=2))

assert sum(r["regressions"] for v in summary.values() for r in (v.values() if isinstance(v,dict) else v))==0,summary
