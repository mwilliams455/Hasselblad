"""Small Camera2 test doubles, not a device/HAL simulation. Production adapter is compiled unchanged."""
from pathlib import Path

def write_stubs(root):
    files={}
    def add(pkg,name,body):
        files[root/Path(pkg.replace('.','/'))/(name+'.java')]='package '+pkg+';\n'+body
    camera='android.hardware.camera2'
    add(camera,'CaptureRequest','''public class CaptureRequest {
      public static final int TONEMAP_MODE_CONTRAST_CURVE=0;
      public static class Key<T>{public final String name;public Key(String n){name=n;}}
      public static final Key<Integer> TONEMAP_MODE=new Key<>("mode");
      public static final Key<android.hardware.camera2.params.TonemapCurve> TONEMAP_CURVE=new Key<>("curve");
      private final java.util.Map<Key<?>,Object> values;
      CaptureRequest(java.util.Map<Key<?>,Object> v){values=new java.util.HashMap<>(v);}
      @SuppressWarnings("unchecked") public <T>T get(Key<T> key){return (T)values.get(key);}
      public static class Builder {
        private final java.util.Map<Key<?>,Object> values=new java.util.HashMap<>();
        @SuppressWarnings("unchecked") public <T>T get(Key<T> key){return (T)values.get(key);}
        public <T>void set(Key<T> key,T value){values.put(key,value);}
        public CaptureRequest build(){return new CaptureRequest(values);}
      }
    }''')
    def keyed(name,keys,extra=''):
        body='public class '+name+' { public static class Key<T>{public Key(String n){}}\n'
        for typ,key in keys:body+='public static final Key<'+typ+'> '+key+'=new Key<>("'+key+'");\n'
        body+='private final java.util.Map<Key<?>,Object> values=new java.util.HashMap<>();\n@SuppressWarnings("unchecked") public <T>T get(Key<T> key){return (T)values.get(key);}\npublic <T>void set(Key<T> key,T value){values.put(key,value);}\n'+extra+'}'
        add(camera,name,body)
    keyed('CameraCharacteristics',[(t,k) for t,ks in [
       ('int[]','TONEMAP_AVAILABLE_TONE_MAP_MODES'),('Integer','TONEMAP_MAX_CURVE_POINTS SENSOR_INFO_COLOR_FILTER_ARRANGEMENT SENSOR_REFERENCE_ILLUMINANT1 SENSOR_REFERENCE_ILLUMINANT2 SENSOR_INFO_WHITE_LEVEL'),
       ('android.hardware.camera2.params.ColorSpaceTransform','SENSOR_CALIBRATION_TRANSFORM1 SENSOR_CALIBRATION_TRANSFORM2 SENSOR_COLOR_TRANSFORM1 SENSOR_COLOR_TRANSFORM2 SENSOR_FORWARD_MATRIX1 SENSOR_FORWARD_MATRIX2'),
       ('android.hardware.camera2.params.BlackLevelPattern','SENSOR_BLACK_LEVEL_PATTERN')] for k in ks.split()], 'public static final int SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGGB=0;')
    keyed('CaptureResult',[(t,k) for t,ks in [
       ('String','LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID'),('Integer','TONEMAP_MODE SENSOR_SENSITIVITY CONTROL_POST_RAW_SENSITIVITY_BOOST SENSOR_DYNAMIC_WHITE_LEVEL'),
       ('Long','SENSOR_EXPOSURE_TIME SENSOR_TIMESTAMP'),('float[]','SENSOR_DYNAMIC_BLACK_LEVEL'),('android.util.Rational[]','SENSOR_NEUTRAL_COLOR_POINT'),
       ('android.hardware.camera2.params.ColorSpaceTransform','COLOR_CORRECTION_TRANSFORM'),('android.hardware.camera2.params.RggbChannelVector','COLOR_CORRECTION_GAINS'),
       ('android.hardware.camera2.params.TonemapCurve','TONEMAP_CURVE')] for k in ks.split()], 'public static final int TONEMAP_MODE_CONTRAST_CURVE=0;')
    add(camera,'TotalCaptureResult','public class TotalCaptureResult extends CaptureResult {public final java.util.Map<String,CaptureResult> physical=new java.util.HashMap<>();public java.util.Map<String,CaptureResult> getPhysicalCameraResults(){return physical;}}')
    add(camera,'CameraManager','public class CameraManager {public final java.util.Map<String,CameraCharacteristics> cameras=new java.util.HashMap<>();public CameraCharacteristics getCameraCharacteristics(String id){return cameras.get(id);}}')
    params=camera+'.params'
    add(params,'ColorSpaceTransform','public class ColorSpaceTransform {final android.util.Rational[] m;public ColorSpaceTransform(android.util.Rational[] m){this.m=m.clone();}public android.util.Rational getElement(int c,int r){return m[3*r+c];}}')
    add(params,'TonemapCurve','public class TonemapCurve {final float[][] c;public TonemapCurve(float[] r,float[] g,float[] b){c=new float[][]{r.clone(),g.clone(),b.clone()};}public int getPointCount(int channel){return c[channel].length/2;}public void copyColorCurve(int channel,float[] out,int offset){System.arraycopy(c[channel],0,out,offset,c[channel].length);}}')
    add(params,'RggbChannelVector','public class RggbChannelVector {final float r,g,h,b;public RggbChannelVector(float r,float g,float h,float b){this.r=r;this.g=g;this.h=h;this.b=b;}public float getRed(){return r;}public float getGreenEven(){return g;}public float getGreenOdd(){return h;}public float getBlue(){return b;}}')
    add(params,'BlackLevelPattern','public class BlackLevelPattern {public int getOffsetForIndex(int x,int y){return 64;}}')
    add('android.util','Rational','public class Rational extends Number {final int n,d;public Rational(int n,int d){this.n=n;this.d=d;}public double doubleValue(){return (double)n/d;}public float floatValue(){return (float)doubleValue();}public int intValue(){return (int)doubleValue();}public long longValue(){return (long)doubleValue();}}')
    add('android.os','Build','public class Build {public static class VERSION {public static int SDK_INT=35;}}')
    add('android.os','SystemClock','public class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000;}}')
    add('android.view','Surface','public class Surface {}')
    prefix='com.particlesdevs.photoncamera'
    add(prefix+'.api','CameraMode','public enum CameraMode {PHOTO,VIDEO,NIGHT}')
    add(prefix+'.api','Settings','public class Settings {public CameraMode selectedMode=CameraMode.PHOTO;public boolean QuadBayer,heicSave,aspect169;public int rawSaver;}')
    add(prefix+'.app','PhotonCamera','public class PhotonCamera {public static final com.particlesdevs.photoncamera.api.Settings settings=new com.particlesdevs.photoncamera.api.Settings();public static com.particlesdevs.photoncamera.api.Settings getSettings(){return settings;}}')
    add(prefix+'.capture','CaptureController','public class CaptureController {public long mPreviewExposureTime=10000000;public int mPreviewIso=100;}')
    add(prefix+'.processing.parameters','IsoExpoSelector','public class IsoExpoSelector {public static class ExpoPair {public long exposure;public int iso;}public static ExpoPair GenerateExpoPair(int step,com.particlesdevs.photoncamera.capture.CaptureController owner){if(step!=-1)throw new AssertionError();ExpoPair p=new ExpoPair();p.exposure=owner.mPreviewExposureTime;p.iso=owner.mPreviewIso;return p;}}')
    for p,text in files.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    return list(map(str,files))
