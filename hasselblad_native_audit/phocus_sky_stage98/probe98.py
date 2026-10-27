from pathlib import Path
import ctypes as C,re,subprocess,json,argparse
import numpy as np
from scipy.ndimage import gaussian_filter,maximum_filter,minimum_filter,median_filter
parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);args=parser.parse_args()
r=Path(__file__).resolve().parents[1];p=args.work.resolve();p.mkdir(parents=True,exist_ok=True)
sources=[r/q for q in re.findall(r'"\$base/([^"\n]+\.c)"',(r/'phocus_output_stage74/run_host74.sh').read_text()) if '/test_' not in q]
sources=list(dict.fromkeys(sources))+[r/'phocus_chroma_stage96/frame96.c',r/'phocus_edges_stage97/frame97.c',r/'phocus_edges_stage97/chroma97.c']
subprocess.run(['gcc','-O2','-std=c11','-ffp-contract=off','-fno-fast-math','-shared','-fPIC','-pthread',*map(str,sources),'-lm','-o',str(p/'sky.so')],check=True)
lib=C.CDLL(str(p/'sky.so'));U=C.POINTER(C.c_uint16)
for rev in [96,97]:getattr(lib,'hb%d_render_band'%rev).argtypes=[U,C.c_size_t,C.c_int,C.c_int,C.c_int,C.c_int,U,C.c_size_t,C.c_double,C.c_double]
ptr=lambda a:a.ctypes.data_as(U)
def render(raw,n,rev):
    dst=np.empty((128,128,3),np.uint16)
    for y in [0,64]:
        a=np.ascontiguousarray(raw[y:y+128]);out=dst[y:y+64]
        assert getattr(lib,'hb%d_render_band'%rev)(ptr(a),a.size,192,0,64,4,ptr(out),out.size,n[0],n[2])==0
    return dst
y,x=np.mgrid[:192,:192];records=[]
for name,sky in [('grey',[.55,.55,.55]),('pale_blue',[.35,.50,.70]),('blue',[.18,.40,.80]),('cyan',[.20,.60,.75])]:
 for n in map(np.array,[[1.,1.,1.],[.35,1.,.6]]):
  for angle in [0,23,45,73,90]:
   for width in [1,2,4]:
    d=(x-96.3)*np.cos(np.deg2rad(angle))+(y-96.3)*np.sin(np.deg2rad(angle))
    mask=gaussian_filter((np.abs(d)<width/2).astype(float),.65)
    truth=(np.array(sky)+(np.array([.03,.04,.02])-sky)*mask[:,:,None])*n*50000
    raw=np.empty((192,192),np.uint16)
    for yy,xx,ch in [(0,0,0),(0,1,1),(1,0,1),(1,1,2)]:raw[yy::2,xx::2]=np.floor(truth[yy::2,xx::2,ch]+.5)
    a=render(raw,n,96);b=render(raw,n,97);target=truth[32:-32,32:-32];edge=np.abs(d[32:-32,32:-32])<5
    rgb=a/n;s=rgb[:,:,0]+2*rgb[:,:,1]+rgb[:,:,2];Y=s*.25
    c1=(rgb[:,:,0]-rgb[:,:,1])/(s+1);c2=(rgb[:,:,2]-rgb[:,:,1])/(s+1)
    near=maximum_filter(np.maximum(np.abs(c1),np.abs(c2)),5)
    contrast=(maximum_filter(Y,3)-minimum_filter(Y,3))/np.maximum(maximum_filter(Y,3),160)
    correction=np.maximum(np.abs(median_filter(c1,3)-c1),np.abs(median_filter(c2,3)-c2))>0
    eligible=edge&(contrast>.2)&correction
    row={'sky':name,'neutral':n.tolist(),'angle':angle,'width':width,'edge_pixels':int(edge.sum()),'changed_edge_pixels':int(np.any(a!=b,2)[edge].sum()),'potential_pixels':int(eligible.sum()),'colour_guard_blocks':int((eligible&(near>=.16)).sum())}
    for key,v in [('stage96',a),('stage97',b)]:
     error=(v-target)/n/50000;row[key+'_rgb_rmse']=float(np.sqrt(np.mean(error[edge]**2)))
     row[key+'_chroma_rmse']=float(np.sqrt(np.mean(((error[:,:,0]-error[:,:,1])**2+(error[:,:,2]-error[:,:,1])**2)[edge])))
    records.append(row)
summary=[]
for name in ['grey','pale_blue','blue','cyan']:
 rows=[q for q in records if q['sky']==name];total=sum(q['edge_pixels'] for q in rows);potential=sum(q['potential_pixels'] for q in rows)
 summary.append({'background':name,'cases':len(rows),'changed_edge_pct':100*sum(q['changed_edge_pixels'] for q in rows)/total,'colour_guard_block_pct_of_potential':100*sum(q['colour_guard_blocks'] for q in rows)/potential if potential else None,**{key:float(np.mean([q[key] for q in rows])) for key in ['stage96_rgb_rmse','stage97_rgb_rmse','stage96_chroma_rmse','stage97_chroma_rmse']}})
result={'synthetic_only':True,'does_not_prove_cause_in_new_jpeg':True,'summary':summary,'cases':records}
(p/'SKY98_DIAGNOSTIC.json').write_text(json.dumps(result,indent=2));print(json.dumps(summary,indent=2))
