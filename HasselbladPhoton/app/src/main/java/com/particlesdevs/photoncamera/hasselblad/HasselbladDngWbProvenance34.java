package com.particlesdevs.photoncamera.hasselblad;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/**
 * Stage34: read-only DNG AsShotNeutral versus ORIGINAL Camera2 and effective
 * Photon neutral from its independently hash-bound .capture.json sidecar.
 *
 * This class has no Camera2 / shutter / rendering hooks and never mutates the
 * selected documents. It refuses mismatched sources, exports only comparisons
 * and always destroys its bounded temporary DNG copy. Not an HNCS renderer.
 */
public final class HasselbladDngWbProvenance34 {
    private HasselbladDngWbProvenance34() { }
    private static final int MAX_SIDECAR_BYTES = 4 * 1024 * 1024;
    private static final String STAGE32_SCHEMA = "hasselblad-stage32-real-dng-centre-tile-v1";
    private static final String CAPTURE_SCHEMA = "hasselblad-photon-capture-evidence-v1";

    private static final class Unproven extends Exception {
        Unproven(String code) { super(code); }
    }
    private static void require(boolean test, String reason) throws Unproven {
        if (!test) throw new Unproven(reason);
    }
    private static String hex(byte[] digest) {
        StringBuilder out = new StringBuilder(digest.length * 2);
        for (byte b : digest) out.append(String.format(Locale.US, "%02x", b & 0xff));
        return out.toString();
    }
    private static boolean sameDigest(String a, String b) {
        return a != null && b != null && a.matches("[0-9a-f]{64}")
            && b.matches("[0-9a-f]{64}")
            && MessageDigest.isEqual(a.getBytes(StandardCharsets.US_ASCII),
                                     b.getBytes(StandardCharsets.US_ASCII));
    }
    private static double[] asRationals(JSONArray values,int len) throws Exception {
        require(values.length()==len,"camera2_rational_matrix_shape_invalid");
        double[] result=new double[len];
        for (int i=0;i<len;i++) {
            JSONObject x=values.getJSONObject(i);
            double numerator=x.getDouble("numerator"),denominator=x.getDouble("denominator");
            require(Double.isFinite(numerator)&&Double.isFinite(denominator)&&denominator!=0,
                    "camera2_invalid_rational");
            result[i]=numerator/denominator;
        }
        return result;
    }
    private static double[] asDoubles(JSONArray arr,int n) throws Exception {
        require(arr.length()==n,"photon_effective_field_wrong_length");
        double[] result=new double[n];
        for(int i=0;i<n;i++){
            result[i]=arr.getDouble(i);
            require(Double.isFinite(result[i]),"photon_effective_field_nonfinite");
        }
        return result;
    }
    private static boolean decimalEquals(String a,String b){
        return a!=null&&a.matches("[0-9]{1,20}")&&a.equals(b);
    }
    private static JSONObject readSidecar(ContentResolver resolver,Uri source)throws Exception {
        try(InputStream stream=resolver.openInputStream(source)){
            require(stream!=null,"capture_json_unreadable");
            ByteArrayOutputStream dest=new ByteArrayOutputStream();
            byte[] buffer=new byte[16384];int count;
            while((count=stream.read(buffer))!=-1){
                if(count==0)continue;
                require(dest.size()<=MAX_SIDECAR_BYTES-count,"capture_json_too_large");
                dest.write(buffer,0,count);
            }
            require(dest.size()>0,"capture_json_empty");
            return new JSONObject(dest.toString(StandardCharsets.UTF_8.name()));
        }
    }
    private static long copyDngAndHash(ContentResolver resolver,Uri source,
                                       File dest,MessageDigest digest)throws Exception {
        long total=0;
        try(InputStream input=resolver.openInputStream(source);
            FileOutputStream output=new FileOutputStream(dest)) {
            require(input!=null,"dng_document_unreadable");
            byte[] buffer=new byte[65536];int count;
            while((count=input.read(buffer))!=-1){
                if(count==0)continue;
                require(total<=HasselbladDngTileReader.MAX_FILE_BYTES-count,
                        "dng_file_over_maximum_size");
                output.write(buffer,0,count);
                digest.update(buffer,0,count);
                total+=count;
            }
        }
        require(total>0,"dng_empty");
        return total;
    }
    private static void validateSidecarBinding(JSONObject record,String digest,long bytes,
                                              int width,int height)throws Exception {
        require(CAPTURE_SCHEMA.equals(record.optString("schema")),"capture_schema_wrong");
        JSONObject saved=record.getJSONObject("dng");
        require(sameDigest(digest,saved.getString("sha256")),"dng_hash_sidecar_mismatch");
        require(saved.getLong("bytes")==bytes,"dng_bytes_sidecar_mismatch");
        require(record.optBoolean("calibration_evidence_usable",false),
                "capture_calibration_evidence_not_usable");
        require(record.optInt("input_frame_count",0)==1,"capture_not_one_raw_frame");
        require("image_timestamp_equals_selected_still_result_timestamp".equals(
                record.optString("pairing_status")),"capture_sensor_timestamp_pairing_bad");
        JSONObject original=record.getJSONObject("original_still");
        JSONObject provenance=original.getJSONObject("sensor_provenance");
        for(String field:new String[]{"sensor_provenance_matched","result_camera_id_matched",
                "request_targets_recorded_raw_surface","selected_and_logical_frame_number_matched"}){
            require(provenance.optBoolean(field,false),"physical_provenance_"+field+"_missing");
        }
        require(!provenance.optBoolean("selected_characteristics_are_logical",true),
                "physical_sensor_not_established");
        String sensor=provenance.getString("selected_calibration_camera_id");
        require(sensor.length()>0&&sensor.equals(provenance.getString("selected_result_camera_id")),
                "selected_physical_sensor_id_mismatch");
        String frame=record.getString("frame_number");
        require(decimalEquals(frame,original.getString("selected_result_frame_number")),
                "capture_frame_number_mismatch");
        String timestamp=original.getString("selected_sensor_timestamp_ns");
        require(decimalEquals(timestamp,original.getJSONObject("selected_raw_sensor_result")
                .getString("android.sensor.timestamp")),"camera2_capture_result_timestamp_mismatch");
        JSONObject raw=record.getJSONObject("delivered_raw");
        require(decimalEquals(timestamp,raw.getString("sensor_timestamp_ns")),
                "delivered_raw_timestamp_mismatch");
        require(raw.getInt("format")==32&&raw.getInt("pixel_stride_bytes")==2,
                "delivered_raw_not_16bit_RAW_SENSOR");
        require(raw.getInt("delivered_width")==width && raw.getInt("copied_width")==width
                &&raw.getInt("delivered_height")==height&&raw.getInt("copied_height")==height,
                "recorded_raw_dimensions_do_not_match_dng");
        require(raw.getInt("copy_offset_bytes")==0&&raw.getInt("copied_crop_x")==0
                &&raw.getInt("copied_crop_y")==0&&!raw.getBoolean("binned"),
                "raw_capture_copy_is_cropped_or_binned");
        require(original.getJSONObject("selected_sensor_characteristics")
                .getInt("android.sensor.info.colorFilterArrangement")==0,
                "selected_physical_sensor_not_RGGB");
    }
    private static String safeError(String failure){
        // Errors never contain filenames, file URIs, actual camera IDs or raw
        // calibration values: only fixed audit reason tokens are emitted.
        return failure.matches("[a-zA-Z0-9_]{1,100}")?failure:"unsupported_input";
    }
    public static String verify(Context context,Uri dngUri,Uri sidecarUri,
                                String previousStage32Json) {
        JSONObject report=new JSONObject();File temporary=null;
        long started=System.nanoTime();String status="NOT_PROVEN";
        try{
            report.put("schema","hasselblad-stage34-dng-AsShotNeutral-provenance-v1");
            report.put("source","explicitly_selected_existing_DNG_and_capture_JSON");
            report.put("raw_pixels_exported",false);
            report.put("private_camera_identifiers_or_calibration_matrices_exported",false);
            report.put("saved_photo_or_original_DNG_modified",false);
            report.put("photographic_colour_still_photon",true);
            report.put("HNCS_pixel_equivalence_proven",false);
            report.put("independent_hardware_attestation",false);
            require(dngUri!=null&&sidecarUri!=null&&previousStage32Json!=null,
                    "both_documents_and_stage32_result_required");
            JSONObject stage32=new JSONObject(previousStage32Json);
            require(STAGE32_SCHEMA.equals(stage32.optString("schema"))
                  && "PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY".equals(stage32.optString("status"))
                  && stage32.optInt("native_stage24_status_code",-1)==0
                  && !stage32.optBoolean("input_is_synthetic",true),
                    "verified_real_stage32_result_required");
            ContentResolver resolver=context.getContentResolver();
            temporary=File.createTempFile("hb34-readonly-",".dng",context.getCacheDir());
            MessageDigest sha=MessageDigest.getInstance("SHA-256");
            long count=copyDngAndHash(resolver,dngUri,temporary,sha);
            String digest=hex(sha.digest());
            require(sameDigest(digest,stage32.getString("source_dng_sha256"))
                    && count==stage32.getLong("source_dng_bytes"),
                    "current_DNG_is_not_stage32_selected_DNG");
            JSONObject sidecar=readSidecar(resolver,sidecarUri);
            HasselbladDngTileReader.ReadResult dng=HasselbladDngTileReader.read(temporary);
            validateSidecarBinding(sidecar,digest,count,dng.width,dng.height);
            report.put("DNG_digest_matches_Stage32_and_capture_sidecar",true);
            report.put("recorded_physical_sensor_frame_and_timestamp_bound",true);
            report.put("DNG_raw_dimensions",new JSONArray().put(dng.width).put(dng.height));
            report.put("DNG_gainmap_count",dng.gainMapCount);
            JSONObject original=sidecar.getJSONObject("original_still");
            JSONObject raw=original.getJSONObject("selected_raw_sensor_result");
            JSONObject characteristics=original.getJSONObject("selected_sensor_characteristics");
            JSONObject effective=sidecar.getJSONObject("effective_photon_export");
            require(dng.asShotNeutral!=null,"DNG_AsShotNeutral_absent");
            double[] originalNeutral=asRationals(raw.getJSONArray("android.sensor.neutralColorPoint"),3);
            double[] effectiveNeutral=asDoubles(effective.getJSONArray("neutral_used"),3);
            HasselbladNeutralCompare34.Comparison comparison=
                    HasselbladNeutralCompare34.compareNeutrals(dng.asShotNeutral,
                                                               originalNeutral,effectiveNeutral);
            report.put("DNG_AsShotNeutral_origin",comparison.classification);
            report.put("DNG_neutral_matches_original_Camera2",comparison.matchesOriginal);
            report.put("DNG_neutral_matches_effective_Photon",comparison.matchesEffective);
            report.put("original_and_effective_neutrals_distinct",comparison.originalAndEffectiveDistinct);
            report.put("max_abs_original_vs_effective_neutral_delta",
                    comparison.maxAbsOriginalVsEffective);
            report.put("max_abs_DNG_vs_original_neutral_delta",
                    comparison.maxAbsDifferenceToOriginal);
            report.put("max_abs_DNG_vs_effective_neutral_delta",
                    comparison.maxAbsDifferenceToEffective);
            report.put("neutral_comparison_absolute_tolerance",
                    HasselbladNeutralCompare34.NEUTRAL_ABSOLUTE_TOLERANCE);
            report.put("ForwardMatrix1_match",HasselbladNeutralCompare34.compareOptionalMatrix(
                    dng.forwardMatrix1,
                    asRationals(characteristics.getJSONArray("android.sensor.forwardMatrix1"),9),
                    asDoubles(effective.getJSONArray("forward_matrix_1"),9)));
            report.put("ForwardMatrix2_match",HasselbladNeutralCompare34.compareOptionalMatrix(
                    dng.forwardMatrix2,
                    asRationals(characteristics.getJSONArray("android.sensor.forwardMatrix2"),9),
                    asDoubles(effective.getJSONArray("forward_matrix_2"),9)));
            report.put("CameraCalibration1_match",HasselbladNeutralCompare34.compareOptionalMatrix(
                    dng.calibration1,
                    asRationals(characteristics.getJSONArray("android.sensor.calibrationTransform1"),9),
                    asDoubles(effective.getJSONArray("calibration_transform_1"),9)));
            report.put("CameraCalibration2_match",HasselbladNeutralCompare34.compareOptionalMatrix(
                    dng.calibration2,
                    asRationals(characteristics.getJSONArray("android.sensor.calibrationTransform2"),9),
                    asDoubles(effective.getJSONArray("calibration_transform_2"),9)));
            report.put("matrix_comparison_absolute_tolerance",
                    HasselbladNeutralCompare34.MATRIX_ABSOLUTE_TOLERANCE);
            report.put("DNG_AsShotNeutral_directly_read",true);
            report.put("DNG_SDK_bit_exact_profile_interpolation_proven",false);
            status="PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED";
        }catch(Unproven e){
            try{report.put("reason",safeError(e.getMessage()));}catch(Exception ignored){}
        }catch(HasselbladDngTileReader.Unsupported e){
            try{report.put("reason", "DNG_"+safeError(e.code));}catch(Exception ignored){}
        }catch(Throwable e){
            try{report.put("reason","unsupported_"+safeError(e.getClass().getSimpleName()));}
            catch(Exception ignored){}
        }finally{
            if(temporary!=null){
                boolean erased=temporary.delete();
                try{report.put("temporary_file_deleted",erased);}catch(Exception ignored){}
                if(!erased)status="NOT_PROVEN";
            }else try{report.put("temporary_file_deleted",true);}catch(Exception ignored){}
        }
        try{
            report.put("status",status);
            report.put("elapsed_ms",Math.round((System.nanoTime()-started)/1e6));
        }catch(Exception ignored){}
        return report.toString();
    }
}
