#!/usr/bin/env python3
"""Synthetic-only stage76 band, seam and scale verification. No full-frame vendor parity claim."""
import argparse,array,ctypes as c,json,os,re,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];AUDIT=ROOT/'hasselblad_native_audit';HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(AUDIT/'phocus_device_stage75'))
from device75 import render
from check75 import run as previous
class Engine:
 def __init__(self,work):
  self.core=c.CDLL(str(work/'libhbfinal74.so'));from device75 import Plan,Settings
  self.core.hb73_plan.argtypes=[c.c_int,c.c_int,c.POINTER(Plan)]
  self.core.hb74_render_final_bounded.argtypes=[c.POINTER(Plan),c.POINTER(Settings),c.POINTER(c.c_uint16),c.c_size_t,c.c_int,c.POINTER(c.c_uint16),c.c_size_t,c.c_void_p]
  self.lib=c.CDLL(str(work/'libhbframe76.so'));self.lib.hb76_render_band.argtypes=[c.POINTER(c.c_uint16),c.c_size_t,c.c_int,c.c_int,c.c_int,c.POINTER(c.c_uint16),c.c_size_t]
 def band(self,data,w,offset=0,rows=64):
  inp=(c.c_uint16*len(data)).from_buffer_copy(data);n=((w-64)&~1)*rows*3;out=(c.c_uint16*n)()
  status=self.lib.hb76_render_band(inp,len(data),w,offset,rows,out,n);assert status==0,status
  return array.array('H',out)
 def tile(self,data,w,x,y):
  payload=b''.join(data[(y+j)*w+x:(y+j)*w+x+128].tobytes() for j in range(128))
  if sys.byteorder!='little':raise RuntimeError('Synthetic runner requires little-endian host')
  return array.array('H',render(self.core,payload,64,64,128))
def run(work,jni):
 work.mkdir(parents=True,exist_ok=True);previous(work,jni)
 sources=[HERE/'frame76.c',HERE/'jni76.c']
 subprocess.run(['cc','-std=c11','-O2','-shared','-fPIC','-Wall','-Wextra','-Werror','-fno-fast-math','-ffp-contract=off','-I'+str(jni),'-I'+str(jni/'linux'),*map(str,sources),'-L'+str(work),'-lhbfinal74','-Wl,-rpath,$ORIGIN','-o',str(work/'libhbframe76.so')],check=True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 classes=work/'classes';java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 subprocess.run(compiler+['--release','17','-cp',str(classes),'-d',str(classes),str(java/'HasselbladFrame76.java'),str(HERE/'Stage76Check.java')],check=True)
 subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'Stage76Check',str(work/'fixtures')],check=True)
 engine=Engine(work);w=256;h=224;cw=w-64;stats=[]
 for case in range(8):
  data=array.array('H');state=76001
  for y in range(h):
   for x in range(w):
    state=(1664525*state+1013904223)&0xffffffff
    value=[state>>16,(x*197+y*31)&65535,((x//17+y//11)%2)*65535,
      (65535 if x==y or x+y==w else 0),(65535 if (x+y)%2==0 else 1),
      (x%2)*50000+(y%2)*15000,((x+y)*1000)&65535,(65535 if x%19==0 and y%23==0 else 10000)][case]
    data.append(value)
  count=0
  for y in (0,32,64,96):
   band=engine.band(data[y*w:(y+128)*w],w)
   for x in (0,2,16,48,64,96,128):
    tile=engine.tile(data,w,x,y)
    for row in range(64):
     actual=band[(row*cw+x)*3:(row*cw+x+64)*3];expected=tile[row*192:(row+1)*192]
     assert actual==expected,('horizontal seam',case,x,y,row);count+=192
   if y+160<=h:
    shifted=engine.band(data[(y+32)*w:(y+160)*w],w)
    assert band[32*cw*3:]==shifted[:32*cw*3],('vertical seam',case,y);count+=32*cw*3
  stats.append({'synthetic_case':case,'overlap_channels_exact':count})
 # Whole 12MP layout coverage; constant expected output is independently known.
 # This is a coverage/runtime check, not original full-frame Phocus equivalence.
 w,h=4096,3072;cw,ch=w-64,h-64;source=array.array('H',[10000])*(w*128)
 start=time.monotonic();channels=0
 for y in range(0,ch,64):
  rows=min(64,ch-y);out=engine.band(source,w,0,rows)
  assert out.tobytes()==(b'\x10\x27'*len(out));channels+=len(out)
 elapsed=time.monotonic()-start
 result={'schema':'hasselblad-stage76-host-v1','status':'PASS_HOST_BANDS_AND_SEAMS','synthetic_only':True,
  'overlap_cases':stats,'overlap_channels_exact':sum(s['overlap_channels_exact'] for s in stats),
  'full_size_constant_coverage':{'raw':[w,h],'output':[cw,ch],'tiles':((cw+63)//64)*((ch+63)//64),'rgb16_channels_exact':channels,'host_seconds':elapsed,
  'phone_performance_measured':False,'original_full_frame_reference_compared':False},
  'border_policy':'actual sensor halo only; crop32 top/left and32or33 bottom/right',
  'device_tested':False,'capture_renderer_changed':False}
 (work/'STAGE76_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni',type=Path,required=True);a=p.parse_args();run(a.work.resolve(),a.jni.resolve())
