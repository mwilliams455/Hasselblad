package com.particlesdevs.photoncamera.hasselblad;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Locale;

/** Explicit user-picked read-only DNG; no photo/camera side effects or network. */
public final class HasselbladRealDngDiagnostic {
    private HasselbladRealDngDiagnostic() { }
    private static String hex(byte[] bytes) {
        StringBuilder b=new StringBuilder(bytes.length*2);
        for(byte x:bytes)b.append(String.format(Locale.US,"%02x",x&255));
        return b.toString();
    }
    private static void safePut(JSONObject object, String key, Object value) {
        try { object.put(key,value); } catch (Exception ignored) { }
    }
    public static String inspect(Context context,Uri document) {
        JSONObject r=new JSONObject();
        File temporary=null;
        String status="INPUT_ERROR";
        long started=System.nanoTime();
        try {
            r.put("schema","hasselblad-stage32-real-dng-centre-tile-v1");
            r.put("input_is_synthetic",false);
            r.put("source","user_selected_local_DNG_SAF");
            r.put("source_timestamp_is_camera_capture_timestamp",false);
            r.put("physical_sensor_binding_proven",false);
            r.put("photographic_colour_still_photon",true);
            r.put("original_hasselblad_ccm_pixel_proven",false);
            r.put("hncs_rendering_performed",false);
            r.put("saved_photo_or_original_dng_modified",false);
            r.put("image_exported",false);
            r.put("pixel_values_in_json",false);
            temporary=File.createTempFile("hb32-readonly-", ".dng",context.getCacheDir());
            MessageDigest hash=MessageDigest.getInstance("SHA-256");
            long copied=0;
            ContentResolver content=context.getContentResolver();
            try(InputStream in=content.openInputStream(document);
                FileOutputStream out=new FileOutputStream(temporary)) {
                if(in==null)throw new IllegalArgumentException("SAF provider returned no file");
                byte[] buffer=new byte[64*1024];int n;
                while((n=in.read(buffer))!=-1){
                    if(n==0)continue;
                    if(copied+n>HasselbladDngTileReader.MAX_FILE_BYTES)
                        throw new IllegalArgumentException("DNG exceeds bounded local diagnostic size");
                    hash.update(buffer,0,n);out.write(buffer,0,n);copied+=n;
                }
            }
            r.put("source_dng_sha256",hex(hash.digest()));
            r.put("source_dng_bytes",copied);
            try {
                HasselbladDngTileReader.ReadResult parsed=HasselbladDngTileReader.read(temporary);
                r.put("raw_dimensions",new org.json.JSONArray().put(parsed.width).put(parsed.height));
                r.put("original_bits",parsed.originalBits);
                r.put("raw_strip_count",parsed.stripCount);
                r.put("CFA","RGGB");
                r.put("decoded_sample_count",HasselbladDngTileReader.TILE_SIZE*HasselbladDngTileReader.TILE_SIZE);
                r.put("decoded_tile_is_full_frame",false);
                r.put("gainmap_opcode_state",parsed.gainState);
                r.put("gainmap_count",parsed.gainMapCount);
                r.put("gainmap_roi_site_applications",parsed.gainAppliedSamples);
                r.put("gainmap_sdk_bit_exact_proven",false);
                r.put("demosaic","Stage32_bounded_bilinear_reference_not_Photon_or_X2D");
                if(!parsed.hasPcsInput()){
                    status="RAW_TILE_PASS_PCS_METADATA_UNAVAILABLE";
                    r.put("native_status","not_invoked_missing_DNG_ForwardMatrix1_or_AsShotNeutral");
                }else{
                    try{
                        System.loadLibrary("hasselblad_colour_reference_jni");
                        double[] converted=new double[32*32*3];
                        int code=HasselbladColourReferenceCheck.nativeLinearTile(
                            parsed.forwardMatrix1,parsed.forwardMatrix2,
                            parsed.calibration1,parsed.calibration2,
                            parsed.analogBalance,parsed.asShotNeutral,
                            0,parsed.cameraLinearTile,32*32,converted);
                        r.put("native_stage24_status_code",code);
                        if(code==0){
                            double[] low={Double.POSITIVE_INFINITY,Double.POSITIVE_INFINITY,Double.POSITIVE_INFINITY};
                            double[] high={Double.NEGATIVE_INFINITY,Double.NEGATIVE_INFINITY,Double.NEGATIVE_INFINITY};
                            double[] sum={0,0,0};
                            int negative=0,over=0;
                            for(int i=0;i<converted.length;i++){
                                double v=converted[i];
                                if(!Double.isFinite(v))throw new IllegalStateException("native colour returned nonfinite");
                                int ch=i%3;low[ch]=Math.min(low[ch],v);high[ch]=Math.max(high[ch],v);
                                sum[ch]+=v;if(v<0)negative++;if(v>1)over++;
                            }
                            // Only aggregate statistics; no samples/calibration or photo values.
                            r.put("linear_channel_min",new org.json.JSONArray().put(low[0]).put(low[1]).put(low[2]));
                            r.put("linear_channel_mean",new org.json.JSONArray().put(sum[0]/1024).put(sum[1]/1024).put(sum[2]/1024));
                            r.put("linear_channel_max",new org.json.JSONArray().put(high[0]).put(high[1]).put(high[2]));
                            r.put("negative_components",negative);r.put("over_unity_components",over);
                            status="PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY";
                            r.put("native_stage24_PCS_only",true);
                        }else{
                            status="RAW_TILE_PASS_NATIVE_PROFILE_UNSUPPORTED";
                            r.put("native_stage24_PCS_only",false);
                            // Most dual-illuminant profiles require SDK interpolation
                            // not implemented by the Stage24/26 bridge.
                            r.put("native_limitation","Stage24_rejects_unverified_dual_illuminant_profiles");
                        }
                    }catch(UnsatisfiedLinkError e){
                        status="RAW_TILE_PASS_ARM64_NATIVE_UNAVAILABLE";
                        r.put("native_status","native_library_unavailable_on_this_ABI");
                    }
                }
            }catch(HasselbladDngTileReader.Unsupported unsupported){
                status="UNSUPPORTED_REAL_DNG";
                r.put("reason",unsupported.code);
                r.put("raw_tile_processed",false);
            }
        }catch(Throwable e){
            status="INPUT_ERROR";
            // Avoid original filename/URI/path/device IDs or stack traces in report.
            r.remove("source_dng_sha256");
            safePut(r,"error_class",e.getClass().getSimpleName());
        }finally{
            if(temporary!=null&&!temporary.delete()){
                safePut(r,"temporary_file_deleted",false);
            }else safePut(r,"temporary_file_deleted",true);
        }
        try{
            r.put("status",status);
            r.put("elapsed_ms",Math.round((System.nanoTime()-started)/1e6));
        }catch(Exception ignored){}
        return r.toString();
    }
}
