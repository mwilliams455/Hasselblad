#!/usr/bin/env python3
"""Parameter transport, stable settings and full-frame versus streaming sharpening."""
import argparse,ctypes,json,shutil,subprocess
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;AUDIT=HERE.parent;ROOT=AUDIT.parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args()
 work=a.work.resolve();work.mkdir(exist_ok=True,parents=True)
 cmd=['python3',str(AUDIT/'phocus_capture_stage87/check87.py'),'--work',str(work)]
 if a.jni_include:cmd+=['--jni-include',str(a.jni_include)]
 subprocess.run(cmd,check=True)
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-cp',str(work/'classes'),'-d',str(work/'classes'),str(HERE/'Stage91Check.java')],check=True)
 subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(work/'classes'),'com.particlesdevs.photoncamera.hasselblad.Stage91Check',str(work),str(work/'synthetic.hbc')],check=True)
 lib=ctypes.CDLL(str(work/'libhbsharp86.so'));ptr=ctypes.POINTER(ctypes.c_uint16)
 lib.hb85_sharpen14.argtypes=[ptr,ptr,ctypes.c_size_t,ctypes.c_size_t,ctypes.c_int,ctypes.c_double,ctypes.c_int,ctypes.c_int]
 total=0;cache={};cases=0
 for f in sorted(work.glob('*.actual.u16')):
  w,h,amount,noise,band=map(int,f.name.split('.')[0].split('_'));key=(w,h,amount,noise)
  if key not in cache:
   i=np.arange(w*h*3,dtype=np.int64);source=((i*73+(i//7)*193+17)&65535).astype(np.uint16)
   if amount==0:expected=source
   else:
    rgb14=source>>2;expected=np.empty_like(rgb14)
    assert lib.hb85_sharpen14(rgb14.ctypes.data_as(ptr),expected.ctypes.data_as(ptr),w,h,amount,1.,noise,10)==0
    expected<<=2
   cache[key]=expected
  actual=np.fromfile(f,dtype='<u2');assert np.array_equal(actual,cache[key]),f.name
  total+=actual.size;cases+=1
 result=json.loads((work/'STAGE91_JAVA.json').read_text())
 result.update(status='PASS_CONTROLS_INTEGRATION',whole_frame_comparisons=cases,rgb16_channels_compared=total,max_abs_difference=0,
  defaults_preserved=True,zero_strength_exact_bypass=True,settings_snapshot_tested=True,failed_commit_memory_rollback_tested=True,
  persistence_adapter='JVM preferences with memory/disk state; Android durability not device-tested',
  demosaic_is_test_adapter=True,preview_math_unchanged=True,sharpening_preview=False,device_tested=False)
 (work/'STAGE91_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
