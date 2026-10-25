package com.particlesdevs.photoncamera.hasselblad;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.exifinterface.media.ExifInterface;
import com.google.android.material.button.MaterialButton;
import com.particlesdevs.photoncamera.BuildConfig;
import com.particlesdevs.photoncamera.app.base.BaseActivity;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Full-scene, saved-DNG-only colour experiment. The unverified outer sensor border is cropped. */
public final class HasselbladTone83Activity extends BaseActivity {
    private TextView status;
    private ImageView image;
    private MaterialButton open,importPack,next,saveJpeg,saveZip,copy,cancel;
    private static final String[] NAMES={"current-profile","curve-0","curve-1","no-film-7"};
    private static final String[] LABELS={"Current profile curve","Recovered curve 0","Recovered curve 1","No-film control (7)"};
    private int savedMode;
    private boolean busy;
    private volatile boolean destroyed;
    private Thread worker;
    private int mode,pw,ph,orientation;
    private int[][] previews;
    private Bitmap shown;
    private File resultDirectory;
    private String report,summary;
    private final ActivityResultLauncher<String[]> picker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null&&!busy)render(uri);});
    private final ActivityResultLauncher<String[]> packPicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null&&!busy)importPack(uri);});
    private final ActivityResultLauncher<String> jpegSaver=registerForActivityResult(
        new ActivityResultContracts.CreateDocument("image/jpeg"),uri->{if(uri!=null&&!busy)save(uri,NAMES[savedMode]+".jpg");});
    private final ActivityResultLauncher<String> zipSaver=registerForActivityResult(
        new ActivityResultContracts.CreateDocument("application/zip"),uri->{if(uri!=null&&!busy)save(uri,"comparison.zip");});
    private MaterialButton button(LinearLayout root,String label,Runnable action) {
        MaterialButton b=new MaterialButton(this);b.setText(label);b.setOnClickListener(v->{if(!busy)action.run();});root.addView(b);return b;
    }
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);scroll.addView(root);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(scroll,(view,insets)->{Insets b=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(pad+b.left,pad+b.top,pad+b.right,pad+b.bottom);return WindowInsetsCompat.CONSUMED;});
        TextView title=new TextView(this);title.setText("Tone curve comparison");title.setTextSize(22);root.addView(title);
        status=new TextView(this);status.setText("Import the private .hbt tone pack, then open a saved DNG. Compare your current profile curve, recovered curves 0 and 1, and a no-film control. White balance, automatic LUT and exposure stay fixed.");root.addView(status);
        importPack=button(root,"Import tone comparison pack (.hbt)",()->packPicker.launch(new String[]{"*/*"}));
        open=button(root,"Open saved DNG and compare tones",()->picker.launch(new String[]{"*/*"}));
        cancel=new MaterialButton(this);cancel.setText("Cancel render");cancel.setOnClickListener(v->{if(worker!=null)worker.interrupt();status.setText("Cancelling…");});root.addView(cancel);
        next=button(root,"Next tone curve",()->{mode=(mode+1)%4;show();});
        image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);root.addView(image,new LinearLayout.LayoutParams(-1,-2));
        saveJpeg=button(root,"Save displayed curve as full-resolution JPEG",()->{savedMode=mode;jpegSaver.launch("Hasselblad_Stage83_"+NAMES[mode]+".jpg");});
        TextView note=new TextView(this);note.setText("The comparison ZIP contains four full-resolution JPEGs, four previews and a report. The no-film control retains the required encoding; it is not a linear display. Your camera's current rendering stays unchanged.");root.addView(note);
        saveZip=button(root,"Export private tone comparison ZIP",()->zipSaver.launch("Hasselblad_Stage83_Tone_Comparison.zip"));
        copy=button(root,"Copy scene report",()->{ClipboardManager c=getSystemService(ClipboardManager.class);if(c!=null)c.setPrimaryClip(ClipData.newPlainText("Stage83",report));});
        button(root,"Back",this::finish);setContentView(scroll);setBusy(false);
    }
    private void setBusy(boolean value) {busy=value;open.setEnabled(!value);importPack.setEnabled(!value);next.setEnabled(!value&&previews!=null);
        saveJpeg.setEnabled(!value&&resultDirectory!=null);saveZip.setEnabled(!value&&resultDirectory!=null);copy.setEnabled(!value&&report!=null);cancel.setEnabled(value);}
    private static void remove(File f) {if(f==null)return;if(f.isDirectory()){File[] list=f.listFiles();if(list!=null)for(File x:list)remove(x);}f.delete();}
    private void clear() {image.setImageDrawable(null);if(shown!=null){shown.recycle();shown=null;}previews=null;report=null;summary=null;remove(resultDirectory);resultDirectory=null;}
    private static void interrupted()throws IOException {if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");}
    private void progress(String text) {runOnUiThread(()->{if(!destroyed)status.setText(text);});}
    private static byte[] digest(File file)throws Exception {MessageDigest md=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){
        byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){interrupted();md.update(b,0,n);}}return md.digest();}
    private static void samplePreview(int[] source,int[] target,int w,int y,int rows,int step,int previewWidth) {
        for(int sy=0;sy<rows;sy++){int gy=y+sy;if(gy%step!=0)continue;for(int x=0;x<w;x+=step)target[(gy/step)*previewWidth+x/step]=source[sy*w+x];}
    }
    private static Bitmap rotated(int[] pixels,int w,int h,int orientation) {
        Bitmap base=Bitmap.createBitmap(pixels,w,h,Bitmap.Config.ARGB_8888);if(orientation==1)return base;
        Matrix m=new Matrix();m.postRotate(orientation==3?180:orientation==6?90:270);Bitmap result=Bitmap.createBitmap(base,0,0,w,h,m,false);if(result!=base)base.recycle();return result;
    }
    private HasselbladProfile43 profile()throws Exception {
        return HasselbladLookStore84.read(this);
    }
    private void importPack(Uri uri) {
        clear();setBusy(true);status.setText("Checking tone pack…");
        worker=new Thread(()->{try {
            HasselbladTone83 pack;
            try(InputStream in=getContentResolver().openInputStream(uri)){pack=HasselbladTone83.read(in);}
            pack.validateProfile(profile());interrupted();
            HasselbladLookStore84.importPack(this,pack);
            runOnUiThread(()->{if(!destroyed){setBusy(false);status.setText("Tone pack ready. Open a saved DNG to compare all four views.");}});
        }catch(Exception e){failed("Import stopped: "+e.getMessage());}},"HB83-import");worker.start();
    }
    private void failed(String message){runOnUiThread(()->{if(!destroyed){setBusy(false);status.setText(message);}});}
    private static String hex(byte[] data) {
        StringBuilder s=new StringBuilder();for(byte v:data)s.append(String.format(Locale.ROOT,"%02x",v&255));return s.toString();
    }
    private static void deleteRequired(File file)throws IOException {
        if(!file.delete())throw new IOException("Cannot clear private intermediate");
    }
    private static byte[] pixelBytes(int[] pixels) {
        java.nio.ByteBuffer b=java.nio.ByteBuffer.allocate(pixels.length*4).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        b.asIntBuffer().put(pixels);return b.array();
    }
    private void render(Uri uri) {
        clear();setBusy(true);progress("Loading colour profile and tone pack…");
        worker=new Thread(()->{File directory=null;Bitmap full=null;boolean delivered=false;try {
            long start=SystemClock.elapsedRealtime();HasselbladProfile43 profile=profile();HasselbladTone83 pack;
            pack=HasselbladLookStore84.readPack(this);
            pack.validateProfile(profile());int[] films={profile.film,0,1,7};
            float[][] curves={profile.curve,pack.curve(0),pack.curve(1),pack.curve(7)};
            int workers=Math.max(1,Math.min(4,Runtime.getRuntime().availableProcessors()));
            directory=new File(getCacheDir(),"hb83-"+UUID.randomUUID());if(!directory.mkdir())throw new IOException("Cannot create render folder");
            File dng=new File(directory,"source.dng"),linear=new File(directory,"linear.u16le"),baseline=new File(directory,"baseline.argb");
            progress("Copying saved DNG…");
            try(InputStream in=getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(dng)) {
                if(in==null)throw new IOException("Cannot read DNG");byte[] b=new byte[65536];long count=0;int n;
                while((n=in.read(b))!=-1){interrupted();count+=n;if(count>HasselbladDngTileReader.MAX_FILE_BYTES)throw new IOException("DNG exceeds 256 MB");out.write(b,0,n);}
            }
            byte[] sourceHash=digest(dng);long copied=SystemClock.elapsedRealtime();progress("Preparing RAW…");
            var rawPreparation=HasselbladDngTileReader.readPrepared78(dng);var prepared=rawPreparation.frame;var m=prepared.metadata;
            int w=HasselbladFrame77.width(m.width),h=HasselbladFrame77.width(m.height),step=1;
            while((long)((w+step-1)/step)*((h+step-1)/step)>1048576)step++;
            int previewWidth=(w+step-1)/step,previewHeight=(h+step-1)/step;
            if(m.illuminant.error!=null)throw new IOException("Automatic LUT unavailable: "+m.illuminant.error);
            var selection=HasselbladIlluminant56.estimate(m.illuminant.colorMatrix1,m.illuminant.colorMatrix2,m.illuminant.light1,m.illuminant.light2,
                m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] params=profile.parameters(camera),grid=profile.gridAtTemperature(selection.lutKelvin);
            long preparedAt=SystemClock.elapsedRealtime();MessageDigest rgbHash=MessageDigest.getInstance("SHA-256");
            try(OutputStream out=new BufferedOutputStream(new FileOutputStream(linear))) {
                for(int y=0;y<h;y+=64) {
                    interrupted();progress("Demosaicing once · "+(100*y/h)+"%");
                    short[] rgb=HasselbladFrame77.band(prepared.bayer,m.width,m.height,y,workers);
                    byte[] bytes=HasselbladDevice75Buffers.encode(rgb);out.write(bytes);rgbHash.update(bytes);
                }
            }
            if(linear.length()!=(long)w*h*6)throw new IOException("RGB intermediate length mismatch");
            if(!MessageDigest.isEqual(sourceHash,digest(dng)))throw new IOException("Private DNG copy changed");
            deleteRequired(dng);long demosaicedAt=SystemClock.elapsedRealtime();
            int[][] views=new int[4][previewWidth*previewHeight];JSONArray variants=new JSONArray();
            full=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);
            for(int view=0;view<4;view++) {
                long began=SystemClock.elapsedRealtime();HasselbladTone83.Stats stats=new HasselbladTone83.Stats();
                MessageDigest outputHash=MessageDigest.getInstance("SHA-256");
                try(DataInputStream in=new DataInputStream(new BufferedInputStream(new FileInputStream(linear)));
                    DataInputStream reference=view==0?null:new DataInputStream(new BufferedInputStream(new FileInputStream(baseline)));
                    OutputStream saved=view==0?new BufferedOutputStream(new FileOutputStream(baseline)):null) {
                    for(int y=0;y<h;y+=64) {
                        interrupted();progress(LABELS[view]+" · "+(100*y/h)+"%\nAutomatic LUT "+selection.lutKelvin+" K · fixed WB and exposure");
                        int rows=Math.min(64,h-y);short[] rgb=HasselbladTone83.readBand(in,w*rows*3);
                        short[] srgb=profile.finishRgb16(HasselbladRenderer42.render(rgb,params,grid,curves[view],profile.gridWidth,profile.gridHeight,1));
                        int[] pixels=HasselbladProfile43.srgb16ToArgb(srgb);byte[] bytes=pixelBytes(pixels);outputHash.update(bytes);
                        int[] prior=pixels;
                        if(view==0)saved.write(bytes);
                        else {
                            byte[] priorBytes=new byte[bytes.length];reference.readFully(priorBytes);prior=new int[pixels.length];
                            java.nio.ByteBuffer.wrap(priorBytes).order(java.nio.ByteOrder.LITTLE_ENDIAN).asIntBuffer().get(prior);
                        }
                        stats.add(pixels,prior);samplePreview(pixels,views[view],w,y,rows,step,previewWidth);
                        full.setPixels(pixels,0,w,0,y,w,rows);
                    }
                    if(in.read()!=-1||(reference!=null&&reference.read()!=-1))throw new IOException("Unexpected intermediate trailing data");
                }
                if(films[view]==profile.film&&stats.changedPixels!=0)throw new IOException("Current curve equivalence check failed");
                File jpeg=new File(directory,NAMES[view]+".jpg");
                try(OutputStream out=new FileOutputStream(jpeg)){if(!full.compress(Bitmap.CompressFormat.JPEG,95,out))throw new IOException("JPEG encoding failed");}
                ExifInterface exif=new ExifInterface(jpeg);exif.setAttribute(ExifInterface.TAG_ORIENTATION,Integer.toString(prepared.orientation));
                exif.setAttribute(ExifInterface.TAG_COLOR_SPACE,"1");exif.saveAttributes();
                Bitmap preview=rotated(views[view],previewWidth,previewHeight,prepared.orientation);
                try(OutputStream out=new FileOutputStream(new File(directory,NAMES[view]+"-preview.png"))) {
                    if(!preview.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("Preview encoding failed");
                }finally{preview.recycle();}
                variants.put(new JSONObject().put("name",NAMES[view]).put("film_code",films[view]).put("pixels",stats.pixels)
                    .put("changed_pixels_vs_current",stats.changedPixels).put("mean_abs_rgb8_difference_vs_current",stats.meanAbsoluteDifference())
                    .put("max_rgb8_difference_vs_current",stats.maxDifference).put("pixels_with_a_white_channel",stats.whiteChannelPixels)
                    .put("all_white_pixels",stats.allWhitePixels).put("all_black_pixels",stats.allBlackPixels)
                    .put("argb32le_sha256_before_jpeg",hex(outputHash.digest())).put("jpeg_sha256",hex(digest(jpeg)))
                    .put("render_and_encode_milliseconds",SystemClock.elapsedRealtime()-began));
            }
            full.recycle();full=null;deleteRequired(linear);deleteRequired(baseline);interrupted();
            JSONObject j=new JSONObject().put("schema","hasselblad-stage83-tones-v1").put("status","RENDERED_FIXED_INPUT_TONE_COMPARISON")
                .put("version_name",BuildConfig.VERSION_NAME).put("version_code",BuildConfig.VERSION_CODE).put("source_commit",BuildConfig.HB83_SOURCE)
                .put("profile_sha256",hex(MessageDigest.getInstance("SHA-256").digest(profile.encoded())))
                .put("tone_pack_sha256",hex(MessageDigest.getInstance("SHA-256").digest(pack.encoded())))
                .put("source_dng_sha256",hex(sourceHash)).put("shared_linear_rgb16_sha256",hex(rgbHash.digest()))
                .put("raw_width",m.width).put("raw_height",m.height).put("output_width",w).put("output_height",h)
                .put("crop_left",32).put("crop_top",32).put("crop_right",m.width-32-w).put("crop_bottom",m.height-32-h)
                .put("orientation",prepared.orientation).put("preview_width",previewWidth).put("preview_height",previewHeight).put("preview_step",step)
                .put("current_profile_film",profile.film).put("automatic_lut_kelvin",selection.lutKelvin).put("manual_lut_kelvin",profile.temperature)
                .put("profile_curve_matches_pack",true).put("same_curve_pixels_exact",true).put("variants",variants)
                .put("native_finishing",true).put("exposure_scale",1).put("white_balance_source","DNG as-shot, identical for every view")
                .put("tone_stage","Recovered film table inside colour render, before default gradation and sRGB output")
                .put("endpoint_metrics","sRGB 8-bit before JPEG; white-channel and black-pixel counts are display endpoints, not RAW clipping")
                .put("demosaic_passes",1).put("worker_limit",workers).put("jpeg_quality",95)
                .put("gainmap_count",m.gainMapCount).put("raw_below_black",prepared.belowBlack).put("raw_at_white",prepared.atWhite).put("gain_clip_events",prepared.gainClips)
                .put("copy_milliseconds",copied-start).put("preparation_milliseconds",preparedAt-copied)
                .put("demosaic_and_spool_milliseconds",demosaicedAt-preparedAt).put("total_before_zip_milliseconds",SystemClock.elapsedRealtime()-start)
                .put("original_opened_read_only",true).put("private_copy_unchanged",true).put("private_intermediates_removed",true)
                .put("capture_renderer_changed",false).put("active_colour_profile_changed",false).put("highlight_reconstruction",false)
                .put("private_profile_or_calibration_exported",false).put("physical_sensor_colour_match_proved",false).put("original_phocus_outer_border_parity",false);
            String receipt=j.toString(2);try(OutputStream out=new FileOutputStream(new File(directory,"report.json"))){out.write(receipt.getBytes(StandardCharsets.UTF_8));}
            // Explicit export allowlist: source DNG, linear RGB and profile/pack never enter ZIP.
            List<String> outputs=new ArrayList<>();outputs.add("report.json");for(String name:NAMES){outputs.add(name+".jpg");outputs.add(name+"-preview.png");}
            try(ZipOutputStream z=new ZipOutputStream(new FileOutputStream(new File(directory,"comparison.zip")))) {
                byte[] block=new byte[65536];for(String name:outputs) {
                    interrupted();z.putNextEntry(new ZipEntry(name));try(InputStream in=new FileInputStream(new File(directory,name))) {
                        int n;while((n=in.read(block))!=-1){interrupted();z.write(block,0,n);}
                    }z.closeEntry();
                }
            }
            final File results=directory;final int rot=prepared.orientation;
            final String description=w+" × "+h+" · automatic LUT "+selection.lutKelvin+" K\nCurrent profile: curve "+profile.film+" · WB and exposure fixed";
            runOnUiThread(()->{if(destroyed){remove(results);return;}resultDirectory=results;previews=views;pw=previewWidth;ph=previewHeight;orientation=rot;
                report=receipt;summary=description;mode=0;setBusy(false);show();});delivered=true;
        }catch(Exception|LinkageError|OutOfMemoryError e){failed("Tone comparison stopped: "+(e instanceof OutOfMemoryError?"Not enough memory for this RAW size.":e.getMessage()));}
        finally{if(full!=null)full.recycle();if(!delivered)remove(directory);}},"HB83-tone-comparison");worker.start();
    }
    private void show() {
        image.setImageDrawable(null);if(shown!=null)shown.recycle();shown=rotated(previews[mode],pw,ph,orientation);image.setImageBitmap(shown);
        image.setContentDescription(LABELS[mode]);status.setText(LABELS[mode]+"\n"+summary+"\nPreview shown; save exports this curve at full resolution.");
    }
    private void save(Uri uri,String name) {
        if(resultDirectory==null){status.setText("Open a DNG and compare again before saving.");return;}
        File file=new File(resultDirectory,name);setBusy(true);worker=new Thread(()->{try{try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(uri,"w")) {
            if(out==null)throw new IOException("Cannot save output");byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){interrupted();out.write(b,0,n);}
            out.flush();}runOnUiThread(()->{if(!destroyed){setBusy(false);status.setText(name.endsWith(".zip")?"Tone comparison saved. Send the ZIP back for comparison.":"Full-resolution curve JPEG saved.");}});
        }catch(Exception e){failed("Save stopped: "+e.getMessage());}},"HB83-export");worker.start();
    }
    @Override protected void onDestroy(){destroyed=true;if(worker!=null)worker.interrupt();clear();super.onDestroy();}
}
