#!/usr/bin/env python3
"""Fail if Stage89 changes any saved-photo, exposure, RAW or native processing source."""
import subprocess
BASE='31189f98e9df99fac2988b42ecdcdb91811d2e92'
allowed={
    '.github/workflows/hb-photon-preview89.yml',
    'HasselbladPhoton/app/build.gradle','HasselbladPhoton/app/version.properties',
    'HasselbladPhoton/app/src/main/assets/shaders/preview/main_fs.glsl',
    'HasselbladPhoton/app/src/main/assets/shaders/preview/blur_oes_fs.glsl',
    'HasselbladPhoton/app/src/main/assets/shaders/preview/tone89.glsl',
    'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java',
    'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/GLPreview.java',
    'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/HasselbladLook84Activity.java',
    *{'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad/'+n+'.java' for n in
      ('HasselbladPreview89','HasselbladPreview89Loader','HasselbladPreview89Settings')}
}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
unexpected=[p for p in changed if p not in allowed and not p.startswith('hasselblad_native_audit/phocus_preview_stage89/')]
assert not unexpected,unexpected
print('PASS Stage88 saved-photo/exposure/native sources unchanged')
