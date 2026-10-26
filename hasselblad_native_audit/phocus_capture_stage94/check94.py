#!/usr/bin/env python3
"""Exercise production capture orchestration with injected Android/I/O/renderer failures.

Pixel kernels and native DNG transport are unchanged from Stage93; this tests routing,
ownership, reporting, callback completion and publication decisions, not image quality.
"""
import argparse,json,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PACKAGE='com.particlesdevs.photoncamera'
STUBS={
'android/content/Context.java':'''package android.content;import java.io.*;import java.util.*;
public class Context {public static final int MODE_PRIVATE=0;final File cache;final Map<String,Prefs> prefs=new HashMap<>();
 public Context(File f){cache=f;f.mkdirs();}public File getCacheDir(){return cache;}
 public Prefs getSharedPreferences(String n,int m){return prefs.computeIfAbsent(n,k->new Prefs());}
 public static class Prefs {final Map<String,Object> values=new HashMap<>();public boolean getBoolean(String k,boolean f){return (Boolean)values.getOrDefault(k,f);}public String getString(String k,String f){return (String)values.getOrDefault(k,f);}public Editor edit(){return new Editor(this);}}
 public static class Editor {final Prefs p;Editor(Prefs p){this.p=p;}public Editor putString(String k,String v){p.values.put(k,v);return this;}public Editor putBoolean(String k,boolean v){p.values.put(k,v);return this;}public void apply(){}public boolean commit(){return true;}}
}''',
'android/graphics/Bitmap.java':'''package android.graphics;import java.io.*;import com.particlesdevs.photoncamera.hasselblad.Test94;
public class Bitmap {public enum Config{ARGB_8888}public enum CompressFormat{JPEG}public static Bitmap createBitmap(int w,int h,Config c){return new Bitmap();}public void setPixels(int[] a,int o,int s,int x,int y,int w,int h){}public void recycle(){Test94.recycled++;}
 public boolean compress(CompressFormat f,int q,OutputStream out)throws IOException{Test94.step("encode");if(Test94.fail.equals("encode_false"))return false;out.write(new byte[]{1,2,3});return true;}}
''',
'androidx/exifinterface/media/ExifInterface.java':'''package androidx.exifinterface.media;import java.io.*;import com.particlesdevs.photoncamera.hasselblad.Test94;public class ExifInterface {public static final String TAG_ORIENTATION="o",TAG_COLOR_SPACE="c";public void setAttribute(String k,String v){}public void saveAttributes()throws IOException{Test94.step("exif");}}''',
'android/media/Image.java':'''package android.media;public class Image {public int closes;public void close(){closes++;}}''',
'org/json/JSONObject.java':'''package org.json;import java.util.*;public class JSONObject {public static final Object NULL=null;final Map<String,Object> data=new LinkedHashMap<>();public JSONObject(){}public JSONObject(Map<?,?> m){m.forEach((k,v)->data.put(k.toString(),v));}public JSONObject put(String k,Object v){data.put(k,v);return this;}public String optString(String k){return String.valueOf(data.getOrDefault(k,""));}public int optInt(String k){return ((Number)data.getOrDefault(k,0)).intValue();}public boolean optBoolean(String k){return Boolean.TRUE.equals(data.get(k));}public String toString(int n){return data.toString();}public String toString(){return data.toString();}}''',
'org/json/JSONArray.java':'''package org.json;public class JSONArray {final java.util.List<Object> data=new java.util.ArrayList<>();public JSONArray put(Object v){data.add(v);return this;}public String toString(){return data.toString();}}''',
PACKAGE+'.BuildConfig':'''public class BuildConfig {public static final String VERSION_NAME="0.1-hb-capture94",HB88_SOURCE="host-fixture";public static final int VERSION_CODE=27233;}''',
PACKAGE+'.util.Log':'''public class Log {public static void e(String t,String m,Throwable e){} }''',
PACKAGE+'.api.CameraMode':'''public enum CameraMode {PHOTO,NIGHT,UNLIMITED,RAWVIDEO}''',
PACKAGE+'.control.GyroBurst':'''public class GyroBurst {}''',
PACKAGE+'.capture.CaptureController':'''public class CaptureController {public static final int RAW_FORMAT=32;}''',
PACKAGE+'.app.PhotonCamera':'''public class PhotonCamera {public static android.content.Context context;public static final Settings settings=new Settings();public static android.content.Context getAppContext(){return context;}public static Settings getSettings(){return settings;}public static class Settings {public boolean heic;public boolean isHeicSave(){return heic;}}}''',
PACKAGE+'.processing.ImageFrame':'''public class ImageFrame {public int closes;public boolean closeThrows;public void close(){closes++;if(closeThrows)throw new IllegalStateException("close fixture");}}''',
PACKAGE+'.processing.DefaultSaver':'''public class DefaultSaver {protected final ProcessingEventsListener processingEventsListener;protected processorDummy unused;public boolean bufferLock=true;protected final com.particlesdevs.photoncamera.processing.processor.ProcessorBase.ProcessingCallback processingCallback=new com.particlesdevs.photoncamera.processing.processor.ProcessorBase.ProcessingCallback(){public void onStarted(){}public void onFinished(){}public void onFailed(){}};public DefaultSaver(ProcessingEventsListener e){processingEventsListener=e;}public void addImage(android.media.Image image){}static class processorDummy{}}''',
PACKAGE+'.processing.processor.ProcessorBase':'''public class ProcessorBase {protected java.nio.file.Path dngFile,imageFile;protected com.particlesdevs.photoncamera.api.ParseExif.ExifData exifData;protected int cameraRotation;protected android.hardware.camera2.CameraCharacteristics characteristics;protected android.hardware.camera2.CaptureResult captureResult;protected android.hardware.camera2.CaptureRequest captureRequest;protected ProcessingCallback callback;protected final com.particlesdevs.photoncamera.processing.ProcessingEventsListener processingEventsListener;public ProcessorBase(com.particlesdevs.photoncamera.processing.ProcessingEventsListener e){processingEventsListener=e;}public interface ProcessingCallback{void onStarted();void onFailed();void onFinished();}}''',
PACKAGE+'.api.ParseExif':'''public class ParseExif {public static class ExifData {public String PHOTOGRAPHIC_SENSITIVITY,EXPOSURE_TIME,F_NUMBER,FOCAL_LENGTH,COMPRESSION,COLOR_SPACE,IMAGE_WIDTH,IMAGE_LENGTH,IMAGE_DESCRIPTION;}public static androidx.exifinterface.media.ExifInterface setAllAttributes(java.io.File f,ExifData e){return new androidx.exifinterface.media.ExifInterface();}}''',
PACKAGE+'.hasselblad.Test94':'''public class Test94 {public static String fail="";public static int renders,writes,recycled,bridgeCloses,rawCalls,jpegCalls;public static boolean diagnostics;
 public static void reset(String f,boolean d){fail=f;diagnostics=d;renders=writes=recycled=bridgeCloses=rawCalls=jpegCalls=0;}
 public static void step(String s)throws java.io.IOException {if(fail.equals(s))throw new java.io.IOException(s+" fixture");if(s.equals("render")&&fail.equals("linkage"))throw new UnsatisfiedLinkError("native fixture");if(s.equals("render")&&fail.equals("memory"))throw new OutOfMemoryError("memory fixture");}}
''',
PACKAGE+'.hasselblad.HasselbladSharpen91':'''public class HasselbladSharpen91 {public boolean enabled=true;public int amount=138,noise=11;public String description(){return "fixture";}}''',
PACKAGE+'.hasselblad.HasselbladCaptureEvidence':'''public class HasselbladCaptureEvidence {public static HasselbladCaptureEvidence begin(java.util.ArrayList<com.particlesdevs.photoncamera.processing.ImageFrame> f,android.hardware.camera2.CameraCharacteristics c,android.hardware.camera2.CaptureResult r,android.hardware.camera2.CaptureRequest q)throws java.io.IOException{Test94.step("snapshot");return Test94.fail.equals("missing_evidence")?null:new HasselbladCaptureEvidence();}public boolean diagnosticsEnabled86(){return Test94.diagnostics;}public HasselbladSharpen91 sharpeningSettings91(){return new HasselbladSharpen91();}public HasselbladDngBridge79 bridge79(com.particlesdevs.photoncamera.processing.ImageFrame f,int r)throws java.io.IOException{Test94.step("bridge");return new HasselbladDngBridge79();}public void recordCapture79(){}public void finishRawSave(java.nio.file.Path p,boolean v){}}''',
PACKAGE+'.hasselblad.HasselbladDngBridge79':'''public class HasselbladDngBridge79 implements AutoCloseable {public int width=320,height=256,orientation=1,iso=100;public long exposureNs=10000000;public Float aperture=2f,focalLength=8f;public void write(java.io.File f)throws java.io.IOException{Test94.step("write");Test94.writes++;java.nio.file.Files.write(f.toPath(),new byte[]{4,5,6});}public void close(){Test94.bridgeCloses++;}}''',
PACKAGE+'.hasselblad.HasselbladProfile43':'''public class HasselbladProfile43 {public boolean hasAutomaticIlluminant=true,hasNativeFinishing=true;public int film=1;public byte[] encoded(){return new byte[0];}}''',
PACKAGE+'.hasselblad.HasselbladLookStore84':'''public class HasselbladLookStore84 {public static HasselbladProfile43 read(android.content.Context c)throws java.io.IOException{Test94.step("profile");var p=new HasselbladProfile43();if(Test94.fail.equals("invalid_profile"))p.hasNativeFinishing=false;return p;}}''',
PACKAGE+'.hasselblad.HasselbladLook84':'''public class HasselbladLook84 {public static String sha256(byte[] b){return "fixture";}public static String curveHash(HasselbladProfile43 p){return "fixture";}}''',
PACKAGE+'.hasselblad.HasselbladDevice75Buffers':'''public class HasselbladDevice75Buffers {public static byte[] encode(short[] b){return new byte[0];}}''',
PACKAGE+'.hasselblad.HasselbladCaptureSaveStatus':'''public class HasselbladCaptureSaveStatus {public static void skipped(String s){}}''',
PACKAGE+'.hasselblad.HasselbladCaptureFiles80':'''public class HasselbladCaptureFiles80 {public static class Metrics {public java.util.Map<String,Object> snapshot(){return java.util.Map.of();}}public static void publish(android.content.Context c,java.nio.file.Path from,java.nio.file.Path to,Metrics m)throws java.io.IOException {boolean raw=to.toString().endsWith(".dng");if(raw)Test94.rawCalls++;else Test94.jpegCalls++;Test94.step(raw?"save_raw":"save_jpeg");java.nio.file.Files.copy(from,to);}}''',
PACKAGE+'.hasselblad.HasselbladSceneRenderer79':'''public class HasselbladSceneRenderer79 {public interface Sink{void begin(int w,int h);void band(int y,int rows,int w,int[] p);}public static class Sample {public short[] bayer,rgb;public int sensorX,sensorY;}public static class Result {public int width=256,height=192,rawWidth=320,rawHeight=256,kelvin=4850,checkedSites,workers=1,gainMaps;public long preparationNs,referenceNs,demosaicNs,colourNs,belowBlack,atWhite,gainClips;public boolean sharpeningApplied=true;public java.util.ArrayList<Sample> samples=new java.util.ArrayList<>();}public static Result render(java.io.File f,HasselbladProfile43 p,int workers,boolean diagnostics,HasselbladSharpen91 sharp,Sink sink)throws java.io.IOException {Test94.renders++;Test94.step("render");sink.begin(256,192);sink.band(0,192,256,new int[256*192]);return new Result();}}'''
}
for name in ('CameraCharacteristics','CaptureResult','CaptureRequest'):
 STUBS['android/hardware/camera2/'+name+'.java']='package android.hardware.camera2;public class '+name+' {}'
def run(work):
 work.mkdir(parents=True,exist_ok=True);src=work/'src';classes=work/'classes';classes.mkdir(exist_ok=True)
 for key,text in STUBS.items():
  if not key.endswith('.java'):
   package,_,name=key.rpartition('.');text='package '+package+';'+text;key=key.replace('.','/')+'.java'
  p=src/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
 java=ROOT/'HasselbladPhoton/app/src/main/java'/PACKAGE.replace('.','/')
 actual=['hasselblad/HasselbladCapture79.java','hasselblad/HasselbladDiagnostics86.java','processing/ProcessingEventsListener.java','processing/encoder/ImageFormatConfig.java','processing/processor/HdrxProcessor.java','processing/JPEGSaver.java','processing/YUVSaver.java']
 compiler=[shutil.which('javac')] if shutil.which('javac') else ['java','com.sun.tools.javac.Main']
 subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,src.rglob('*.java')),*[str(java/p) for p in actual],str(HERE/'Stage94Check.java')],check=True)
 result=json.loads(subprocess.check_output(['java','-cp',str(classes),PACKAGE+'.hasselblad.Stage94Check',str(work)],text=True))
 (work/'STAGE94_HOST_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);run(p.parse_args().work.resolve())
