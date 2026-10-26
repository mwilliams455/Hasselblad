#!/usr/bin/env python3
"""Stage90 may change selection invalidation, not RAW/capture/shader pixel processing."""
import subprocess
BASE='d45ef1c1e62e0204266b8e80c20649d6cd5a1814'
prefix='HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/'
allowed={
    '.github/workflows/hb-photon-preview90.yml',
    'HasselbladPhoton/app/build.gradle','HasselbladPhoton/app/version.properties',
    prefix+'ui/camera/views/viewfinder/MainRenderer.java',
    prefix+'ui/camera/views/viewfinder/GLPreview.java',
    *{prefix+'hasselblad/'+n+'.java' for n in ('HasselbladLook84Activity','HasselbladLookStore84',
        'HasselbladPreview89Settings','HasselbladPreview90Changes','HasselbladPreview90Controller','HasselbladPreview90Cache')},
    'hasselblad_native_audit/phocus_look_stage84/check84.py',
    'hasselblad_native_audit/phocus_preview_stage89/check89.py'
}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
unexpected=[p for p in changed if p not in allowed and not p.startswith('hasselblad_native_audit/phocus_preview_stage90/')]
assert not unexpected,unexpected
print('PASS RAW/capture/native/tone-table/shader pixel sources unchanged')
