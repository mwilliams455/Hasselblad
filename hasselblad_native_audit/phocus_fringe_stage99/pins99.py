#!/usr/bin/env python3
"""Allow only the new correction/stream and version metadata above Stage98."""
import subprocess
from pathlib import Path
BASE='9aebd5059f0da0476fd8328743e0107c44d5bf83'
APP='HasselbladPhoton/app/';JAVA=APP+'src/main/java/com/particlesdevs/photoncamera/hasselblad/'
allowed={APP+'build.gradle',APP+'version.properties',APP+'src/main/cpp/CMakeLists.txt',JAVA+'HasselbladFrame99.java',JAVA+'HasselbladSceneRenderer79.java',JAVA+'HasselbladCapture79.java','.github/workflows/hb-photon-fringe99.yml'}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
assert all(p in allowed or p.startswith('hasselblad_native_audit/phocus_fringe_stage99/') for p in changed),changed
for file in ['HasselbladSceneRenderer79.java','HasselbladCapture79.java']:
 p=JAVA+file;old=subprocess.check_output(['git','show',BASE+':'+p],text=True)
 if file.startswith('HasselbladScene'):
  expected=old.replace('        try {\n            for (int y=', '        HasselbladFrame99.Stream fringe=new HasselbladFrame99.Stream(prepared.bayer,m.width,m.height,workers,r.chromaNeutral);\n        try {\n            for (int y=').replace('HasselbladFrame97.band(prepared.bayer,m.width,m.height,y,workers,r.chromaNeutral)','fringe.band(y)').replace('}finally{if(sharp!=null)sharp.abort();}','}finally{fringe.abort();if(sharp!=null)sharp.abort();}')
 else:expected=old.replace('hasselblad-stage97-capture-v1','hasselblad-stage99-capture-v1').replace('phocus-edges97','phocus-fringe99')
 assert Path(p).read_text()==expected,p
print('PASS original reconstruction, RAW prep, colour/profile/sharpening, preview, Photo/Motion and publication preserved')
