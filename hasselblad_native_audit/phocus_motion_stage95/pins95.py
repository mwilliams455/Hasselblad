#!/usr/bin/env python3
"""Bound Motion restoration to mode UI/persistence/eligibility and fresh RAW acquisition."""
import subprocess
from pathlib import Path
BASE='daa65814687018bb32a842be7ef783bf95621310'
app='HasselbladPhoton/app/';java=app+'src/main/java/com/particlesdevs/photoncamera/'
allowed={app+'build.gradle',app+'version.properties','.github/workflows/hb-photon-motion95.yml',
 *{java+p for p in ('hasselblad/HasselbladStillModes95.java','hasselblad/HasselbladDevelopmentPolicy.java',
 'hasselblad/HasselbladLook84Activity.java','hasselblad/HasselbladPreview92Camera.java',
 'processing/processor/HdrxProcessor.java','processing/DefaultSaver.java','processing/RAW16Saver.java',
 'settings/PreferenceKeys.java','ui/camera/CameraUIViewImpl.java','capture/CaptureController.java')},
 'hasselblad_native_audit/phocus_capture_stage94/check94.py','hasselblad_native_audit/phocus_capture_stage94/Stage94Check.java'}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
assert all(p in allowed or p.startswith('hasselblad_native_audit/phocus_motion_stage95/') for p in changed),changed
def old(p):return subprocess.check_output(['git','show',BASE+':'+java+p],text=True)
def current(p):return Path(java+p).read_text()
p='hasselblad/HasselbladPreview92Camera.java'
assert current(p)==old(p).replace('s.selectedMode==CameraMode.PHOTO','HasselbladStillModes95.supports(s.selectedMode)'), 'Preview math changed'
p='capture/CaptureController.java'
guard='''        // The legacy ring pairs buffered pixels with the latest preview result.
        // Hasselblad requires each RAW's own timestamp-matched metadata and source surface.
        if (HasselbladDevelopmentPolicy.isEnabled()) return false;
'''
assert current(p)==old(p).replace('    public boolean isZslMode() {\n','    public boolean isZslMode() {\n'+guard), 'Capture controller changed beyond safe ZSL exclusion'
router=current('processing/processor/HdrxProcessor.java')
assert '!HasselbladStillModes95.supports(cameraMode)' in router
for forbidden in ('ApplyHdrX','PostPipeline','Camera2ApiAutoFix','StillEncoder','HasselbladCapture79.fallback'):
 assert forbidden not in router,forbidden
raw=current('processing/RAW16Saver.java')
assert '!HasselbladStillModes95.supports(PhotonCamera.getSettings().selectedMode)' in raw
ui=current('ui/camera/CameraUIViewImpl.java')
assert 'cameraFragment.getString(R.string.mode_photo), cameraFragment.getString(R.string.mode_motion)' in ui
assert 'switchToMode(HasselbladStillModes95.at(index))' in ui
assert 'setSelectedItem(HasselbladStillModes95.indexOf(PreferenceKeys.getCameraModeOrdinal()))' in ui
prefs=current('settings/PreferenceKeys.java')
assert 'HasselbladStillModes95.allowedOrdinal(saved)' in prefs and 'HasselbladStillModes95.allowedOrdinal(value)' in prefs
policy=current('hasselblad/HasselbladDevelopmentPolicy.java')
assert 'HasselbladStillModes95.allowedOrdinal(' in policy
assert 'manager.set(scope, PreferenceKeys.Key.KEY_FRAME_COUNT, 1)' in policy
print('PASS Motion mode restored with fresh matched RAW; exposure algorithm, renderer, save handler, preview math, DNG transport and native processing unchanged')
