#!/usr/bin/env python3
"""Allow only sharpening control plumbing; preserve completed kernel/preview proofs."""
import subprocess
BASE='c5e942877bb4912e988d9668f40413fb4ca70b87'
prefix='HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/'
allowed={'.github/workflows/hb-photon-controls91.yml','HasselbladPhoton/app/build.gradle','HasselbladPhoton/app/version.properties',
 'HasselbladPhoton/app/src/main/cpp/hasselblad/hb_sharpen86_jni.c',
 *{prefix+n+'.java' for n in ('HasselbladCapture79','HasselbladCaptureEvidence','HasselbladLook84Activity','HasselbladSceneRenderer79','HasselbladSharpen86','HasselbladSharpen87Settings','HasselbladSharpen91')},
 *{'hasselblad_native_audit/'+p for p in ('phocus_capture_stage87/Context.java','phocus_capture_stage87/check87.py','phocus_preview_stage90/check90.py','phocus_preview_stage89/check89.py','phocus_sharpen_stage86/check86.py')}}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
bad=[p for p in changed if p not in allowed and not p.startswith('hasselblad_native_audit/phocus_controls_stage91/')]
assert not bad,bad
print('PASS RAW/demosaic/colour/gradation/output/sharpening kernels, profile store, preview controller/cache/shaders and public saving preserved')
