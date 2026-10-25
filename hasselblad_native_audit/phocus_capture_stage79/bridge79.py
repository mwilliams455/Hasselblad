"""Exercise the actual Android metadata adapter with small JVM API/allocator/writer spies.

This checks parameter transport and resource ownership, not Android/native DNG IO.
The native writer is unchanged; its phone roundtrip remains a device acceptance test.
"""
from pathlib import Path
import shutil,subprocess
def run(root,work):
 src=work/'bridge79-src';classes=work/'bridge79-classes';src.mkdir(exist_ok=True);classes.mkdir(exist_ok=True)
 camera_keys=['SENSOR_INFO_COLOR_FILTER_ARRANGEMENT','SENSOR_INFO_WHITE_LEVEL','SENSOR_REFERENCE_ILLUMINANT1']
 definitions={
 'android/graphics/ImageFormat.java':'package android.graphics; public class ImageFormat { public static final int RAW_SENSOR=32; }',
 'android/graphics/Rect.java':'package android.graphics; public class Rect { public int left,top,right,bottom; public Rect(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;} }',
 'android/os/Build.java':'package android.os; public class Build {public static String MANUFACTURER="Synthetic",MODEL="Fixture";}',
 'android/util/Rational.java':'package android.util; public class Rational {double v;public Rational(int n,int d){v=(double)n/d;}public double doubleValue(){return v;}}',
 'android/hardware/camera2/params/ColorSpaceTransform.java':'package android.hardware.camera2.params; public class ColorSpaceTransform {public android.util.Rational getElement(int x,int y){return new android.util.Rational(y*3+x+1,10);}}',
 'android/hardware/camera2/params/BlackLevelPattern.java':'package android.hardware.camera2.params; public class BlackLevelPattern {public int getOffsetForIndex(int x,int y){return 64+y*2+x;}}',
 'android/hardware/camera2/params/LensShadingMap.java':'package android.hardware.camera2.params; public class LensShadingMap {public int getColumnCount(){return 3;}public int getRowCount(){return 2;}public int getGainFactorCount(){return 24;}public void copyGainFactors(float[] dst,int offset){for(int i=0;i<24;i++)dst[offset+i]=1+i*.01f;}}',
 'com/particlesdevs/photoncamera/BuildConfig.java':'package com.particlesdevs.photoncamera; public class BuildConfig {public static final String VERSION_NAME="test";}',
 'com/particlesdevs/photoncamera/processing/ImageFrame.java':'''package com.particlesdevs.photoncamera.processing;
 public class ImageFrame { public java.nio.ByteBuffer buffer; public int sourceRawWidth,sourceRawHeight,sourceRawFormat,sourceRowStride,sourcePixelStride,width,height,sourceRawBufferCapacity,sourceCopyOffsetBytes,cropOriginX,cropOriginY,packedBits; public boolean sourceBinned,fp16;public android.graphics.Rect sourceImageCropRect; }''',
 'com/particlesdevs/photoncamera/util/Allocator.java':'''package com.particlesdevs.photoncamera.util;public class Allocator {public static int allocations,frees;public static java.nio.ByteBuffer allocate(int n){allocations++;return java.nio.ByteBuffer.allocateDirect(n);}public static void free(java.nio.ByteBuffer b){frees++;}}'''
 }
 common='import android.graphics.Rect;import android.hardware.camera2.params.*;import android.util.Rational;import java.util.*;'
 for name,keys in [
  ('CameraCharacteristics', [('Integer',k) for k in camera_keys]+[('Byte','SENSOR_REFERENCE_ILLUMINANT2'),('BlackLevelPattern','SENSOR_BLACK_LEVEL_PATTERN')]+[('Rect',k) for k in ('SENSOR_INFO_ACTIVE_ARRAY_SIZE','SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE')]+[('ColorSpaceTransform','SENSOR_'+k+str(i)) for k in ('COLOR_TRANSFORM','FORWARD_MATRIX','CALIBRATION_TRANSFORM') for i in (1,2)]),
  ('CaptureResult',[('Integer',k) for k in ('SENSOR_DYNAMIC_WHITE_LEVEL','SENSOR_SENSITIVITY')]+[('float[]','SENSOR_DYNAMIC_BLACK_LEVEL'),('Rational[]','SENSOR_NEUTRAL_COLOR_POINT'),('LensShadingMap','STATISTICS_LENS_SHADING_CORRECTION_MAP'),('Long','SENSOR_EXPOSURE_TIME')]+[('Float',k) for k in ('LENS_APERTURE','LENS_FOCAL_LENGTH')])]:
  body='package android.hardware.camera2;'+common+'public class '+name+' {public static class Key<T>{} public Map<Key<?>,Object> values=new HashMap<>(); @SuppressWarnings("unchecked") public <T>T get(Key<T> key){return (T)values.get(key);} public <T>void set(Key<T> key,T value){values.put(key,value);}'
  body+='public static final int SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGGB=0;'
  body+=''.join('public static final Key<'+ty+'> '+key+'=new Key<>();' for ty,key in keys)+'}'
  definitions['android/hardware/camera2/'+name+'.java']=body
 setters={'boolean':['Compression','Binning'],'int':['BitsPerSample','CFAPattern','Orientation'],
  'double':['WhiteLevel','ExposureTime','Aperture','FocalLength'],'short[]':['BlackLevel'],
  'short':['CalibrationIlluminant1','CalibrationIlluminant2','Iso'],
  'double[]':['ColorMatrix1','ColorMatrix2','ForwardMatrix1','ForwardMatrix2','CameraCalibration1','CameraCalibration2','AsShotNeutral','AnalogBalance'],
  'String':['Make','Model','UniqueCameraModel','DateTime','Software','Description']}
 writer='''package com.particlesdevs.photoncamera.processing;import java.util.*;import java.nio.*;import java.io.*;
 public class DngCreator {public static DngCreator last;public static boolean failWrite;public boolean closed;public Map<String,Object> values=new HashMap<>();public DngCreator(){last=this;}
 public void close(){closed=true;}public void writeBuffer(OutputStream out,ByteBuffer data,int w,int h){byte[] b=new byte[w*h*2];data.get(b);try{if(failWrite)throw new IOException("injected");out.write(b);}catch(IOException e){throw new RuntimeException(e);}}
 public void setGainMap(float[] gain,int l,int t,int r,int b,int w,int h){values.put("GainMap",gain.clone());values.put("GainArea",new int[]{l,t,r,b,w,h});}'''
 writer+=''.join('public void set'+name+'('+ty+' v){values.put("'+name+'",v);}' for ty,names in setters.items() for name in names)+'}'
 definitions['com/particlesdevs/photoncamera/processing/DngCreator.java']=writer
 for name,body in definitions.items():
  path=src/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
 java=root/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 sources=list(src.rglob('*.java'))+[java/'HasselbladDngBridge79.java',java/'HasselbladRawLayout79.java',Path(__file__).with_name('Stage79BridgeCheck.java')]
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,sources)],check=True)
 subprocess.run(['java','-cp',str(classes),'Stage79BridgeCheck',str(work)],check=True)
