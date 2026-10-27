#!/usr/bin/env python3
"""Restrict application changes to the Stage97 adapter and revision metadata."""
import subprocess
from pathlib import Path
BASE='1e227b04cb95f732b6aaf41cd19719c790160a76'
APP='HasselbladPhoton/app/';JAVA=APP+'src/main/java/com/particlesdevs/photoncamera/hasselblad/'
allowed={APP+'build.gradle',APP+'version.properties',APP+'src/main/cpp/CMakeLists.txt',
 JAVA+'HasselbladFrame97.java',JAVA+'HasselbladSceneRenderer79.java',JAVA+'HasselbladCapture79.java',
 '.github/workflows/hb-photon-edges97.yml'}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
assert all(p in allowed or p.startswith('hasselblad_native_audit/phocus_edges_stage97/') for p in changed),changed
for file in ['HasselbladSceneRenderer79.java','HasselbladCapture79.java']:
    p=JAVA+file;old=subprocess.check_output(['git','show',BASE+':'+p],text=True)
    expected=old.replace('HasselbladFrame96.band','HasselbladFrame97.band') if file.startswith('HasselbladScene') else old.replace('hasselblad-stage96-capture-v1','hasselblad-stage97-capture-v1').replace('phocus-chroma96','phocus-edges97')
    assert Path(p).read_text()==expected,p
print('PASS Stage96 kernels, RAW preparation, colour, sharpening, preview, Photo/Motion routing, preferences and publication preserved')
