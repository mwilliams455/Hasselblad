import com.particlesdevs.photoncamera.hasselblad.*;
import com.particlesdevs.photoncamera.processing.*;
import com.particlesdevs.photoncamera.util.Allocator;
import android.hardware.camera2.*;
import android.hardware.camera2.params.*;
import android.graphics.Rect;
import android.util.Rational;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import static android.hardware.camera2.CameraCharacteristics.*;
import static android.hardware.camera2.CaptureResult.*;
public final class Stage79BridgeCheck {
    static void check(boolean ok,String what){if(!ok)throw new AssertionError(what);}
    public static void main(String[] args)throws Exception {
        CameraCharacteristics c=new CameraCharacteristics();CaptureResult r=new CaptureResult();
        c.set(SENSOR_INFO_COLOR_FILTER_ARRANGEMENT,0);c.set(SENSOR_INFO_WHITE_LEVEL,4095);
        c.set(SENSOR_BLACK_LEVEL_PATTERN,new BlackLevelPattern());c.set(SENSOR_REFERENCE_ILLUMINANT1,21);c.set(SENSOR_REFERENCE_ILLUMINANT2,(byte)17);
        c.set(SENSOR_INFO_ACTIVE_ARRAY_SIZE,new Rect(0,0,128,128));c.set(SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE,new Rect(0,0,128,128));
        for(var key:List.of(SENSOR_COLOR_TRANSFORM1,SENSOR_COLOR_TRANSFORM2,SENSOR_FORWARD_MATRIX1,SENSOR_FORWARD_MATRIX2,SENSOR_CALIBRATION_TRANSFORM1,SENSOR_CALIBRATION_TRANSFORM2))c.set(key,new ColorSpaceTransform());
        r.set(SENSOR_DYNAMIC_WHITE_LEVEL,4000);r.set(SENSOR_DYNAMIC_BLACK_LEVEL,new float[]{60,61,62,63});
        r.set(SENSOR_NEUTRAL_COLOR_POINT,new Rational[]{new Rational(1,2),new Rational(1,1),new Rational(3,4)});
        r.set(STATISTICS_LENS_SHADING_CORRECTION_MAP,new LensShadingMap());r.set(SENSOR_SENSITIVITY,400);r.set(SENSOR_EXPOSURE_TIME,10000000L);
        ImageFrame f=new ImageFrame();f.sourceRawWidth=128;f.sourceRawHeight=128;f.sourceRawFormat=32;f.sourcePixelStride=2;
        f.sourceRowStride=272;f.width=136;f.height=128;f.sourceRawBufferCapacity=272*128;f.buffer=ByteBuffer.allocateDirect(f.sourceRawBufferCapacity);
        f.sourceImageCropRect=new Rect(0,0,128,128);
        for(int i=0;i<f.buffer.capacity();i++)f.buffer.put(i,(byte)(i*19));f.buffer.position(7);f.buffer.limit(f.buffer.capacity()-1);
        Path dest=Path.of(args[0],"bridge79-spy.raw");
        try(var bridge=new HasselbladDngBridge79(f,c,r,90)) {
            var v=DngCreator.last.values;
            check(v.get("WhiteLevel").equals(4000.0),"Dynamic white ignored");
            check(Arrays.equals((short[])v.get("BlackLevel"),new short[]{60,61,62,63}),"Dynamic black ignored");
            check(Arrays.equals((double[])v.get("ForwardMatrix1"),new double[]{.1,.2,.3,.4,.5,.6,.7,.8,.9}),"Matrix transposed");
            check(Arrays.equals((double[])v.get("AsShotNeutral"),new double[]{.5,1,.75}),"Original neutral changed");
            check(v.get("Orientation").equals(1)&&bridge.orientation==6,"DNG/EXIF rotation units confused");
            check(Arrays.equals((int[])v.get("GainArea"),new int[]{0,0,128,128,3,2}),"Gain map coordinates changed");
            bridge.write(dest.toFile());byte[] actual=Files.readAllBytes(dest);
            for(int y=0;y<128;y++)for(int x=0;x<256;x++)check(actual[y*256+x]==(byte)((y*272+x)*19),"Wrong staged RAW counts");
            check(f.buffer.position()==7&&f.buffer.limit()==f.buffer.capacity()-1,"Caller buffer cursor modified");
            DngCreator.failWrite=true;boolean failed=false;try{bridge.write(dest.toFile());}catch(RuntimeException e){failed=true;}
            check(failed&&Allocator.allocations==Allocator.frees,"Write failure leaks packed allocation");DngCreator.failWrite=false;
        }
        check(DngCreator.last.closed,"DNG writer leaked");
        r.set(SENSOR_DYNAMIC_BLACK_LEVEL,new float[]{60.5f,61,62,63});
        try(var ignored=new HasselbladDngBridge79(f,c,r,0)){
            check(Arrays.equals((double[])DngCreator.last.values.get("BlackLevelPrecise93"),new double[]{60.5,61,62,63}),"Fractional black not transported exactly");
            check(!DngCreator.last.values.containsKey("BlackLevel"),"Fractional black was also sent through integer setter");
        }
        boolean rejected=false;
        r.set(SENSOR_DYNAMIC_BLACK_LEVEL,null);r.set(SENSOR_DYNAMIC_WHITE_LEVEL,null);
        try(var bridge=new HasselbladDngBridge79(f,c,r,0)) {
            check(DngCreator.last.values.get("WhiteLevel").equals(4095.0),"Static white fallback");
            check(Arrays.equals((short[])DngCreator.last.values.get("BlackLevel"),new short[]{64,65,66,67}),"CFA black order");
        }
        c.set(SENSOR_INFO_ACTIVE_ARRAY_SIZE,new Rect(2,0,130,128));rejected=false;
        try(var ignored=new HasselbladDngBridge79(f,c,r,0)){}catch(java.io.IOException e){rejected=true;}
        check(rejected,"Shifted gain map domain accepted");
        System.out.println("STAGE79_BRIDGE_PASS original matrix/neutral/levels, CFA/rotation, padded RAW copy, writer/allocator cleanup; JVM spies only, not device IO");
    }
}
