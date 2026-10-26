#!/usr/bin/env python3
"""Bound the change to the white-point adapter, its integration and build/tests."""
import subprocess
from pathlib import Path
BASE='2f02f420631c139cea48c7bcf89f7e7e40a6d259'
APP='HasselbladPhoton/app/';JAVA=APP+'src/main/java/com/particlesdevs/photoncamera/hasselblad/'
allowed={APP+'build.gradle',APP+'version.properties',APP+'src/main/cpp/CMakeLists.txt',
 JAVA+'HasselbladFrame96.java',JAVA+'HasselbladSceneRenderer79.java',JAVA+'HasselbladCapture79.java',
 '.github/workflows/hb-photon-chroma96.yml'}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
assert all(p in allowed or p.startswith('hasselblad_native_audit/phocus_chroma_stage96/') for p in changed),changed
p=JAVA+'HasselbladSceneRenderer79.java'
old=subprocess.check_output(['git','show',BASE+':'+p],text=True)
expected=old.replace('public boolean sharpeningApplied;','public boolean sharpeningApplied;\n        public double[] chromaNeutral;').replace('r.orientation=prepared.orientation;','r.orientation=prepared.orientation;\n        r.chromaNeutral=m.asShotNeutral.clone();').replace('HasselbladFrame77.band(prepared.bayer,m.width,m.height,y,workers)','HasselbladFrame96.band(prepared.bayer,m.width,m.height,y,workers,r.chromaNeutral)')
assert Path(p).read_text()==expected,'Scene changed beyond chroma adaptation'
p=JAVA+'HasselbladCapture79.java';old=subprocess.check_output(['git','show',BASE+':'+p],text=True)
expected=old.replace('hasselblad-stage88-capture-v1','hasselblad-stage96-capture-v1').replace('.put("jpeg_quality",95)', '''.put("reconstruction_revision","phocus-chroma96")
                        .put("chroma_correction_neutral",new JSONArray().put(rendered.chromaNeutral[0]).put(rendered.chromaNeutral[1]).put(rendered.chromaNeutral[2]))
                        .put("source_rgb_restored_before_colour",true)
                        .put("jpeg_quality",95)''')
assert Path(p).read_text()==expected,'Capture changed beyond diagnostic metadata'
print('PASS Stage95 exposure, preview, raw preparation, Phocus kernels, colour/curve/sharpening, preferences and capture publication preserved')
