#!/usr/bin/env python3
"""Stage92 changes preview ownership, not the saved-photo pixel pipeline."""
import subprocess
BASE='a1b60c1dda03d93133919df4022f83767f3a336b'
root='HasselbladPhoton/app/'
java=root+'src/main/java/com/particlesdevs/photoncamera/'
allowed={'.github/workflows/hb-photon-preview92.yml',root+'build.gradle',root+'version.properties',root+'src/main/assets/shaders/preview/colour92.glsl',
 *{java+n+'.java' for n in ['capture/CaptureController','ui/camera/views/viewfinder/MainRenderer','ui/camera/views/viewfinder/GLPreview',
 'hasselblad/HasselbladCaptureEvidence','hasselblad/HasselbladLook84Activity','hasselblad/HasselbladPreview92','hasselblad/HasselbladPreview92Camera','hasselblad/HasselbladPreview92Worker']}}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
bad=[p for p in changed if p not in allowed and not p.startswith('hasselblad_native_audit/phocus_preview_stage92/')]
assert not bad,bad
# Limit integration edits in the large capture controller to preview request construction/callback/lifecycle.
old=subprocess.check_output(['git','show',BASE+':'+java+'capture/CaptureController.java'],text=True)
from pathlib import Path
new=Path(java+'capture/CaptureController.java').read_text()
start=new.index('    private final com.particlesdevs.photoncamera.hasselblad.HasselbladPreview92Camera preview92')
end=new.index('    public void rebuildPreviewBuilder()',start)
new=new[:start]+new[end:]
new=new.replace('buildPreview92()','mPreviewRequestBuilder.build()').replace('        preview92.close();\n','').replace('            if(session==mCaptureSession)preview92.result(CaptureController.this,request,result,surface);\n','')
assert new==old,'unexpected capture processing edits'
old=subprocess.check_output(['git','show',BASE+':'+java+'hasselblad/HasselbladCaptureEvidence.java'],text=True)
new=Path(java+'hasselblad/HasselbladCaptureEvidence.java').read_text().replace('        document.put("preview92_status", HasselbladPreview92Camera.status());\n','')
assert new==old,'unexpected still metadata edits'
print('PASS saved RAW/demosaic/colour/finishing/sharpening/exposure selection/profile storage/publication sources unchanged; capture hooks limited to preview and one diagnostic field')
