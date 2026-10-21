import com.particlesdevs.photoncamera.hasselblad.HasselbladSceneDiagnostics;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.*;
import org.json.*;

/** Desktop JVM integration of the actual app binder and JNI library. Only
 * ImageFrame's Android-dependent allocation layer is replaced by a field shim. */
public final class SceneJniHarness {
    static int checks=0;
    static void check(boolean b) {checks++;if(!b)throw new AssertionError("check "+checks);}
    static ImageFrame frame(byte[] raw,int w,int h) {
        ImageFrame f=new ImageFrame();f.width=f.sourceRawWidth=w;f.height=f.sourceRawHeight=h;
        f.sourceRowStride=w*2;f.sourcePixelStride=2;f.buffer=ByteBuffer.allocateDirect(raw.length);f.buffer.put(raw).rewind();return f;
    }
    static JSONObject copy(JSONObject j)throws Exception{return new JSONObject(j.toString());}
    static JSONObject result(JSONObject j)throws Exception{return j.getJSONObject("original_still").getJSONObject("selected_raw_sensor_result");}
    static JSONObject chars(JSONObject j)throws Exception{return j.getJSONObject("original_still").getJSONObject("selected_sensor_characteristics");}
    static JSONObject run(JSONObject j,ImageFrame f)throws Exception{return HasselbladSceneDiagnostics.run(j,f);}
    public static void main(String[] args)throws Exception {
        JSONObject input=new JSONObject(Files.readString(Path.of(args[0])));
        JSONObject original=input.getJSONObject("capture");byte[] raw=Files.readAllBytes(Path.of(args[1]));
        int w=input.getInt("width"),h=input.getInt("height");long timestamp=Long.parseLong(result(original).getString("android.sensor.timestamp"));
        ImageFrame f=frame(raw,w,h);f.rawSensorTimestampNs=timestamp;
        String jsonBefore=original.toString();JSONObject first=run(original,f);
        check(first.getString("status").equals("completed"));check(!first.getBoolean("render_applied"));
        check(original.toString().equals(jsonBefore));check(f.buffer.position()==0 && f.buffer.limit()==raw.length);
        for(int i=0;i<raw.length;i++)if(f.buffer.get(i)!=raw[i])throw new AssertionError("RAW changed");checks++;
        JSONArray expected=input.getJSONArray("expected"),actual=first.getJSONArray("policies");
        String[] scalar={"radius_q12","adapter_status","decision","native_status","raw_valid_blocks","admitted_blocks","classified_blocks","retained_blocks","raw_rejected_blocks","brightness_rejected_blocks","signed_gain_rejected_blocks","outside_locus_blocks","component_removed_blocks"};
        for(int p=0;p<6;p++) {
            JSONObject e=expected.getJSONObject(p),a=actual.getJSONObject(p);
            for(String key:scalar)check(e.get(key).toString().equals(a.get(key).toString()));
            for(String key:new String[]{"gain_q12","neutral_green_normalized","temperature_kelvin_tint_residual"}) {
                if(e.isNull(key))check(a.isNull(key));
                else for(int i=0;i<3;i++)check(e.getJSONArray(key).getDouble(i)==a.getJSONArray(key).getDouble(i));
            }
        }
        ImageFrame empty=frame(new byte[raw.length],w,h);empty.rawSensorTimestampNs=timestamp;
        JSONObject no=run(original,empty);check(no.getString("status").equals("completed"));
        for(int p=0;p<6;p++) {JSONObject a=no.getJSONArray("policies").getJSONObject(p);check(a.getString("decision").equals("no_candidate"));check(a.isNull("gain_q12") && a.isNull("neutral_green_normalized"));}
        JSONObject again=run(original,f);check(again.getJSONArray("policies").toString().equals(actual.toString()));
        for(int test=0;test<26;test++) {
            JSONObject j=copy(original);ImageFrame bad=frame(raw,w,h);bad.rawSensorTimestampNs=timestamp;
            switch(test) {
                case 0:j.put("calibration_evidence_usable",false);break;
                case 1:bad.rawSensorTimestampNs++;break;
                case 2:bad.fp16=true;break;
                case 3:bad.packedBits=10;break;
                case 4:bad.sourceBinned=true;break;
                case 5:bad.cropOriginX=2;break;
                case 6:bad.sourceCopyOffsetBytes=2;break;
                case 7:bad.sourceRowStride+=2;break;
                case 8:bad.buffer=ByteBuffer.wrap(raw);break;
                case 9:bad.buffer.position(2);break;
                case 10:bad.buffer.limit(raw.length-2);break;
                case 11:bad.buffer=ByteBuffer.allocateDirect(raw.length-2);break;
                case 12:chars(j).remove("android.sensor.colorTransform1");break;
                case 13:chars(j).getJSONArray("android.sensor.colorTransform1").getJSONObject(0).put("denominator",0);break;
                case 14:chars(j).put("android.sensor.referenceIlluminant1",0);break;
                case 15:result(j).put("android.sensor.dynamicBlackLevel",new JSONArray(new double[]{64,65,64,64}));break;
                case 16:result(j).put("android.sensor.dynamicWhiteLevel",1);break;
                case 17:chars(j).put("android.sensor.info.colorFilterArrangement",4);break;
                case 18:result(j).put("android.sensor.pixelMode",1);break;
                case 20:chars(j).put("android.sensor.info.pixelArraySize",new JSONArray(new int[]{w*2,h*2}));break;
                case 21:j.getJSONObject("delivered_raw").put("image_crop_rect",new JSONArray(new int[]{2,0,w,h}));break;
                case 22:result(j).put("android.sensor.rawBinningFactorUsed",true);chars(j).put("android.request.availableCapabilities",new JSONArray(new int[]{3,16,17}));break;
                case 23:result(j).put("android.sensor.rawBinningFactorUsed",JSONObject.NULL);chars(j).put("android.request.availableCapabilities",new JSONArray(new int[]{3,16,17}));break;
                case 24:chars(j).put("android.request.availableCapabilities",new JSONArray(new int[]{0}));break;
                case 25:result(j).put("android.sensor.dynamicBlackLevel",new JSONArray(new double[]{.000001,.000001,.000001,.000001}));break;
                case 19:result(j).put("android.sensor.pixelMode",JSONObject.NULL);chars(j).put("android.request.availableCapabilities",new JSONArray(new int[]{16}));break;
            }
            JSONObject rejection=run(j,bad);check(rejection.getString("status").equals("skipped"));check(!rejection.has("policies"));
            check(HasselbladSceneDiagnostics.latestSummary().contains("skipped"));
        }
        int binningCases=0;
        for(int capability=0;capability<4;capability++)for(int flag=0;flag<4;flag++) {
            JSONObject j=copy(original);
            int[][] capSets={{3},{3,16},{3,16,17},{3,17}};
            chars(j).put("android.request.availableCapabilities",new JSONArray(capSets[capability]));
            result(j).put("android.sensor.pixelMode",0);
            if(flag==0)result(j).remove("android.sensor.rawBinningFactorUsed");
            else result(j).put("android.sensor.rawBinningFactorUsed",flag==1 ? JSONObject.NULL : flag==3);
            JSONObject decision=run(j,f);boolean allowed=capability<2 || (capability==2 && flag==2);
            check(decision.getString("status").equals(allowed ? "completed" : "skipped"));
            check(!decision.getBoolean("render_applied"));
            if(allowed) {
                check(decision.getJSONArray("policies").toString().equals(actual.toString()));
                check(decision.getBoolean("raw_binning_flag_outside_scope")== (capability<2 && flag>=2));
            } else check(!decision.has("policies"));
            binningCases++;
        }
        Method nativeCall=HasselbladSceneDiagnostics.class.getDeclaredMethod("nativeSweep",ByteBuffer.class,int[].class,double[].class,float[].class);nativeCall.setAccessible(true);
        int[] geometry=new int[]{w,h,w*2,0,1023,2856,6504};double[] black={64,64,64,64};float[] matrices=new float[36];for(int a=0;a<4;a++)for(int i=0;i<3;i++)matrices[a*9+i*4]=1;
        for(int test=0;test<19;test++) {
            Object[] a={f.buffer,geometry.clone(),black.clone(),matrices.clone()};int[] g=(int[])a[1];double[] b=(double[])a[2];float[] m=(float[])a[3];
            switch(test){
                case 0:a[0]=null;break;case 1:a[1]=null;break;case 2:a[2]=null;break;case 3:a[3]=null;break;
                case 4:a[1]=new int[6];break;case 5:a[2]=new double[3];break;case 6:a[3]=new float[35];break;
                case 7:a[0]=ByteBuffer.allocate(raw.length);break;case 8:g[0]=-1;break;case 9:g[1]=63;break;
                case 10:g[2]+=2;break;case 11:g[3]=4;break;case 12:g[4]=65536;break;case 13:g[5]=4000;break;
                case 14:b[0]=Double.NaN;break;case 15:b[1]=65;break;case 16:m[0]=Float.POSITIVE_INFINITY;break;
                case 17:a[0]=ByteBuffer.allocateDirect(raw.length-2);break;
                case 18:java.util.Arrays.fill(b,.000001);break;
            }
            try {nativeCall.invoke(null,a);throw new AssertionError("native guard "+test);}
            catch(InvocationTargetException ex){check(ex.getCause() instanceof IllegalArgumentException);}
        }
        check(run(original,f).getJSONArray("policies").toString().equals(actual.toString()));
        Files.writeString(Path.of(args[2]),first.toString(2));
        System.out.println(new JSONObject().put("checks",checks).put("java_rejections",26).put("binning_capability_cases",binningCases).put("jni_rejections",19).put("raw_unmodified",true).put("metadata_unmodified",true).put("candidate_empty_candidate_reset",true));
    }
}
