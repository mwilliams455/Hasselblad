import com.particlesdevs.photoncamera.hasselblad.*;
import com.particlesdevs.photoncamera.processing.*;
import com.particlesdevs.photoncamera.util.Allocator;
import android.hardware.camera2.*;
import android.hardware.camera2.params.*;
import android.graphics.Rect;
import android.util.Rational;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import static android.hardware.camera2.CameraCharacteristics.*;
import static android.hardware.camera2.CaptureResult.*;

public final class Stage93Check {
    static int checks,preparedSamples;
    static void check(boolean ok,String reason){checks++;if(!ok)throw new AssertionError(reason);}
    interface Task {void run()throws Exception;}
    static void invalid(Task task)throws Exception{boolean rejected=false;try{task.run();}catch(IllegalArgumentException|java.io.IOException e){rejected=true;}check(rejected,"Invalid metadata accepted");}
    static CameraCharacteristics camera(){
        CameraCharacteristics c=new CameraCharacteristics();c.set(SENSOR_INFO_COLOR_FILTER_ARRANGEMENT,0);c.set(SENSOR_INFO_WHITE_LEVEL,4095);
        c.set(SENSOR_BLACK_LEVEL_PATTERN,new BlackLevelPattern());c.set(SENSOR_REFERENCE_ILLUMINANT1,21);c.set(SENSOR_REFERENCE_ILLUMINANT2,(byte)17);
        c.set(SENSOR_INFO_ACTIVE_ARRAY_SIZE,new Rect(0,0,128,128));c.set(SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE,new Rect(0,0,128,128));
        for(var key:List.of(SENSOR_COLOR_TRANSFORM1,SENSOR_COLOR_TRANSFORM2,SENSOR_FORWARD_MATRIX1,SENSOR_FORWARD_MATRIX2,SENSOR_CALIBRATION_TRANSFORM1,SENSOR_CALIBRATION_TRANSFORM2))c.set(key,new ColorSpaceTransform());return c;
    }
    static CaptureResult metadata(float[] black,int white){
        CaptureResult r=new CaptureResult();r.set(SENSOR_DYNAMIC_WHITE_LEVEL,white);r.set(SENSOR_DYNAMIC_BLACK_LEVEL,black);
        r.set(SENSOR_NEUTRAL_COLOR_POINT,new Rational[]{new Rational(1,2),new Rational(1,1),new Rational(3,4)});
        r.set(STATISTICS_LENS_SHADING_CORRECTION_MAP,new LensShadingMap());r.set(SENSOR_SENSITIVITY,400);r.set(SENSOR_EXPOSURE_TIME,10000000L);return r;
    }
    static ImageFrame frame(int white,boolean padded){
        ImageFrame f=new ImageFrame();f.sourceRawWidth=128;f.sourceRawHeight=128;f.sourceRawFormat=32;f.sourcePixelStride=2;
        f.sourceRowStride=padded?272:256;f.width=f.sourceRowStride/2;f.height=128;f.sourceRawBufferCapacity=f.sourceRowStride*128;
        f.buffer=ByteBuffer.allocateDirect(f.sourceRawBufferCapacity).order(ByteOrder.LITTLE_ENDIAN);f.sourceImageCropRect=new Rect(0,0,128,128);
        for(int y=0;y<128;y++)for(int x=0;x<128;x++)f.buffer.putShort(y*f.sourceRowStride+x*2,(short)(((y*128+x)*37)%white));
        f.buffer.position(7);f.buffer.limit(f.buffer.capacity()-1);return f;
    }
    static void legacy(Path work)throws Exception{
        for(String mode:new String[]{"uncompressed","compressed","binned","10bit"}){
            DngCreator writer=new DngCreator();try {
                writer.setCompression(mode.equals("compressed"));writer.setBinning(mode.equals("binned"));writer.setBitsPerSample(mode.equals("10bit")?10:16);
                writer.setWhiteLevel(4095);writer.setBlackLevel(new short[]{60,61,62,63});writer.setCFAPattern(0);writer.setOrientation(0);
                writer.setDateTime("2026:10:26 12:00:00");writer.setMake("Synthetic");writer.setModel("Fractional black regression");
                ByteBuffer raw=frame(4095,false).buffer;raw.clear();try(OutputStream out=Files.newOutputStream(work.resolve("legacy-"+mode+".dng"))){writer.writeBuffer(out,raw,128,128);}
            }finally{writer.close();}
        }
    }
    public static void main(String[] args)throws Exception{
        Path work=Path.of(args[0]);legacy(work);if(args.length>1)return;
        List<float[]> sets=new ArrayList<>(List.of(new float[]{60,61,62,63},new float[]{60.5f,61.25f,62.75f,63.125f},
                new float[]{64.00001f,65.12345f,66.99999f,67.5f},new float[]{0,.125f,1f/256,4094.75f}));
        Random rng=new Random(93);for(int c=0;c<12;c++){float[] b=new float[4];for(int i=0;i<4;i++)b[i]=rng.nextFloat()*512;sets.add(b);}sets.add(null);
        List<String> manifest=new ArrayList<>();CameraCharacteristics c=camera();int index=0;
        for(float[] values:sets){
            int white=index==16?4095:4000;if(index==3)white=4095;
            CaptureResult result=metadata(values,white);if(values==null)result.set(SENSOR_DYNAMIC_WHITE_LEVEL,null);
            ImageFrame frame=frame(white,index%2==0);byte[] before=new byte[frame.buffer.capacity()];frame.buffer.duplicate().clear().get(before);
            String name="roundtrip-"+index+".dng";Path file=work.resolve(name);boolean fractional=false;
            double[] black=new double[4];for(int i=0;i<4;i++){black[i]=values==null?64+i:values[i];fractional|=black[i]!=Math.rint(black[i]);}
            try(HasselbladDngBridge79 bridge=new HasselbladDngBridge79(frame,c,result,90)){bridge.write(file.toFile());}
            check(frame.buffer.position()==7&&frame.buffer.limit()==frame.buffer.capacity()-1,"source buffer cursor changed");
            byte[] after=new byte[before.length];frame.buffer.duplicate().clear().get(after);check(Arrays.equals(before,after),"source RAW buffer mutated");
            var prepared=HasselbladDngTileReader.readPrepared78(file.toFile()).frame;
            check(prepared.orientation==6&&prepared.metadata.width==128&&prepared.metadata.height==128,"metadata geometry changed");
            double max=Arrays.stream(black).max().getAsDouble();
            for(int y=0;y<128;y++)for(int x=0;x<128;x++){
                int i=y*128+x,raw=(i*37)%white,phase=(y%2)*2+x%2;
                float normalized=Math.max(0f,Math.min(1f,(float)((raw-black[phase])/(white-max))));
                int expected=(int)(normalized*65535f);check((prepared.bayer[i]&65535)==expected,"fractional black not used by RAW preparation");preparedSamples++;
            }
            manifest.add("{\"file\":\""+name+"\",\"black\":"+Arrays.toString(black)+",\"fractional\":"+fractional+",\"white\":"+white+"}");index++;
        }
        check(Allocator.allocations==Allocator.frees,"padded RAW allocation leak");
        for(float[] bad:new float[][]{{Float.NaN,1,1,1},{Float.POSITIVE_INFINITY,1,1,1},{-1,1,1,1},{4000,1,1,1},{1,2,3}})
            invalid(()->{try(var ignored=new HasselbladDngBridge79(frame(4000,false),c,metadata(bad,4000),0)){};});
        DngCreator writer=new DngCreator();
        for(double[] bad:new double[][]{null,{1,2,3},{1,2,3,4,5},{Double.NaN,1,1,1},{-1,1,1,1},{65536,1,1,1}})invalid(()->writer.setBlackLevelPrecise93(bad));
        // JNI independently validates dimensions even if the Java wrapper is bypassed.
        var pointer=DngCreator.class.getDeclaredField("nativePtr");pointer.setAccessible(true);
        var nativeSetter=DngCreator.class.getDeclaredMethod("setBlackLevelPrecise93",long.class,double[].class);nativeSetter.setAccessible(true);
        check(!(Boolean)nativeSetter.invoke(writer,pointer.getLong(writer),new double[]{1,2,3}),"native undersized array accepted");
        check(!(Boolean)nativeSetter.invoke(writer,pointer.getLong(writer),new double[]{Double.NaN,1,1,1}),"native NaN accepted");writer.close();
        boolean closed=false;try{writer.setBlackLevelPrecise93(new double[]{1,2,3,4});}catch(IllegalStateException e){closed=true;}check(closed,"closed writer accepted metadata");
        for(String mode:new String[]{"compressed","binned","10bit"}){
            DngCreator exact=new DngCreator();try{
                exact.setWhiteLevel(4095);exact.setBlackLevelPrecise93(new double[]{60.5,61,62,63});exact.setCompression(mode.equals("compressed"));exact.setBinning(mode.equals("binned"));exact.setBitsPerSample(mode.equals("10bit")?10:16);
                boolean rejected=false;try{ByteBuffer raw=frame(4095,false).buffer;raw.clear();exact.writeBuffer(new ByteArrayOutputStream(),raw,128,128);}catch(RuntimeException e){rejected=true;}check(rejected,"exact RAW API silently changed sample domain");
            }finally{exact.close();}
        }
        Files.writeString(work.resolve("roundtrips.json"),"["+String.join(",",manifest)+"]\n");
        String receipt="{\"checks\":"+checks+",\"prepared_samples_exact\":"+preparedSamples+",\"actual_Java_bridge_wrapper_JNI_reader\":true}";
        Files.writeString(work.resolve("STAGE93_JAVA_CHECKS.json"),receipt+"\n");System.out.println(receipt);
    }
}
