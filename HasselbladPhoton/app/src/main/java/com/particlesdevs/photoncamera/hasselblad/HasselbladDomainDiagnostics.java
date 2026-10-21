package com.particlesdevs.photoncamera.hasselblad;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * On-demand, diagnostic-only Domain1 sweep of the latest proven physical
 * sensor's ORIGINAL Camera2 calibration. No RAW, HAL white balance or
 * photographic renderer is an input. Never invoked on the shutter hot path.
 *
 * Only a small immutable snapshot is cached in memory during the app session;
 * reopening the app requires another properly bound RAW capture. The snapshot
 * is labelled with its original frame/timestamp and physical camera ID.
 */
public final class HasselbladDomainDiagnostics {
    private static volatile String lastOriginalCalibration;
    private static native long[] nativeEvaluate(int[] illuminants, float[] matrices, int[] request);
    private static final int[] GRID = {2000, 10000, 100, -100, 100, 25};
    private static final int HEADER = 8;
    private static final int POINT_FIELDS = 7;
    private static boolean libraryLoaded;

    private HasselbladDomainDiagnostics() { }

    public static void clear() { lastOriginalCalibration = null; }

    /** Called during evidence collection, but does not run any native sweep. */
    public static void rememberCapture(JSONObject capture) {
        lastOriginalCalibration = null;
        try {
            require(capture.getBoolean("calibration_evidence_usable"),
                    "capture provenance not usable");
            JSONObject original = capture.getJSONObject("original_still");
            JSONObject prov = original.getJSONObject("sensor_provenance");
            require(prov.getBoolean("sensor_provenance_matched")
                    && prov.getBoolean("result_camera_id_matched")
                    && prov.getBoolean("request_targets_recorded_raw_surface")
                    && prov.getBoolean("selected_and_logical_frame_number_matched")
                    && !prov.getBoolean("selected_characteristics_are_logical"),
                    "physical RAW sensor provenance not verified");
            String cameraId=prov.getString("selected_calibration_camera_id");
            require(!cameraId.isEmpty() &&
                    cameraId.equals(prov.getString("selected_result_camera_id")),
                    "original physical sensor mismatch");
            String timestamp=original.getString("selected_sensor_timestamp_ns");
            require(timestamp.matches("[0-9]+") &&
                    timestamp.equals(original.getJSONObject("selected_raw_sensor_result")
                        .getString("android.sensor.timestamp")),
                    "original frame timestamp mismatch");
            String frame=capture.getString("frame_number");
            require(frame.matches("[0-9]+") &&
                    frame.equals(original.getString("selected_result_frame_number")),
                    "original RAW frame number mismatch");
            JSONObject characteristics=original.getJSONObject("selected_sensor_characteristics");
            JSONObject stored=new JSONObject();
            stored.put("physical_sensor_id",cameraId);
            stored.put("frame_number",frame);
            stored.put("sensor_timestamp_ns",timestamp);
            stored.put("reference_illuminant1",characteristics.getInt("android.sensor.referenceIlluminant1"));
            stored.put("reference_illuminant2",characteristics.getInt("android.sensor.referenceIlluminant2"));
            for (int i=1;i<=2;i++) {
                stored.put("color"+i,new JSONArray(characteristics.getJSONArray(
                        "android.sensor.colorTransform"+i).toString()));
                stored.put("calibration"+i,new JSONArray(characteristics.getJSONArray(
                        "android.sensor.calibrationTransform"+i).toString()));
            }
            // Cache only after all evidence and copy checks have passed.
            lastOriginalCalibration=stored.toString();
        } catch (Exception failure) {
            lastOriginalCalibration=null;
        }
    }

    public static boolean hasVerifiedCapture() {
        return lastOriginalCalibration != null;
    }

    /** Run on a background thread from the development screen, never on shutter. */
    public static JSONObject evaluateLatest() {
        long started=System.nanoTime();
        JSONObject out=new JSONObject();
        try {
            out.put("schema","hasselblad-phone-domain1-on-demand-v1");
            out.put("render_applied",false);
            out.put("shipping_policy_selected",false);
            out.put("full_automatic_controller",false);
            out.put("selection_uses_hal_neutral",false);
            out.put("scene_candidate_selected",false);
            out.put("original_scene1b_policies_changed",false);
            out.put("scope","Original proven physical camera metadata; explicit 729-point temperature/tint coverage; representability only.");
            String saved=lastOriginalCalibration;
            require(saved!=null,"no_verified_capture_this_app_session");
            JSONObject metadata=new JSONObject(saved);
            out.put("physical_sensor_id",metadata.getString("physical_sensor_id"));
            out.put("source_frame_number",metadata.getString("frame_number"));
            out.put("source_sensor_timestamp_ns",metadata.getString("sensor_timestamp_ns"));
            out.put("matrix_source","original_camera2_characteristics_before_Photon_fix");
            int[] kelvins={illuminant(metadata.getInt("reference_illuminant1")),
                    illuminant(metadata.getInt("reference_illuminant2"))};
            require(kelvins[0]!=kelvins[1],"duplicate_reference_illuminants");
            float[] matrices=new float[36];
            for (int a=1;a<=2;a++) {
                matrix(metadata.getJSONArray("color"+a),matrices,(a-1)*18);
                matrix(metadata.getJSONArray("calibration"+a),matrices,(a-1)*18+9);
            }
            load();
            long[] wire=nativeEvaluate(kelvins,matrices,GRID.clone());
            require(wire!=null && wire.length==HEADER+729*POINT_FIELDS &&
                    wire[0]==1 && wire[1]==81 && wire[2]==9 && wire[3]==729,
                    "unsupported_native_domain_wire");
            long valid=wire[4],clipped=wire[5],signed=wire[6],duplicate=wire[7];
            require(valid>=0 && clipped>=0 && signed>=0 && duplicate>=0 &&
                    valid+clipped+signed+duplicate==729,"invalid_native_domain_counts");
            JSONObject request=new JSONObject();
            request.put("kelvin_first",GRID[0]);request.put("kelvin_last",GRID[1]);
            request.put("kelvin_step",GRID[2]);request.put("tint_first",GRID[3]);
            request.put("tint_last",GRID[4]);request.put("tint_step",GRID[5]);
            request.put("point_order","tint-major, ascending kelvin");
            out.put("requested_grid",request);
            JSONObject counts=new JSONObject();
            counts.put("representable",valid);
            counts.put("temperature_clipped",clipped);
            counts.put("scene_signed_gain",signed);
            counts.put("adjacent_duplicate",duplicate);
            counts.put("total",729);
            out.put("counts",counts);
            JSONArray points=new JSONArray();
            int[] observed=new int[4];
            for (int i=0;i<729;i++) {
                int o=HEADER+POINT_FIELDS*i;
                int kelvin=(int)wire[o],tint=(int)wire[o+1],reason=(int)wire[o+2],
                        status=(int)wire[o+3];
                require(kelvin==GRID[0]+(i%81)*GRID[2] &&
                        tint==GRID[3]+(i/81)*GRID[5] &&
                        reason>=0 && reason<4,
                        "native_domain_point_order_or_reason");
                boolean present=reason==0;
                require(present ? status==0 && wire[o+4]>0 && wire[o+5]==4096 &&
                        wire[o+6]>0 : wire[o+4]==0 && wire[o+5]==0 && wire[o+6]==0,
                        "invalid_domain_exclusion_values");
                if (reason==1) require(status==4,"converter_clip_without_status");
                if (reason==2 || reason==3) require(status==0,"scene_exclusion_with_converter_error");
                observed[reason]++;
                JSONObject point=new JSONObject();
                point.put("kelvin",kelvin);
                point.put("tint",tint);
                point.put("exclusion",reason==0?"representable":reason==1?
                        "temperature_clipped":reason==2?"scene_signed_gain":"adjacent_duplicate");
                point.put("temperature_status",status);
                point.put("gain_q12",present?new JSONArray()
                        .put(wire[o+4]).put(wire[o+5]).put(wire[o+6]):JSONObject.NULL);
                points.put(point);
            }
            require(observed[0]==valid && observed[1]==clipped &&
                    observed[2]==signed && observed[3]==duplicate,
                    "native_domain_counter_mismatch");
            out.put("points",points);
            out.put("status","completed");
        } catch (LinkageError ex) {
            failure(out,"unavailable","arm64_domain_library_unavailable");
        } catch (OutOfMemoryError ex) {
            failure(out,"unavailable","domain_workspace_allocation_failed");
        } catch (Exception ex) {
            failure(out,"skipped",ex.getMessage()==null?"unsupported_input":ex.getMessage());
        }
        try {out.put("elapsed_ms",(System.nanoTime()-started)/1000000.0);}
        catch(Exception ignored) {}
        return out;
    }

    public static String summary(JSONObject report) {
        if (!"completed".equals(report.optString("status"))) {
            return "Domain1: "+report.optString("status","skipped")+
                    " ("+report.optString("reason","unknown")+"). "+
                    "No photographic changes.";
        }
        JSONObject counts=report.optJSONObject("counts");
        return "Domain1 on-demand: "+(counts==null?"?":counts.optInt("representable"))+
                "/729 representable; physical camera "+report.optString("physical_sensor_id","?")+
                ". Zero pixels changed. Use Copy coverage JSON for all exclusions.";
    }

    private static synchronized void load() {
        if (!libraryLoaded) {
            System.loadLibrary("hasselblad_domain_jni");
            libraryLoaded=true;
        }
    }
    private static int illuminant(int code) {
        if(code==17)return 2856;
        if(code==21)return 6504;
        throw new IllegalArgumentException("only_A_D65_anchors_supported");
    }
    private static void matrix(JSONArray rational,float[] output,int offset) throws Exception {
        require(rational.length()==9,"matrix_requires_nine_rationals");
        for (int i=0;i<9;i++) {
            JSONObject r=rational.getJSONObject(i);
            int numerator=r.getInt("numerator"),denominator=r.getInt("denominator");
            require(denominator!=0,"invalid_matrix_denominator");
            output[offset+i]=(float)numerator/(float)denominator;
            require(Float.isFinite(output[offset+i]) && Math.abs(output[offset+i])<=16,
                    "invalid_Camera2_matrix_coefficient");
        }
    }
    private static void require(boolean condition,String message) {
        if (!condition)throw new IllegalArgumentException(message);
    }
    private static void failure(JSONObject out,String status,String reason) {
        try {out.put("status",status);out.put("reason",reason);}
        catch(Exception ignored) {}
    }
}
