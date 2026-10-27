"""Independent dense/multicolour holdouts, never used to select original Stage97 gates."""
import numpy as np,ctypes as C,json
from scipy.ndimage import gaussian_filter,maximum_filter,minimum_filter
from pathlib import Path
from native99 import candidate,configure
options={'candidate':{}}
import sys
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
y,x=np.mgrid[:192,:192];rng=np.random.default_rng(99067);rows=[]
palette=np.array([[.5,.03,.04],[.04,.5,.08],[.03,.06,.55],[.48,.4,.04],[.35,.04,.42],[.05,.42,.48],[.5,.5,.5]])
def scene(kind,angle,phase):
 rad=np.deg2rad(angle);X=(x-96)*np.cos(rad)+(y-96)*np.sin(rad)+phase;Y=-(x-96)*np.sin(rad)+(y-96)*np.cos(rad)+phase
 if kind=='weave':return palette[(np.floor(X/3).astype(int)+2*np.floor(Y/4).astype(int))%7]
 if kind=='broad_tiles':return palette[(np.floor(X/18).astype(int)+2*np.floor(Y/18).astype(int))%7]
 if kind=='purple_texture':
  v=np.sin(X*2.1)*np.cos(Y*1.7)*.5+.5
  return np.array([.1,.04,.1])+v[:,:,None]*np.array([.32,.22,.36])
 if kind=='colour_sines':return np.stack([.25+.2*np.sin(X*.45),.25+.2*np.sin(Y*.39),.25+.2*np.sin((X+Y)*.2)],2)
 local=np.random.default_rng(331 if kind=='sky_branches' else 887)
 out=np.zeros((192,192,3))+([.23,.42,.68] if kind=='sky_branches' else [.32,.4,.22])
 for i in range(45):
  cx,cy=local.uniform(-90,90,2);theta=local.uniform(0,np.pi);length=local.uniform(8,100);width=local.uniform(.4,5)
  along=(X-cx)*np.cos(theta)+(Y-cy)*np.sin(theta);across=-(X-cx)*np.sin(theta)+(Y-cy)*np.cos(theta)
  mask=(abs(along)<length/2)&(abs(across)<width/2)
  out[mask]=([.025,.035,.02] if kind=='sky_branches' else palette[i%7]*local.uniform(.4,1))
 return out

for kind in ['weave','broad_tiles','purple_texture','colour_sines','sky_branches','coloured_branches']:
 for n in map(np.array,[[.3369140625,1,.638671875],[.21,1,.87],[1.2,1,.45]]):
  for angle,phase in [(7,.3),(38,.8),(79,1.1)]:
   for blur in [.45,1.1]:
    original=scene(kind,angle,phase);signal=gaussian_filter(original,(blur,blur,0))
    for scale,noise in [(50000,0),(8000,80),(135000,0)]:
     truth=signal*n*scale
     raw=np.empty((192,192),float)
     for yy,xx,ch in [(0,0,0),(0,1,1),(1,0,1),(1,1,2)]:raw[yy::2,xx::2]=truth[yy::2,xx::2,ch]
     if noise:raw+=rng.normal(0,noise,raw.shape)
     raw=np.clip(np.floor(raw+.5),0,65535).astype(np.uint16);src=render(raw,n)
     base=filter_chroma(src,n);baseguard=maximum_filter((raw==0)|(raw==65535),5)[32:-32,32:-32];base[baseguard]=src[baseguard]
     target=truth[32:-32,32:-32];row={'kind':kind,'n':n.tolist(),'angle':angle,'phase':phase,'blur':blur,'scale':scale,'noise':noise}
     for name,opts in [('stage97',None)]+list(options.items()):
      out=base if opts is None else candidate(base,n,**opts)
      if opts is not None:
       guard=((raw==0)|maximum_filter(raw==65535,31))[32:-32,32:-32];out[guard]=base[guard]
      err=(out-target)/n/scale
      row[name]={'rgb':float(np.sqrt(np.mean(err**2))),'chroma':float(np.sqrt(np.mean((err[:,:,0]-err[:,:,1])**2+(err[:,:,2]-err[:,:,1])**2)))}
     rows.append(row)
 print(kind,len(rows),flush=True)
summary={}
for name in options:
 summary[name]={}
 for kind in sorted(set(r['kind'] for r in rows)):
  group=[r for r in rows if r['kind']==kind];bad=[r for r in group if r[name]['rgb']>r['stage97']['rgb']*1.05+.0001]
  summary[name][kind]={'cases':len(group),'regressions':len(bad),'rgb_ratio':float(np.mean([r[name]['rgb']/r['stage97']['rgb'] for r in group])),'chroma_ratio':float(np.mean([r[name]['chroma']/r['stage97']['chroma'] for r in group]))}
(p/'STAGE99_TEXTURES_CASES.json').write_text(json.dumps(rows));(p/'STAGE99_TEXTURES_SUMMARY.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))

assert sum(r["regressions"] for v in summary.values() for r in (v.values() if isinstance(v,dict) else v))==0,summary
