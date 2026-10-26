#!/usr/bin/env python3
"""Bound the fix to fractional original black metadata, writer integration and tests."""
import hashlib,re,subprocess
from pathlib import Path
BASE='f05ffa697d8066db625f0af91d83f76caf12f245'
app='HasselbladPhoton/app/'
allowed={'.github/workflows/hb-photon-preview93.yml',app+'build.gradle',app+'version.properties',
 *{app+'src/main/cpp/'+p for p in ['CMakeLists.txt','dngCreator.cpp','dngCreator.h','deps/tiny_dng_writer.h']},
 *{app+'src/main/java/com/particlesdevs/photoncamera/'+p for p in ['hasselblad/HasselbladDngBridge79.java','processing/DngCreator.java']},
 'hasselblad_native_audit/phocus_capture_stage79/bridge79.py','hasselblad_native_audit/phocus_capture_stage79/Stage79BridgeCheck.java'}
changed=subprocess.check_output(['git','diff','--name-only',BASE,'--'],text=True).splitlines()
assert all(p in allowed or p.startswith('hasselblad_native_audit/phocus_preview_stage93/') for p in changed),changed
path=app+'src/main/cpp/deps/tiny_dng_writer.h';old=subprocess.check_output(['git','show',BASE+':'+path],text=True);new=Path(path).read_text()
def outside(source):
 a=source.index('bool DNGImage::SetBlackLevelRational(');b=source.index('bool DNGImage::SetWhiteLevelRational(',a);return source[:a]+source[b:]
assert outside(old)==outside(new),'unrelated retained TIFF writer changes'
sha=hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert 'tiny_dng_writer.h '+sha in Path(app+'src/main/cpp/CMakeLists.txt').read_text()
print('PASS preview/exposure/RAW reader/demosaic/colour/film/finishing/sharpening/publication unchanged; TIFF writer edit limited to BlackLevel rational setter')
