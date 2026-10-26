#!/usr/bin/env python3
"""Actual Java/JNI stream against independently partitioned Stage85 full-frame reference."""
import argparse,hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];AUDIT=HERE.parent
sys.path.insert(0,str(AUDIT/'phocus_sharpen_stage85'))
from check85 import Port

def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path)
 p.add_argument('--private-profiles',nargs='*',type=Path,default=[]);a=p.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
 src=ROOT/'HasselbladPhoton/app/src/main';java=src/'java/com/particlesdevs/photoncamera/hasselblad';classes=work/'classes';classes.mkdir(exist_ok=True)
 javac=shutil.which('javac');jdk=Path(javac or shutil.which('java')).resolve().parents[1];jni=a.jni_include or jdk/'include'
 assert (jni/'jni.h').is_file(), 'JNI headers required'
 compiler=[javac] if javac else ['java','com.sun.tools.javac.Main']
 units=['HasselbladSharpen91','HasselbladSharpen86','HasselbladProfile43','HasselbladRenderer42']
 subprocess.run(compiler+['--release','17','-d',str(classes),*[str(java/(n+'.java')) for n in units],str(HERE/'Stage86Check.java')],check=True)
 includes=[jni,jni/'linux',AUDIT/'phocus_port_stage42/src',AUDIT/'isp_dng_stage18/src',AUDIT/'isp_colour_stage19/src',AUDIT/'phocus_highlight_stage53',AUDIT/'phocus_post_stage55',AUDIT/'phocus_finish_stage88',AUDIT/'phocus_sharpen_stage85']
 common=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off','-fPIC','-shared','-pthread',*['-I'+str(x) for x in includes]]
 old=[src/'cpp/hasselblad/hb_renderer42_jni.c',AUDIT/'phocus_port_stage42/src/hb42_colour.c',AUDIT/'isp_dng_stage18/src/hb_dng_pcs_bridge.c',AUDIT/'isp_colour_stage19/src/hb_colour_stage19.c',AUDIT/'phocus_highlight_stage53/highlight53.c',AUDIT/'phocus_post_stage55/post55.c',AUDIT/'phocus_finish_stage88/finish88.c']
 for name,sources in [('hbsharp86',[src/'cpp/hasselblad/hb_sharpen86_jni.c',AUDIT/'phocus_sharpen_stage85/sharpen85.c']),('hasselblad_renderer42_jni',old)]:
  subprocess.run(common+list(map(str,sources))+['-Wl,--no-undefined','-lm','-o',str(work/('lib'+name+'.so'))],check=True)
 port=Port(work/'reference');rng=np.random.default_rng(86);cases=[]
 for index,(w,h) in enumerate(((1,1),(7,2),(8,63),(9,64),(33,65),(65,127),(128,128),(256,130),(4032,130))):
  x=rng.integers(0,65536,(h,w,3),dtype=np.uint16);expected=(port.render(x>>2).astype(np.uint16)<<2)
  stem='case'+str(index);x.astype('<u2').tofile(work/(stem+'.input'));expected.astype('<u2').tofile(work/(stem+'.expected'));cases.append(f'{stem} {w} {h}')
 (work/'cases.txt').write_text('\n'.join(cases)+'\n')
 # Synthetic finishing-enabled profile; no vendor payload.
 data=b'HB55LUT1'+struct.pack('<6i',2,2,4000,0,1,0)
 values=[0.]*38
 for i in (22,23,24,25,37):values[i]=1.
 data+=struct.pack('<38d',*values)+bytes(64)+np.arange(65536,dtype='<f4').tobytes()
 data+=struct.pack('<4i10d',1,0,2,1,1,0,0,0,1,0,0,0,1,2.2)
 (work/'synthetic.hbc').write_bytes(data+hashlib.sha256(data).digest())
 subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'com.particlesdevs.photoncamera.hasselblad.Stage86Check',str(work),*map(str,a.private_profiles)],check=True)
 from diagnostics86 import check
 diagnostic=check(work,compiler)
 result={'schema':'hasselblad-stage86-host-v1','status':'PASS_STREAMING_AND_DIAGNOSTICS','jni':json.loads((work/'STAGE86_JNI_VALIDATION.json').read_text()),'diagnostics':diagnostic,'original_native_kernel_retested':False,'prior_stage85_native_proof_retained':True,'demosaic_retested':False,'device_tested':False}
 (work/'STAGE86_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
