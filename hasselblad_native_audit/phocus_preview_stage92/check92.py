#!/usr/bin/env python3
"""Production inverse/JNI cube, bounded worker, Camera2 adapter and GLES tests."""
import argparse,importlib.util,json,shutil,subprocess
from pathlib import Path
from android92 import write_stubs
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];AUDIT=HERE.parent
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args()
work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
command=['python3',str(AUDIT/'phocus_preview_stage90/check90.py'),'--work',str(work)]
if a.jni_include:command+=['--jni-include',str(a.jni_include)]
subprocess.run(command,check=True)
classes=work/'classes';java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
context=work/'stubs/Context.java';context.write_text(context.read_text().replace('public final class Context {','public final class Context { public Context getApplicationContext(){return this;}'))
stubs=write_stubs(work/'android')
compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
units=['HasselbladPreview92','HasselbladPreview92Worker','HasselbladPreview92Camera','HasselbladIlluminant56','HasselbladRawStream']
subprocess.run(compiler+['--release','17','-cp',str(classes),'-d',str(classes),str(context),*stubs,*[str(java/(u+'.java')) for u in units],str(HERE/'Stage92Check.java')],check=True)
subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'com.particlesdevs.photoncamera.hasselblad.Stage92Check',str(work)],check=True)
from gpu92 import check_gpu
r=json.loads((work/'STAGE92_HOST_VALIDATION.json').read_text());r['gpu']=check_gpu(ROOT/'HasselbladPhoton/app/src/main/assets/shaders/preview',work)
r['device_tested']=False;r['camera_api_test_adapter']='Deterministic Camera2 doubles; no claim of HAL/device validation'
(work/'STAGE92_HOST_VALIDATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
