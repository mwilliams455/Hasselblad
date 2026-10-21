import com.particlesdevs.photoncamera.hasselblad.HasselbladDomainDiagnostics;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;

/** JVM harness for the app's REAL Java -> JNI -> Domain1 -> owned leaf route.
 * Uses only synthetic calibration fixtures. Never uses vendor/phone metadata. */
public final class DomainJniHarness {
    private static int checks;
    private static void ok(boolean b) {checks++;if(!b) throw new AssertionError("check "+checks);}
    private static JSONArray identityMatrix(int numerator) throws Exception {
        JSONArray a=new JSONArray();
        for(int i=0;i<9;i++) {
            int n=(i==0 || i==4 || i==8)?numerator:0;
            a.put(new JSONObject().put("numerator",n).put("denominator",1000));
        }
        return a;
    }
    private static JSONObject fixture() throws Exception {
        JSONObject provenance=new JSONObject()
            .put("sensor_provenance_matched",true).put("result_camera_id_matched",true)
            .put("request_targets_recorded_raw_surface",true)
            .put("selected_and_logical_frame_number_matched",true)
            .put("selected_characteristics_are_logical",false)
            .put("selected_calibration_camera_id","2")
            .put("selected_result_camera_id","2");
        JSONObject ch=new JSONObject()
            .put("android.sensor.referenceIlluminant1",17)
            .put("android.sensor.referenceIlluminant2",21)
            .put("android.sensor.colorTransform1",identityMatrix(1000))
            .put("android.sensor.colorTransform2",identityMatrix(1020))
            .put("android.sensor.calibrationTransform1",identityMatrix(1000))
            .put("android.sensor.calibrationTransform2",identityMatrix(1000));
        JSONObject original=new JSONObject()
            .put("sensor_provenance",provenance)
            .put("selected_sensor_characteristics",ch)
            .put("selected_sensor_timestamp_ns","185144849665300")
            .put("selected_result_frame_number","77")
            .put("selected_raw_sensor_result",new JSONObject()
                .put("android.sensor.timestamp","185144849665300"));
        return new JSONObject().put("calibration_evidence_usable",true)
            .put("frame_number","77").put("original_still",original);
    }
    private static void rejects(Method nativeCall,Object a,Object b,Object c) throws Exception {
        try {
            nativeCall.invoke(null,a,b,c);
            throw new AssertionError("native JNI must reject malformed input");
        } catch (InvocationTargetException ex) {
            ok(ex.getCause() instanceof IllegalArgumentException);
        }
    }
    public static void main(String[] args) throws Exception {
        HasselbladDomainDiagnostics.clear();
        JSONObject absent=HasselbladDomainDiagnostics.evaluateLatest();
        ok("skipped".equals(absent.getString("status")));
        ok(!absent.getBoolean("render_applied"));
        ok(!absent.getBoolean("shipping_policy_selected"));
        JSONObject input=fixture();
        String before=input.toString();
        HasselbladDomainDiagnostics.rememberCapture(input);
        ok(HasselbladDomainDiagnostics.hasVerifiedCapture());
        ok(input.toString().equals(before));
        JSONObject result=HasselbladDomainDiagnostics.evaluateLatest();
        ok("completed".equals(result.optString("status")));
        ok(!result.getBoolean("render_applied"));
        ok(!result.getBoolean("shipping_policy_selected"));
        ok(!result.getBoolean("selection_uses_hal_neutral"));
        ok("2".equals(result.getString("physical_sensor_id")));
        ok(result.getJSONObject("counts").getInt("total")==729);
        JSONArray points=result.getJSONArray("points");
        ok(points.length()==729);
        ok(points.getJSONObject(0).getInt("kelvin")==2000);
        ok(points.getJSONObject(0).getInt("tint")==-100);
        ok(points.getJSONObject(728).getInt("kelvin")==10000);
        ok(points.getJSONObject(728).getInt("tint")==100);
        ok(result.getJSONObject("counts").getInt("representable")
                +result.getJSONObject("counts").getInt("temperature_clipped")
                +result.getJSONObject("counts").getInt("scene_signed_gain")
                +result.getJSONObject("counts").getInt("adjacent_duplicate")==729);
        JSONObject second=HasselbladDomainDiagnostics.evaluateLatest();
        ok(second.getJSONObject("counts").toString().equals(result.getJSONObject("counts").toString()));
        ok(second.getJSONArray("points").toString().equals(points.toString()));
        ok(input.toString().equals(before));
        ok(HasselbladDomainDiagnostics.summary(result).contains("729"));
        JSONObject wrong=new JSONObject(before);
        wrong.getJSONObject("original_still").getJSONObject("sensor_provenance")
                .put("selected_result_camera_id","7");
        HasselbladDomainDiagnostics.rememberCapture(wrong);
        ok(!HasselbladDomainDiagnostics.hasVerifiedCapture());
        ok("skipped".equals(HasselbladDomainDiagnostics.evaluateLatest().optString("status")));
        wrong=new JSONObject(before);
        wrong.getJSONObject("original_still").put("selected_sensor_timestamp_ns","185144849665301");
        HasselbladDomainDiagnostics.rememberCapture(wrong);
        ok(!HasselbladDomainDiagnostics.hasVerifiedCapture());
        wrong=new JSONObject(before);
        wrong.getJSONObject("original_still").getJSONObject("selected_sensor_characteristics")
                .getJSONArray("android.sensor.colorTransform1").getJSONObject(0)
                .put("denominator",0);
        HasselbladDomainDiagnostics.rememberCapture(wrong);
        ok(HasselbladDomainDiagnostics.hasVerifiedCapture()); // Native input must still reject malformed matrix.
        ok("skipped".equals(HasselbladDomainDiagnostics.evaluateLatest().optString("status")));
        wrong=new JSONObject(before);
        wrong.put("calibration_evidence_usable",false);
        HasselbladDomainDiagnostics.rememberCapture(wrong);
        ok(!HasselbladDomainDiagnostics.hasVerifiedCapture());
        HasselbladDomainDiagnostics.rememberCapture(input);
        ok(HasselbladDomainDiagnostics.hasVerifiedCapture());

        // Native guards (after the positive call has loaded the library).
        Method nativeCall=HasselbladDomainDiagnostics.class.getDeclaredMethod(
            "nativeEvaluate",int[].class,float[].class,int[].class);
        nativeCall.setAccessible(true);
        int[] kelvins={2856,6504};
        float[] matrices=new float[36];
        for(int anchor=0;anchor<2;anchor++)for(int mode=0;mode<2;mode++)
            for(int diagonal=0;diagonal<3;diagonal++)
                matrices[anchor*18+mode*9+diagonal*4]=1f;
        int[] grid={2000,10000,100,-100,100,25};
        rejects(nativeCall,null,matrices,grid);
        rejects(nativeCall,new int[]{2856},matrices,grid);
        rejects(nativeCall,new int[]{2856,2856},matrices,grid);
        rejects(nativeCall,kelvins,new float[35],grid);
        rejects(nativeCall,kelvins,matrices,new int[5]);
        rejects(nativeCall,kelvins,matrices,new int[]{2000,10001,100,-100,100,25});
        rejects(nativeCall,kelvins,matrices,new int[]{2000,10000,0,-100,100,25});
        rejects(nativeCall,kelvins,matrices,new int[]{2000,10000,100,-101,100,25});
        float[] nan=matrices.clone();nan[0]=Float.NaN;
        rejects(nativeCall,kelvins,nan,grid);
        nan=matrices.clone();nan[7]=Float.POSITIVE_INFINITY;
        rejects(nativeCall,kelvins,nan,grid);
        nan=new float[36];
        rejects(nativeCall,kelvins,nan,grid);
        ok(HasselbladDomainDiagnostics.evaluateLatest().getJSONArray("points").length()==729);
        System.out.println("PASS Domain1 Java/JNI/owned-leaf checks="+checks+
            " synthetic grid points=729 render_applied=false");
    }
}
