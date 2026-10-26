package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.graphics.Bitmap;
import androidx.exifinterface.media.ExifInterface;
import com.particlesdevs.photoncamera.BuildConfig;
import com.particlesdevs.photoncamera.api.ParseExif;
import com.particlesdevs.photoncamera.processing.ImageFrame;
import com.particlesdevs.photoncamera.processing.ProcessingEventsListener;
import com.particlesdevs.photoncamera.processing.encoder.ImageFormatConfig;
import com.particlesdevs.photoncamera.processing.processor.ProcessorBase;
import com.particlesdevs.photoncamera.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.ArrayList;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Shutter integration; Stage87 records the selected look and optional sharpening; publication uses the existing DCIM document-tree grant. */
public final class HasselbladCapture79 {
    private static final String TAG="HasselbladCapture79";
    private static final Object REPORT_LOCK=new Object();
    private static boolean cleaned;
    private HasselbladCapture79() {}
    private static void remove(File f){if(f==null)return;if(f.isDirectory()){File[] files=f.listFiles();if(files!=null)for(File x:files)remove(x);}f.delete();}
    private static File latest(Context c){return new File(c.getCacheDir(),"hb82-latest");}
    private static void cleanupOnce(Context context) {
        synchronized(REPORT_LOCK) {
            if(cleaned)return;cleaned=true;
            File[] files=context.getCacheDir().listFiles();
            if(files!=null)for(File file:files)if(file.getName().startsWith("hb82-shot-") || file.getName().startsWith("hb81-shot-") || file.getName().startsWith("hb80-shot-") || file.getName().startsWith("hb79-shot-"))remove(file);
        }
    }
    private static JSONObject report(String status) throws Exception {
        return new JSONObject().put("schema","hasselblad-stage96-capture-v1").put("status",status)
                .put("version_name",BuildConfig.VERSION_NAME).put("version_code",BuildConfig.VERSION_CODE)
                .put("required_renderer","Hasselblad").put("photon_colour_applied",false)
                .put("source_commit",BuildConfig.HB88_SOURCE).put("physical_sensor_colour_match_proved",false)
                .put("private_profile_or_full_dng_exported",false);
    }
    private static void remember(Context context,JSONObject report,File results,boolean diagnostics) {
        synchronized(REPORT_LOCK) {
            // Keep only a small human-readable result when diagnostic exports are off.
            try {context.getSharedPreferences("hasselblad-capture94",Context.MODE_PRIVATE).edit()
                    .putString("last_status",display94(report)).apply();}
            catch(Exception e){Log.e(TAG,"Cannot retain capture status",e);}
            File target=latest(context);remove(target);
            if(!diagnostics||!HasselbladDiagnostics86.enabled(context))return;
            try {
                if(!target.mkdir())throw new IOException("Cannot create capture report folder");
                if(results!=null)for(File f:results.listFiles())
                    if(f.getName().equals("automatic-colour.jpg") || f.getName().matches("sample[0-2]\\.(input|rgb)\\.u16le"))
                        Files.copy(f.toPath(),new File(target,f.getName()).toPath());
                Files.write(new File(target,"report.json").toPath(),report.toString(2).getBytes(StandardCharsets.UTF_8));
            }catch(Exception e){remove(target);Log.e(TAG,"Capture report unavailable",e);}
        }
    }
    static String display94(JSONObject r) {
        String state=r.optString("status"),text;
        if("HASSELBLAD_SHUTTER_RENDERED".equals(state))
            text="Last saved photo: Hasselblad · Curve "+r.optInt("film_curve_code")
                    +"\nAutomatic LUT "+r.optInt("automatic_lut_kelvin")+" K"
                    +"\nSharpening: "+(r.optBoolean("sharpening_applied")?"on":"off");
        else if("RAW_ONLY_SAVED".equals(state))text="Last capture: original RAW saved. No JPEG requested.";
        else text="Last Hasselblad capture "+("CANCELLED".equals(state)?"cancelled":"failed")+": "+r.optString("reason")
                    +"\n"+(r.optBoolean("jpeg_saved")?"JPEG saved.":"No JPEG saved.")
                    +(r.optBoolean("raw_saved")?" Original RAW saved.":"");
        return text+"\nBuild: "+r.optString("version_name");
    }
    public static String lastStatus94(Context context) {
        return context.getSharedPreferences("hasselblad-capture94",Context.MODE_PRIVATE)
                .getString("last_status","Take a new photo to see its Hasselblad capture result.");
    }
    private static void closeFrames94(ArrayList<ImageFrame> frames) {
        if(frames!=null)for(ImageFrame frame:frames)if(frame!=null)
            try{frame.close();}catch(Exception e){Log.e(TAG,"RAW cleanup failed",e);}
    }
    /** Terminal rejection: release the capture, report failure and never select another renderer. */
    public static void reject94(Context context,ArrayList<ImageFrame> frames,String reason,
            ProcessorBase.ProcessingCallback callback,ProcessingEventsListener events) {
        try {
            try {remember(context,report("SAVE_OR_RENDER_FAILED").put("reason",reason)
                    .put("failure_stage","eligibility").put("raw_saved",false).put("jpeg_saved",false),
                    null,HasselbladDiagnostics86.enabled(context));}
            catch(Exception e){Log.e(TAG,"Cannot record capture rejection",e);}
            event(()->callback.onFailed());event(()->events.onProcessingError("Hasselblad capture failed: "+reason));
        } finally {closeFrames94(frames);}
    }
    public static void clearDiagnostics86(Context context) {
        synchronized(REPORT_LOCK){remove(latest(context));}
    }
    public static String lastReport(Context context) throws IOException {
        if(!HasselbladDiagnostics86.enabled(context)) {
            clearDiagnostics86(context);return "Capture diagnostics are off. Photos are saved normally; no capture report or comparison is retained.";
        }
        synchronized(REPORT_LOCK){File f=new File(latest(context),"report.json");
            return f.isFile()?new String(Files.readAllBytes(f.toPath()),StandardCharsets.UTF_8):"Take a photo first. No capture report is available.";}
    }
    public static void export(Context context,OutputStream output) throws IOException {
        if(!HasselbladDiagnostics86.enabled(context))throw new IOException("Enable capture diagnostics and take a new photo before exporting.");
        synchronized(REPORT_LOCK) {
            File folder=latest(context);File[] files=folder.listFiles();
            if(files==null || !new File(folder,"report.json").isFile())throw new IOException("No capture report available");
            try(ZipOutputStream zip=new ZipOutputStream(output)) {
                for(File f:files){zip.putNextEntry(new ZipEntry(f.getName()));Files.copy(f.toPath(),zip);zip.closeEntry();}
            }
        }
    }
    private static void event(Runnable action){try{action.run();}catch(Exception e){Log.e(TAG,"Capture UI callback failed",e);}}
    /** Owns every outcome and always releases the supplied frames. No renderer substitution. */
    public static void handle(Context context,ArrayList<ImageFrame> frames,HasselbladCaptureEvidence evidence,
            int rotation,int saveMode,Path rawPath,Path imageBase,ParseExif.ExifData exif,
            ProcessorBase.ProcessingCallback callback,ProcessingEventsListener events) {
        boolean diagnostics=false;
        File directory=null;Bitmap[] bitmap={null};
        String stage="eligibility";
        boolean renderCompleted=false;
        boolean rawSaved=false,jpegSaved=false;long start=System.nanoTime();JSONObject receipt=null;
        event(()->callback.onStarted());event(()->events.onProcessingStarted("Hasselblad rendering"));
        try {
            cleanupOnce(context);diagnostics=HasselbladDiagnostics86.enabled(context);
            if(frames==null || frames.size()!=1 || frames.get(0)==null || evidence==null)
                throw new IOException("Single RAW and matched original still metadata required");
            if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
            diagnostics=evidence.diagnosticsEnabled86();
            final HasselbladSharpen91 sharpening=evidence.sharpeningSettings91();
            boolean rawOnly=ImageFormatConfig.isRawOnly(saveMode);
            if(ImageFormatConfig.usesHeic(saveMode))throw new IOException("Hasselblad outputs sRGB JPEG. Select JPEG, RAW + JPEG or RAW.");
            HasselbladProfile43 profile=null;
            if(!rawOnly) {
                profile=HasselbladLookStore84.read(context);
                if(!profile.hasAutomaticIlluminant || !profile.hasNativeFinishing)throw new IOException("Import the Stage56 automatic .hbc profile first");
            }
            receipt=report("PREPARING").put("save_mode",saveMode).put("metadata_source","original_matched_still_before_Photon_fix")
                    .put("capture_diagnostics",diagnostics).put("sharpening_requested",sharpening.enabled).put("sharpening_applied",false)
                    .put("sharpening_selection",new JSONObject().put("enabled",sharpening.enabled).put("amount",sharpening.amount).put("noise_limit",sharpening.noise).put("radius",1).put("dark_limit",10))
                    .put("dng_writer","existing_writer_original_metadata").put("raw_saved",false).put("jpeg_saved",false);
            if(profile!=null)receipt.put("film_curve_code",profile.film)
                    .put("profile_sha256",HasselbladLook84.sha256(profile.encoded()))
                    .put("film_curve_sha256",HasselbladLook84.curveHash(profile))
                    .put("profile_source","snapshot_of_imported_automatic_profile")
                    .put("native_finishing",profile.hasNativeFinishing);
            directory=new File(context.getCacheDir(),"hb82-shot-"+UUID.randomUUID());
            if(!directory.mkdir())throw new IOException("Cannot create capture staging folder");
            File dng=new File(directory,"source.dng"),jpeg=new File(directory,"automatic-colour.jpg");
            HasselbladSceneRenderer79.Result rendered=null;
            try(HasselbladDngBridge79 bridge=evidence.bridge79(frames.get(0),rotation)) {
                stage="dng_staging";long t=System.nanoTime();bridge.write(dng);
                receipt.put("dng_stage_milliseconds",(System.nanoTime()-t)/1e6).put("raw_width",bridge.width)
                        .put("raw_height",bridge.height).put("orientation",bridge.orientation);
                if(!rawOnly) {
                    int workers=Math.max(1,Math.min(4,Runtime.getRuntime().availableProcessors()));
                    stage="rendering";
                    rendered=HasselbladSceneRenderer79.render(dng,profile,workers,diagnostics,sharpening,new HasselbladSceneRenderer79.Sink() {
                        public void begin(int w,int h){bitmap[0]=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);}
                        public void band(int y,int rows,int w,int[] pixels){bitmap[0].setPixels(pixels,0,w,0,y,w,rows);}
                    });
                    stage="jpeg_encoding";t=System.nanoTime();
                    try(OutputStream out=new FileOutputStream(jpeg)) {
                        if(!bitmap[0].compress(Bitmap.CompressFormat.JPEG,95,out))throw new IOException("JPEG encoding failed");
                    }
                    exif.PHOTOGRAPHIC_SENSITIVITY=Integer.toString(bridge.iso);
                    exif.EXPOSURE_TIME=Double.toString(bridge.exposureNs/1e9);
                    if(bridge.aperture!=null)exif.F_NUMBER=bridge.aperture.toString();
                    if(bridge.focalLength!=null)exif.FOCAL_LENGTH=((int)(bridge.focalLength*100))+"/100";
                    exif.COMPRESSION="6"; // TIFF/EXIF code for JPEG; encoder quality is separately 95.
                    exif.COLOR_SPACE="1";exif.IMAGE_WIDTH=Integer.toString(rendered.width);exif.IMAGE_LENGTH=Integer.toString(rendered.height);
                    exif.IMAGE_DESCRIPTION="Hasselblad; curve "+profile.film+"; automatic LUT "+rendered.kelvin+" K; sharpening "+(rendered.sharpeningApplied?sharpening.description():"off")+"; sensor interior crop32; sRGB";
                    ExifInterface tags=ParseExif.setAllAttributes(jpeg,exif);
                    if(tags==null)throw new IOException("Cannot write JPEG metadata");
                    tags.setAttribute(ExifInterface.TAG_ORIENTATION,Integer.toString(bridge.orientation));
                    tags.setAttribute(ExifInterface.TAG_COLOR_SPACE,"1");tags.saveAttributes();renderCompleted=true;
                    bitmap[0].recycle();bitmap[0]=null;
                    receipt.put("jpeg_encode_milliseconds",(System.nanoTime()-t)/1e6);
                }
            }
            if(rendered!=null) {
                receipt.put("finishing_tables_cached",true).put("sharpening_applied",rendered.sharpeningApplied)
                        .put("sharpening_settings",rendered.sharpeningApplied?new JSONObject().put("amount",sharpening.amount).put("radius",1).put("noise_limit",sharpening.noise).put("dark_limit",10):JSONObject.NULL)
                        .put("colour_and_bitmap_includes_sharpening",rendered.sharpeningApplied)
                        .put("output_width",rendered.width).put("output_height",rendered.height)
                        .put("crop_left",32).put("crop_top",32).put("crop_right",rendered.rawWidth-32-rendered.width)
                        .put("crop_bottom",rendered.rawHeight-32-rendered.height).put("automatic_lut_kelvin",rendered.kelvin)
                        .put("prepared_reference_sites_checked",rendered.checkedSites).put("worker_limit",rendered.workers)
                        .put("preparation_milliseconds",rendered.preparationNs/1e6).put("preparation_reference_check_milliseconds",rendered.referenceNs/1e6)
                        .put("demosaic_milliseconds",rendered.demosaicNs/1e6).put("colour_and_bitmap_milliseconds",rendered.colourNs/1e6)
                        .put("raw_below_black",rendered.belowBlack).put("raw_at_white",rendered.atWhite)
                        .put("gain_clip_events",rendered.gainClips).put("gainmap_count",rendered.gainMaps)
                        .put("reconstruction_revision","phocus-chroma96")
                        .put("chroma_correction_neutral",new JSONArray().put(rendered.chromaNeutral[0]).put(rendered.chromaNeutral[1]).put(rendered.chromaNeutral[2]))
                        .put("source_rgb_restored_before_colour",true)
                        .put("jpeg_quality",95).put("photon_colour_applied",false).put("no_white_balance_before_demosaic",true);
                JSONArray samples=new JSONArray();int index=0;
                for(var s:rendered.samples) {
                    String prefix="sample"+(index++);
                    Files.write(new File(directory,prefix+".input.u16le").toPath(),HasselbladDevice75Buffers.encode(s.bayer));
                    Files.write(new File(directory,prefix+".rgb.u16le").toPath(),HasselbladDevice75Buffers.encode(s.rgb));
                    samples.put(new JSONObject().put("prefix",prefix).put("width",64).put("height",64).put("halo",32)
                            .put("input_stride",128).put("sensor_x",s.sensorX).put("sensor_y",s.sensorY).put("cfa","RGGB"));
                }
                receipt.put("samples",samples);
            }
            if(Thread.currentThread().isInterrupted())throw new IOException("Capture cancelled");
            // Publish each requested file once; any failure is terminal.
            if(ImageFormatConfig.savesRaw(saveMode)) {
                stage="saving_raw";long saveStart=System.nanoTime();
                HasselbladCaptureFiles80.Metrics saveMetrics=new HasselbladCaptureFiles80.Metrics();
                try{HasselbladCaptureFiles80.publish(context,dng.toPath(),rawPath,saveMetrics);rawSaved=true;}
                finally{receipt.put("raw_save_milliseconds",(System.nanoTime()-saveStart)/1e6)
                        .put("raw_save_operations",new JSONObject(saveMetrics.snapshot()));}
                event(()->events.notifyImageSavedStatus(true,rawPath));
                evidence.recordCapture79();evidence.finishRawSave(rawPath,true);
            } else HasselbladCaptureSaveStatus.skipped("Stage82 JPEG-only: private DNG removed after rendering.");
            if(!rawOnly) {
                Path jpg=Paths.get(imageBase.toAbsolutePath()+".jpg");
                stage="saving_jpeg";long saveStart=System.nanoTime();
                HasselbladCaptureFiles80.Metrics saveMetrics=new HasselbladCaptureFiles80.Metrics();
                try{HasselbladCaptureFiles80.publish(context,jpeg.toPath(),jpg,saveMetrics);jpegSaved=true;}
                finally{receipt.put("jpeg_save_milliseconds",(System.nanoTime()-saveStart)/1e6)
                        .put("jpeg_save_operations",new JSONObject(saveMetrics.snapshot()));}
                event(()->events.notifyImageSavedStatus(true,jpg));
            }
            receipt.put("status",rawOnly?"RAW_ONLY_SAVED":"HASSELBLAD_SHUTTER_RENDERED")
                    .put("render_completed",renderCompleted).put("storage_backend","primary_DCIM_granted_document_tree")
                    .put("capture_renderer_changed",!rawOnly).put("raw_saved",rawSaved).put("jpeg_saved",jpegSaved)
                    .put("total_milliseconds",(System.nanoTime()-start)/1e6);
            remember(context,receipt,directory,diagnostics);
            event(()->events.onProcessingFinished("Hasselblad capture saved"));event(callback::onFinished);
            return;
        } catch(Exception|LinkageError|OutOfMemoryError e) {
            boolean cancelled=Thread.currentThread().isInterrupted();
            String reason=e instanceof OutOfMemoryError?"Not enough memory":e.getMessage();
            if(reason==null)reason=e.getClass().getSimpleName();
            final String failureReason=reason;
            try {if(receipt==null)receipt=report("FAILED");receipt.put("status",cancelled?"CANCELLED":"SAVE_OR_RENDER_FAILED")
                    .put("reason",reason).put("failure_stage",stage).put("render_completed",renderCompleted)
                    .put("raw_saved",rawSaved).put("jpeg_saved",jpegSaved).put("total_milliseconds",(System.nanoTime()-start)/1e6);
                JSONArray cleanupErrors=new JSONArray();
                for(Throwable cleanup:e.getSuppressed())cleanupErrors.put(cleanup.toString());
                receipt.put("cleanup_errors",cleanupErrors);
                remember(context,receipt,renderCompleted?directory:null,diagnostics);}
            catch(Exception ignored) {Log.e(TAG,"Could not record capture failure",e);}
            event(callback::onFailed);event(()->events.onProcessingError("Hasselblad capture failed: "+failureReason));
        } finally {
            try {if(bitmap[0]!=null)bitmap[0].recycle();remove(directory);}
            finally {closeFrames94(frames);}
        }
    }
}
