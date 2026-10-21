package com.particlesdevs.photoncamera.hasselblad;

import com.particlesdevs.photoncamera.processing.ImageFrame;
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.ByteBuffer;

/** Single original RAW -> six explicitly experimental policies -> private JSON.
 * Runs synchronously before Photon mutates metadata/buffers. Never publishes a
 * render neutral, modifies a frame, or reuses a candidate from an earlier shot. */
public final class HasselbladSceneDiagnostics {
    private static volatile String latest = "Scene diagnostics: no capture yet.";
    private static boolean loaded;
    private static native double[] nativeSweep(ByteBuffer raw, int[] geometry,
                                               double[] black, float[] matrices);
    private HasselbladSceneDiagnostics() {}
    public static String latestSummary() { return latest; }
    public static void reset() { latest = "Scene diagnostics: unavailable for latest capture."; }
    private static synchronized void load() {
        if (!loaded) { System.loadLibrary("hasselblad_scene_jni"); loaded=true; }
    }

    public static JSONObject run(JSONObject capture, ImageFrame frame) {
        JSONObject out = new JSONObject();
        long started=System.nanoTime();
        try {
            out.put("schema", "hasselblad-phone-scene-diagnostics-v1");
            out.put("render_applied", false);
            out.put("full_automatic_controller", false);
            out.put("policy_calibrated", false);
            out.put("selection_uses_hal_neutral", false);
            out.put("raw_sensor_timestamp_ns", Long.toString(frame.rawSensorTimestampNs));
            out.put("frame_number", capture.opt("frame_number"));
            out.put("scope", "Original full single RAW, phone matrices, six acceptance tests; no production policy selected.");
            require(capture.getBoolean("calibration_evidence_usable"), "capture_identity_or_metadata_unproven");
            require(frame.rawSensorTimestampNs>0 && !frame.fp16 && frame.packedBits==0
                    && !frame.sourceBinned, "processed_or_unknown_raw");
            require(frame.width==frame.sourceRawWidth && frame.height==frame.sourceRawHeight
                    && frame.cropOriginX==0 && frame.cropOriginY==0 && frame.sourceCopyOffsetBytes==0
                    && frame.sourcePixelStride==2 && (long)frame.width*2==frame.sourceRowStride,
                    "only_full_tightly_packed_raw16_supported");
            require(frame.buffer!=null && frame.buffer.isDirect() && frame.buffer.position()==0
                    && frame.buffer.limit()==frame.buffer.capacity()
                    && frame.buffer.capacity()==(long)frame.width*frame.height*2,
                    "raw_buffer_extent_unproven");
            JSONObject original=capture.getJSONObject("original_still");
            JSONObject chars=original.getJSONObject("selected_sensor_characteristics");
            JSONObject result=original.getJSONObject("selected_raw_sensor_result");
            JSONArray pixels=chars.getJSONArray("android.sensor.info.pixelArraySize");
            require(pixels.length()==2 && pixels.getInt(0)==frame.width && pixels.getInt(1)==frame.height,
                    "sensor_crop_or_scale_mapping_unproven");
            JSONArray crop=capture.getJSONObject("delivered_raw").getJSONArray("image_crop_rect");
            require(crop.length()==4 && crop.getInt(0)==0 && crop.getInt(1)==0
                    && crop.getInt(2)==frame.width && crop.getInt(3)==frame.height, "partial_image_crop_unsupported");
            require(Long.toString(frame.rawSensorTimestampNs).equals(result.getString("android.sensor.timestamp")),
                    "raw_result_timestamp_mismatch");
            // Missing pixel mode is permitted only without the high-resolution capability.
            JSONArray caps=chars.getJSONArray("android.request.availableCapabilities");
            boolean ultra=false,remosaic=false,rawCapability=false;
            // Public CameraMetadata capability values: RAW=3, ultra-high-resolution=16, remosaic=17.
            for(int i=0;i<caps.length();i++) {
                if(caps.getInt(i)==16)ultra=true;
                if(caps.getInt(i)==17)remosaic=true;
                if(caps.getInt(i)==3)rawCapability=true;
            }
            require(rawCapability,"selected_camera_does_not_advertise_raw");
            boolean binningKnown=!result.isNull("android.sensor.rawBinningFactorUsed");
            require((!ultra || !remosaic || binningKnown)
                    && (!binningKnown || !result.getBoolean("android.sensor.rawBinningFactorUsed")),
                    "non_bayer_or_unknown_raw_binning");
            Object pixelMode=result.opt("android.sensor.pixelMode");
            require((pixelMode!=null && pixelMode!=JSONObject.NULL && result.getInt("android.sensor.pixelMode")==0)
                    || ((pixelMode==null || pixelMode==JSONObject.NULL) && !ultra), "maximum_resolution_or_unknown_pixel_mode");
            int cfa=chars.getInt("android.sensor.info.colorFilterArrangement");
            require(cfa>=0 && cfa<=3, "unsupported_cfa");
            JSONArray blacks=result.optJSONArray("android.sensor.dynamicBlackLevel");
            String blackSource="original_still_dynamic";
            if(blacks==null) {blacks=chars.getJSONArray("android.sensor.blackLevelPattern");blackSource="original_static_fallback";}
            require(blacks.length()==4,"invalid_black_levels");
            double[] black=new double[4];
            int white=result.isNull("android.sensor.dynamicWhiteLevel")
                    ? chars.getInt("android.sensor.info.whiteLevel") : result.getInt("android.sensor.dynamicWhiteLevel");
            for(int i=0;i<4;i++) {
                black[i]=blacks.getDouble(i);
                require(Double.isFinite(black[i]) && black[i]>=0 && black[i]<white && black[i]==black[0]
                        && black[i]*65536.0==Math.rint(black[i]*65536.0),
                        "unequal_or_invalid_black_spans_not_supported");
            }
            int k1=kelvin(chars.getInt("android.sensor.referenceIlluminant1"));
            int k2=kelvin(chars.getInt("android.sensor.referenceIlluminant2"));
            require(k1!=k2,"distinct_A_D65_anchors_required");
            float[] matrices=new float[36];
            for(int a=0;a<2;a++) {
                readMatrix(chars.getJSONArray("android.sensor.colorTransform"+(a+1)), matrices,a*18);
                readMatrix(chars.getJSONArray("android.sensor.calibrationTransform"+(a+1)), matrices,a*18+9);
            }
            out.put("black_source",blackSource); out.put("black_site_order_raw_counts",new JSONArray(black));
            out.put("white_source",result.isNull("android.sensor.dynamicWhiteLevel") ? "original_static_fallback" : "original_still_dynamic");
            out.put("white_raw_counts",white);
            out.put("matrix_source","original_selected_sensor_Camera2_before_Photon_normalization");
            out.put("sensor_provenance",original.getJSONObject("sensor_provenance"));
            out.put("center_tint",0); out.put("neighbor_factor",2); out.put("minimum_blocks",16);
            out.put("minimum_bayer_brightness",.005); out.put("maximum_bayer_brightness",.9);
            out.put("ct_locus_kelvin","2000..10000 step 100, green-relative Q12");
            out.put("filter_topology","retained native linear offsets, including cross-row links");
            out.put("lens_shading_applied",false);
            load();
            // Synchronous borrow: HdrxProcessor has not packed/normalized/freed the frame.
            double[] wire=nativeSweep(frame.buffer, new int[]{frame.width,frame.height,frame.sourceRowStride,cfa,white,k1,k2},black,matrices);
            require(wire!=null && wire.length==138 && wire[0]==1,"native_wire_format_mismatch");
            for(double v:wire) require(Double.isFinite(v),"nonfinite_native_output");
            out.put("raw_adapter_status",(int)wire[1]);
            require(wire[1]==0,"native_raw_adapter_rejected");
            out.put("raw_valid_blocks",(int)wire[2]); out.put("nonpositive_blocks",(int)wire[3]);
            out.put("saturated_blocks",(int)wire[4]); out.put("raw_ratio_range_blocks",(int)wire[5]);
            JSONArray policies=new JSONArray(); int candidates=0,errors=0;
            for(int p=0;p<6;p++) {
                int o=6+22*p; JSONObject row=new JSONObject();
                row.put("radius_q12",(int)wire[o]); row.put("adapter_status",(int)wire[o+1]);
                row.put("decision",wire[o+1]!=0 ? "adapter_rejected" : wire[o+2]==1
                        ? "diagnostic_candidate" : wire[o+2]==2 ? "temperature_rejected" : "no_candidate");
                row.put("native_status",(int)wire[o+3]); row.put("raw_valid_blocks",(int)wire[o+4]);
                row.put("admitted_blocks",(int)wire[o+5]); row.put("classified_blocks",(int)wire[o+6]);
                row.put("retained_blocks",(int)wire[o+7]);
                boolean candidate=wire[o+1]==0 && wire[o+2]==1;
                row.put("gain_q12",candidate ? triple(wire,o+8) : JSONObject.NULL);
                row.put("neutral_green_normalized",candidate ? triple(wire,o+11) : JSONObject.NULL);
                row.put("temperature_kelvin_tint_residual",candidate ? triple(wire,o+14) : JSONObject.NULL);
                row.put("raw_rejected_blocks",(int)wire[o+17]); row.put("brightness_rejected_blocks",(int)wire[o+18]);
                row.put("signed_gain_rejected_blocks",(int)wire[o+19]); row.put("outside_locus_blocks",(int)wire[o+20]);
                row.put("component_removed_blocks",(int)wire[o+21]);
                policies.put(row); if(candidate)candidates++; if(wire[o+1]!=0)errors++;
            }
            out.put("policies",policies); out.put("status",errors==0 ? "completed" : "native_policy_errors");
            latest="Scene diagnostics: "+candidates+" of 6 test settings produced a candidate; "
                    +errors+" errors. Photo colour still uses Photon.";
        } catch (LinkageError e) {
            putFailure(out,"unavailable","arm64_native_library_unavailable");
        } catch (OutOfMemoryError e) {
            putFailure(out,"unavailable","diagnostic_workspace_allocation_failed");
        } catch (Exception e) {
            putFailure(out,"skipped",e.getMessage()==null ? e.getClass().getSimpleName() : e.getMessage());
        }
        try { out.put("elapsed_ms",(System.nanoTime()-started)/1000000.0); } catch(Exception ignored) {}
        return out;
    }
    private static void putFailure(JSONObject out,String status,String reason) {
        latest="Scene diagnostics: "+status+" ("+reason+").";
        try {out.put("status",status);out.put("reason",reason);} catch(Exception ignored) {}
    }
    private static void require(boolean valid,String reason) {if(!valid)throw new IllegalArgumentException(reason);}
    private static int kelvin(int illuminant) {
        if(illuminant==17)return 2856;if(illuminant==21)return 6504;
        throw new IllegalArgumentException("only_A_and_D65_anchors_supported");
    }
    private static void readMatrix(JSONArray values,float[] out,int offset) throws Exception {
        require(values.length()==9,"matrix_requires_nine_rationals");
        for(int i=0;i<9;i++) {
            JSONObject r=values.getJSONObject(i);int n=r.getInt("numerator"),d=r.getInt("denominator");
            require(d!=0,"invalid_matrix_denominator");
            // Same float32 division as android.util.Rational.floatValue().
            out[offset+i]=(float)n/(float)d;
            require(Float.isFinite(out[offset+i]),"nonfinite_matrix");
        }
    }
    private static JSONArray triple(double[] x,int start) throws Exception {
        return new JSONArray().put(x[start]).put(x[start+1]).put(x[start+2]);
    }
}
