#!/usr/bin/env python3
"""Stage77 scheduling/performance regression, using unchanged Stage76 as reference."""
import argparse,array,ctypes as c,json,random,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'phocus_scene_stage76'))
from check76 import run as previous,Engine
def run(work,jni,reuse=False):
 work.mkdir(parents=True,exist_ok=True)
 if not reuse:previous(work,jni)
 subprocess.run(['cc','-std=c11','-O2','-shared','-fPIC','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-pthread','-I'+str(jni),'-I'+str(jni/'linux'),str(HERE/'frame77.c'),str(HERE/'jni77.c'),'-L'+str(work),'-lhbfinal74','-Wl,-rpath,$ORIGIN','-o',str(work/'libhbframe77.so')],check=True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 classes=work/'classes';java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 subprocess.run(compiler+['--release','17','-cp',str(classes),'-d',str(classes),*[str(java/name) for name in ('HasselbladFrame77.java','HasselbladPreview77.java')],str(HERE/'Stage77Check.java')],check=True)
 subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'Stage77Check',str(work/'fixtures')],check=True)
 engine=Engine(work);lib=c.CDLL(str(work/'libhbframe77.so'));lib.hb77_render_band.argtypes=[c.POINTER(c.c_uint16),c.c_size_t,c.c_int,c.c_int,c.c_int,c.c_int,c.POINTER(c.c_uint16),c.c_size_t]
 rng=random.Random(7702);channels=0
 for case in range(8):
  w=642;data=array.array('H')
  for y in range(128):
   for x in range(w):
    value=[rng.randrange(65536),(x*197+y*31)&65535,((x//17+y//11)%2)*65535,
     65535 if x==y or x+y==w else 0,65535 if (x+y)%2==0 else 1,
     (x%2)*50000+(y%2)*15000,((x+y)*1000)&65535,65535 if x%19==0 and y%23==0 else 10000][case]
    data.append(value)
  source=(c.c_uint16*len(data)).from_buffer_copy(data)
  for offset,rows in ((0,64),(62,2)):
   expected=engine.band(data,w,offset,rows);out=(c.c_uint16*len(expected))()
   for workers in (1,4):
    assert lib.hb77_render_band(source,len(data),w,offset,rows,workers,out,len(out))==0
    assert bytes(out)==expected.tobytes(),('pattern',case,offset,workers);channels+=len(out)
 # One complete 12MP interior, spatially varying reproducible Bayer data.
 # Store reference output per band for exact comparison and comparable timing.
 w,h=4096,3072;cw,ch=w-64,h-64
 raw=array.array('H',((x*331+y*97+(x*y)%1237)&65535 for y in range(h) for x in range(w)))
 bands=[];expected=[];baseline=0.0
 for y in range(0,ch,64):
  rows=min(64,ch-y);anchor=min(y,ch-64);data=raw[anchor*w:(anchor+128)*w]
  source=(c.c_uint16*len(data)).from_buffer_copy(data);out=(c.c_uint16*(cw*rows*3))()
  t=time.monotonic();assert engine.lib.hb76_render_band(source,len(data),w,y-anchor,rows,out,len(out))==0;baseline+=time.monotonic()-t
  bands.append((source,y-anchor,rows));expected.append(bytes(out))
 timings={};full_channels=0
 for workers in (1,4):
  elapsed=0.0
  for (source,offset,rows),wanted in zip(bands,expected):
   out=(c.c_uint16*(cw*rows*3))();t=time.monotonic()
   assert lib.hb77_render_band(source,len(source),w,offset,rows,workers,out,len(out))==0
   elapsed+=time.monotonic()-t;assert bytes(out)==wanted,('full scene',workers);full_channels+=len(out)
  timings[str(workers)]={'host_seconds':elapsed,'relative_to_stage76':baseline/elapsed}
 result={'schema':'hasselblad-stage77-host-v1','status':'PASS_EXACT_STAGE76_SCHEDULING','synthetic_pattern_channels_exact':channels,
  'full_scene':{'raw':[w,h],'output':[cw,ch],'rgb16_channels_exact_per_run':cw*ch*3,'worker_modes':[1,4],'total_compared_channels':full_channels,
   'stage76_host_seconds':baseline,'stage77':timings,'phone_performance_measured':False},
  'stage74_76_reference_unchanged':True,'original_vendor_wide_geometry_parity_claimed':False,'capture_renderer_changed':False}
 (work/'STAGE77_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni',type=Path,required=True);p.add_argument('--reuse-baseline',action='store_true');a=p.parse_args();run(a.work.resolve(),a.jni.resolve(),a.reuse_baseline)
