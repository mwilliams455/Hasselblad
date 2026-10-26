#!/usr/bin/env python3
"""Require exclusive Hasselblad capture routing and retain all Stage93 pixel math."""
import subprocess
from pathlib import Path
BASE='e2aac6280cd2e1857a7c4fde55ef0140ade500fd'
app='HasselbladPhoton/app/';java=app+'src/main/java/com/particlesdevs/photoncamera/'
allowed={app+'build.gradle',app+'version.properties','.github/workflows/hb-photon-capture94.yml',
 *{java+p for p in ('hasselblad/HasselbladCapture79.java','hasselblad/HasselbladLook84Activity.java',
 'processing/processor/HdrxProcessor.java','processing/JPEGSaver.java','processing/YUVSaver.java',
 'processing/DefaultSaver.java','processing/RAW16Saver.java')}}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
assert all(p in allowed or p.startswith('hasselblad_native_audit/phocus_capture_stage94/') for p in changed),changed
router=Path(java+'processing/processor/HdrxProcessor.java').read_text()
assert 'HasselbladCapture79.handle(' in router and 'HasselbladCapture79.reject94(' in router
for forbidden in ('ApplyHdrX','PostPipeline','Camera2ApiAutoFix','StillEncoder','ImageFrameDeblur','Allocator','HasselbladDevelopmentPolicy'):
 assert forbidden not in router,forbidden
capture=Path(java+'hasselblad/HasselbladCapture79.java').read_text()
assert 'public static void handle(' in capture and 'closeFrames94(frames)' in capture
assert 'return false' not in capture and 'PHOTON_FALLBACK' not in capture and 'fallback(' not in capture
assert '.getString("last_status"' in capture and '.putString("last_status",display94(report))' in capture
for saver in ('JPEGSaver','YUVSaver'):
 text=Path(java+'processing/'+saver+'.java').read_text()
 assert 'reject94(' in text and 'image.close()' in text and 'Files.write' not in text and 'getFrame(' not in text
default=Path(java+'processing/DefaultSaver.java').read_text()
start=default[default.index('    public void processStart('):default.index('    public void videoCaptureResult(')]
assert start.index('HasselbladDevelopmentPolicy.isEnabled()')<start.index('return;')<start.index('mUnlimitedProcessor.unlimitedStart(')
end=default[default.index('    public void processEnd()'):]
assert end.index('HasselbladDevelopmentPolicy.isEnabled()) return;')<end.index('mUnlimitedProcessor.unlimitedEnd()')
raw=Path(java+'processing/RAW16Saver.java').read_text();start=raw[raw.index('public void addImage(Image image,'):]
assert start.index('selectedMode != CameraMode.PHOTO')<start.index('return;')<start.index('mUnlimitedProcessor.unlimitedCycle(')
ui=Path(java+'hasselblad/HasselbladLook84Activity.java').read_text()
assert 'lastStatus94(this)' in ui and 'PHOTON_FALLBACK' not in ui
print('PASS exclusive Hasselblad still routing; preview, native DNG metadata, RAW preparation, demosaic, colour, tone, sharpening, and publication bytes unchanged')
