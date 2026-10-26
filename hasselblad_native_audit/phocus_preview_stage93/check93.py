#!/usr/bin/env python3
"""Actual Java Camera2 bridge -> production JNI DNG writer -> production RAW preparation.

Only Android camera data/allocator/logging and unused Parameters are test doubles.
No demosaic, colour, preview math or private data is changed or required.
"""
import argparse,hashlib,importlib.util,json,shutil,struct,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];AUDIT=HERE.parent
BASE='f05ffa697d8066db625f0af91d83f76caf12f245'
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--jni-include',type=Path);a=p.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
cpp=ROOT/'HasselbladPhoton/app/src/main/cpp';java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera'
compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main'];jdk=Path(shutil.which('javac') or shutil.which('java')).resolve().parents[1];jni=a.jni_include or jdk/'include'
spec=importlib.util.spec_from_file_location('bridge79',AUDIT/'phocus_capture_stage79/bridge79.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter);adapter.run(ROOT,work)
stubs=work/'bridge79-src';classes=work/'classes';classes.mkdir(exist_ok=True)
# Replace only the writer spy with the actual production Java wrapper and JNI.
(stubs/'com/particlesdevs/photoncamera/processing/DngCreator.java').unlink()
build=stubs/'com/particlesdevs/photoncamera/BuildConfig.java';build.write_text(build.read_text().replace('public static final String VERSION_NAME="test";','public static final String VERSION_NAME="test";public static final int VERSION_CODE=1;'))
build=stubs/'android/os/Build.java';build.write_text(build.read_text().replace('MANUFACTURER="Synthetic"','BRAND="Synthetic",MANUFACTURER="Synthetic"'))
files={
 'android/media/Image.java':'package android.media;public class Image {public int getWidth(){return 0;}public int getHeight(){return 0;}public Plane[] getPlanes(){return null;}public static class Plane {public java.nio.ByteBuffer getBuffer(){return null;}}}',
 'com/particlesdevs/photoncamera/processing/render/Parameters.java':'''package com.particlesdevs.photoncamera.processing.render;
 public class Parameters {
 public float[] blackLevel,ColorMatrix1,ColorMatrix2,ForwardTransform1,ForwardTransform2,calibrationTransform1,calibrationTransform2,whitePoint,gainMap;
 public int iso,whiteLevel,calibrationIlluminant1,calibrationIlluminant2,cfaPattern,cameraRotation;
 public double exposureTime,focalLength,aperture;public android.graphics.Rect sensorPix;public Point mapSize;
 public Noise noiseModeler;public static class Point{public int x,y;}public static class Pair{public double first,second;}
 public static class Noise{public Object baseModel;public Pair[] computeModel;}}
'''}
for name,body in files.items():f=stubs/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(body)
# Identity gain map makes the black/white normalization oracle independent and exact.
f=stubs/'android/hardware/camera2/params/LensShadingMap.java';f.write_text(f.read_text().replace('1+i*.01f','1'))
units=[java/'processing/DngCreator.java',*[java/('hasselblad/'+n+'.java') for n in ['HasselbladDngBridge79','HasselbladRawLayout79','HasselbladDngTileReader']]]
subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,stubs.rglob('*.java')),*map(str,units),str(HERE/'Stage93Check.java')],check=True)
headers=work/'headers/android';headers.mkdir(parents=True,exist_ok=True)
(headers/'log.h').write_text('#pragma once\n#define ANDROID_LOG_DEBUG 3\n#define ANDROID_LOG_ERROR 6\nstatic inline int __android_log_print(int,const char*,const char*,...){return 0;}\n')
common=['g++','-std=c++17','-O2','-fPIC','-shared','-pthread','-I'+str(work/'headers'),'-I'+str(cpp/'deps'),'-I'+str(jni),'-I'+str(jni/'linux'),'-ldl','-Wl,--no-undefined']
subprocess.run(common+[str(cpp/'dngCreator.cpp'),'-o',str(work/'libdngCreator.so')],check=True)
subprocess.run(['java','-Djava.library.path='+str(work),'-cp',str(classes),'Stage93Check',str(work)],check=True)
# Compile the unchanged Stage92 writer and compare deterministic legacy exports byte-for-byte.
old=work/'legacy';old.mkdir(exist_ok=True)
for rel in ['dngCreator.cpp','dngCreator.h','dngWhiteLevel.h','deps/tiny_dng_writer.h']:
 target=old/rel;target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(subprocess.check_output(['git','show',BASE+':HasselbladPhoton/app/src/main/cpp/'+rel],cwd=ROOT))
subprocess.run(common+[str(old/'dngCreator.cpp'),'-o',str(old/'libdngCreator.so')],check=True)
subprocess.run(['java','-Djava.library.path='+str(old),'-cp',str(classes),'Stage93Check',str(old),'legacy'],check=True)
for filename in ['legacy-uncompressed.dng','legacy-compressed.dng','legacy-binned.dng','legacy-10bit.dng']:
 assert (work/filename).read_bytes()==(old/filename).read_bytes(),filename
# Independent TIFF parser: inspect tag type/count/rationals and raw bytes, rather than trusting the Java reader alone.
def tiff(path):
 data=path.read_bytes();assert data[:4]==b'II*\0';offset=struct.unpack_from('<I',data,4)[0];tags={}
 for i in range(struct.unpack_from('<H',data,offset)[0]):
  tag,typ,count,value=struct.unpack_from('<HHII',data,offset+2+12*i);size={1:1,2:1,3:2,4:4,5:8,7:1,9:4,10:8,12:8}[typ]*count
  tags[tag]=(typ,count,data[offset+2+12*i+8:offset+2+12*i+12] if size<=4 else data[value:value+size])
 return data,tags
manifest=json.loads((work/'roundtrips.json').read_text());channels=raw_samples=0
for entry in manifest:
 data,tags=tiff(work/entry['file']);typ,count,b=tags[50714];assert count==4 and typ==(5 if entry['fractional'] else 3)
 if typ==5:
  values=struct.unpack('<8I',b);black=[values[2*i]/values[2*i+1] for i in range(4)];assert all(values[2*i+1]>0 for i in range(4))
 else:black=list(struct.unpack('<4H',b[:8]))
 assert black==entry['black'],(entry,black);channels+=4
 assert tags[50713][:2]==(3,2) and struct.unpack('<2H',tags[50713][2])==(2,2)
 assert tags[277][:2]==(3,1) and struct.unpack('<H',tags[277][2][:2])[0]==1
 assert tags[50717][0]==4 and struct.unpack('<I',tags[50717][2])[0]==entry['white']
 offset=struct.unpack('<I',tags[273][2])[0];count=struct.unpack('<I',tags[279][2])[0]
 raw=struct.unpack('<'+str(count//2)+'H',data[offset:offset+count]);assert len(raw)==128*128
 assert all(value==(i*37)%entry['white'] for i,value in enumerate(raw));raw_samples+=len(raw)
receipt=json.loads((work/'STAGE93_JAVA_CHECKS.json').read_text());receipt.update(status='PASS_FRACTIONAL_BLACK',native_writer=True,roundtrip_files=len(manifest),black_channels_exact=channels,unmodified_RAW_samples=raw_samples,legacy_files_byte_exact=4,device_tested=False,preview_math_changed=False,demosaic_retested=False,private_profile_or_photo_used=False)
(work/'STAGE93_HOST_VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
