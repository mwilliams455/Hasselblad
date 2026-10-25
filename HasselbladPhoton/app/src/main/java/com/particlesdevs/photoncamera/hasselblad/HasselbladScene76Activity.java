package com.particlesdevs.photoncamera.hasselblad;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.AtomicFile;
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
public final class HasselbladScene76Activity extends BaseActivity {
    private TextView status;
    private ImageView image;
    private MaterialButton open,next,saveJpeg,saveZip,copy,cancel;
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
    private final ActivityResultLauncher<String> jpegSaver=registerForActivityResult(
        new ActivityResultContracts.CreateDocument("image/jpeg"),uri->{if(uri!=null&&!busy)save(uri,"automatic-colour.jpg");});
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
        TextView title=new TextView(this);title.setText("Stage76 · full-scene colour");title.setTextSize(22);root.addView(title);
        status=new TextView(this);status.setText("Open a saved DNG with your imported automatic .hbc profile. " +
            "A 32-pixel sensor-edge crop retains real neighbours for every tile. A 4096 × 3072 DNG produces a 4032 × 3008 JPEG. " +
            "Rendering runs once; use the three previews to compare colour and LUTs.");root.addView(status);
        open=button(root,"Open saved DNG and render scene",()->picker.launch(new String[]{"*/*"}));
        cancel=new MaterialButton(this);cancel.setText("Cancel render");cancel.setOnClickListener(v->{if(worker!=null)worker.interrupt();status.setText("Cancelling…");});root.addView(cancel);
        next=button(root,"Next colour / LUT view",()->{mode=(mode+1)%3;show();});
        image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);root.addView(image,new LinearLayout.LayoutParams(-1,-2));
        saveJpeg=button(root,"Save full-resolution automatic-colour JPEG",()->jpegSaver.launch("Hasselblad_Stage76_Automatic_Colour.jpg"));
        TextView note=new TextView(this);note.setText("The private comparison ZIP includes the full-resolution JPEG, three scene previews, report and small Bayer/RGB16 samples. Camera photos still use Photon.");root.addView(note);
        saveZip=button(root,"Export private scene comparison ZIP",()->zipSaver.launch("Hasselblad_Stage76_Scene_Comparison.zip"));
        copy=button(root,"Copy scene report",()->{ClipboardManager c=getSystemService(ClipboardManager.class);if(c!=null)c.setPrimaryClip(ClipData.newPlainText("Stage76",report));});
        button(root,"Back",this::finish);setContentView(scroll);setBusy(false);
    }
    private void setBusy(boolean value) {busy=value;open.setEnabled(!value);next.setEnabled(!value&&previews!=null);
        saveJpeg.setEnabled(!value&&resultDirectory!=null);saveZip.setEnabled(!value&&resultDirectory!=null);copy.setEnabled(!value&&report!=null);cancel.setEnabled(value);}
    private static void remove(File f) {if(f==null)return;if(f.isDirectory()){File[] list=f.listFiles();if(list!=null)for(File x:list)remove(x);}f.delete();}
    private void clear() {image.setImageDrawable(null);if(shown!=null){shown.recycle();shown=null;}previews=null;report=null;summary=null;remove(resultDirectory);resultDirectory=null;}
    private static void interrupted()throws IOException {if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");}
    private void progress(String text) {runOnUiThread(()->{if(!destroyed)status.setText(text);});}
    private static byte[] digest(File file)throws Exception {MessageDigest md=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(file)){
        byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){interrupted();md.update(b,0,n);}}return md.digest();}
    private static void writeWords(File file,short[] data)throws IOException {try(OutputStream out=new FileOutputStream(file)){out.write(HasselbladDevice75Buffers.encode(data));}}
    private static void samplePreview(int[] source,int[] target,int w,int y,int rows,int step,int previewWidth) {
        for(int sy=0;sy<rows;sy++){int gy=y+sy;if(gy%step!=0)continue;for(int x=0;x<w;x+=step)target[(gy/step)*previewWidth+x/step]=source[sy*w+x];}
    }
    private static Bitmap rotated(int[] pixels,int w,int h,int orientation) {
        Bitmap base=Bitmap.createBitmap(pixels,w,h,Bitmap.Config.ARGB_8888);if(orientation==1)return base;
        Matrix m=new Matrix();m.postRotate(orientation==3?180:orientation==6?90:270);Bitmap result=Bitmap.createBitmap(base,0,0,w,h,m,false);if(result!=base)base.recycle();return result;
    }
    private void render(Uri uri) {
        clear();setBusy(true);progress("Loading profile and checking band assembly…");
        worker=new Thread(()->{File directory=null;Bitmap full=null;boolean delivered=false;try {
            long start=SystemClock.elapsedRealtime();HasselbladProfile43 profile;
            try(InputStream in=new AtomicFile(new File(getFilesDir(),"stage43-colour.hbc")).openRead()){profile=HasselbladProfile43.read(in);}
            if(!profile.hasAutomaticIlluminant||!profile.hasNativeFinishing)throw new IOException("Import your Stage56 automatic .hbc profile on Saved DNG colour first.");
            HasselbladFrame76.selfCheck();interrupted();
            directory=new File(getCacheDir(),"hb76-"+UUID.randomUUID());if(!directory.mkdir())throw new IOException("Cannot create render folder");
            File dng=new File(directory,"source.dng");progress("Copying the saved DNG…");
            try(InputStream in=getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(dng)) {
                if(in==null)throw new IOException("Cannot read DNG");byte[] b=new byte[65536];long count=0;int n;
                while((n=in.read(b))!=-1){interrupted();count+=n;if(count>HasselbladDngTileReader.MAX_FILE_BYTES)throw new IOException("DNG exceeds 256 MB");out.write(b,0,n);}
            }
            byte[] before=digest(dng);long copied=SystemClock.elapsedRealtime();progress("Preparing the full Bayer image…");
            var prepared=HasselbladDngTileReader.readPrepared76(dng);var m=prepared.metadata;
            int w=HasselbladFrame76.width(m.width),h=HasselbladFrame76.width(m.height),step=1;
            while((long)((w+step-1)/step)*((h+step-1)/step)>1048576)step++;
            int previewWidth=(w+step-1)/step,previewHeight=(h+step-1)/step;
            if(m.illuminant.error!=null)throw new IOException("Automatic LUT unavailable: "+m.illuminant.error);
            var selection=HasselbladIlluminant56.estimate(m.illuminant.colorMatrix1,m.illuminant.colorMatrix2,m.illuminant.light1,m.illuminant.light2,
                m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] params=profile.parameters(camera),grid=profile.gridAtTemperature(selection.lutKelvin),srgb=HasselbladRenderer42.xyzToSrgb();
            long preparedAt=SystemClock.elapsedRealtime();int[][] views=new int[3][previewWidth*previewHeight];
            full=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);
            long nativeNs=0,colourNs=0;JSONArray samples=new JSONArray();int tileCount=0;
            int[] sampleRows={0,((h/2)/64)*64,((h-64)/64)*64};Set<Integer> sampleBands=new HashSet<>();
            for(int y:sampleRows)if(y>=0&&y+64<=h)sampleBands.add(y);
            for(int y=0;y<h;y+=64) {
                interrupted();progress("Rendering scene · "+(100*y/h)+"%\n"+w+" × "+h+" · automatic LUT "+selection.lutKelvin+" K");
                long t0=SystemClock.elapsedRealtimeNanos();short[] rgb=HasselbladFrame76.band(prepared.bayer,m.width,m.height,y);
                nativeNs+=SystemClock.elapsedRealtimeNanos()-t0;int rows=Math.min(64,h-y);tileCount+=(w+63)/64;
                if(sampleBands.contains(y)) {
                    int x=Math.max(0,Math.min(w-64,((w/2)/64)*64-16))&~1;short[] input=new short[128*128],out=new short[64*64*3];
                    for(int yy=0;yy<128;yy++)System.arraycopy(prepared.bayer,(y+yy)*m.width+x,input,yy*128,128);
                    for(int yy=0;yy<64;yy++)System.arraycopy(rgb,(yy*w+x)*3,out,yy*64*3,64*3);
                    String prefix="sample"+samples.length();writeWords(new File(directory,prefix+".input.u16le"),input);writeWords(new File(directory,prefix+".rgb.u16le"),out);
                    samples.put(new JSONObject().put("prefix",prefix).put("width",64).put("height",64).put("input_stride",128)
                        .put("halo",32).put("cfa","RGGB").put("sensor_x",x+32).put("sensor_y",y+32).put("from_assembled_band",true));
                }
                t0=SystemClock.elapsedRealtimeNanos();int[] neutral=HasselbladProfile43.baseline(rgb,camera,srgb);
                samplePreview(neutral,views[0],w,y,rows,step,previewWidth);interrupted();
                short[] manual=profile.finishRgb16(HasselbladRenderer42.render(rgb,params,profile.grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
                samplePreview(HasselbladProfile43.srgb16ToArgb(manual),views[1],w,y,rows,step,previewWidth);interrupted();
                short[] automatic=profile.finishRgb16(HasselbladRenderer42.render(rgb,params,grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
                int[] pixels=HasselbladProfile43.srgb16ToArgb(automatic);samplePreview(pixels,views[2],w,y,rows,step,previewWidth);
                full.setPixels(pixels,0,w,0,y,w,rows);colourNs+=SystemClock.elapsedRealtimeNanos()-t0;
            }
            long renderedAt=SystemClock.elapsedRealtime();interrupted();progress("Saving the full-resolution colour render…");
            if(!MessageDigest.isEqual(before,digest(dng)))throw new IOException("Private DNG copy changed");
            File jpeg=new File(directory,"automatic-colour.jpg");try(OutputStream out=new FileOutputStream(jpeg)){
                if(!full.compress(Bitmap.CompressFormat.JPEG,95,out))throw new IOException("JPEG encoding failed");}
            full.recycle();full=null;ExifInterface exif=new ExifInterface(jpeg);
            exif.setAttribute(ExifInterface.TAG_ORIENTATION,Integer.toString(prepared.orientation));exif.setAttribute(ExifInterface.TAG_COLOR_SPACE,"1");exif.saveAttributes();
            String[] names={"neutral-preview.png","manual-lut-preview.png","automatic-lut-preview.png"};
            for(int i=0;i<3;i++){interrupted();Bitmap b=rotated(views[i],previewWidth,previewHeight,prepared.orientation);
                try(OutputStream out=new FileOutputStream(new File(directory,names[i]))){if(!b.compress(Bitmap.CompressFormat.PNG,100,out))throw new IOException("Preview encoding failed");}finally{b.recycle();}}
            long encodedAt=SystemClock.elapsedRealtime();
            JSONObject j=new JSONObject().put("schema","hasselblad-stage76-scene-v1").put("status","RENDERED_SENSOR_INTERIOR_COLOUR")
                .put("version_name",BuildConfig.VERSION_NAME).put("version_code",BuildConfig.VERSION_CODE).put("source_commit",BuildConfig.HB76_SOURCE)
                .put("raw_width",m.width).put("raw_height",m.height).put("output_width",w).put("output_height",h)
                .put("crop_left",32).put("crop_top",32).put("crop_right",m.width-32-w).put("crop_bottom",m.height-32-h)
                .put("border_policy","Crop 32 sites (33 on odd trailing dimensions); all halos use actual sensor samples; no synthesized borders")
                .put("orientation",prepared.orientation).put("preview_width",previewWidth).put("preview_height",previewHeight).put("preview_step",step)
                .put("tile_count",tileCount).put("native_tile_geometry","64x64 output with 32px real halo; unchanged Stage74 core")
                .put("band_selfcheck_exact",true).put("project_stage75_device_gate_previously_passed",true)
                .put("stage76_exported_samples_host_compared",false).put("samples",samples)
                .put("manual_lut_kelvin",profile.temperature).put("automatic_lut_kelvin",selection.lutKelvin).put("native_finishing",true)
                .put("full_resolution_jpeg_view","automatic LUT + native finishing + sRGB, JPEG quality 95")
                .put("preparation","Stage75 common-range float preparation; ordered GainMaps/clamps; quantize Bayer before demosaic")
                .put("gainmap_count",m.gainMapCount).put("raw_below_black",prepared.belowBlack).put("raw_at_white",prepared.atWhite).put("gain_clip_events",prepared.gainClips)
                .put("setup_and_copy_milliseconds",copied-start).put("preparation_and_calibration_milliseconds",preparedAt-copied)
                .put("demosaic_bands_milliseconds",nativeNs/1e6).put("colour_and_bitmap_milliseconds",colourNs/1e6)
                .put("render_wall_milliseconds",renderedAt-preparedAt).put("verification_and_encode_milliseconds",encodedAt-renderedAt)
                .put("total_before_zip_milliseconds",encodedAt-start).put("original_opened_read_only",true).put("private_copy_unchanged",true)
                .put("highlight_reconstruction",false).put("no_white_balance_before_demosaic",true).put("capture_renderer_changed",false)
                .put("private_profile_or_calibration_exported",false).put("physical_sensor_colour_match_proved",false).put("original_phocus_outer_border_parity",false);
            dng.delete();String receipt=j.toString(2);try(OutputStream out=new FileOutputStream(new File(directory,"report.json"))){out.write(receipt.getBytes(StandardCharsets.UTF_8));}
            try(ZipOutputStream z=new ZipOutputStream(new FileOutputStream(new File(directory,"comparison.zip")))) {
                File[] files=directory.listFiles();if(files==null)throw new IOException("Cannot list comparison output");Arrays.sort(files,Comparator.comparing(File::getName));
                byte[] block=new byte[65536];for(File f:files){if(f.getName().equals("comparison.zip")||f.getName().equals("source.dng"))continue;
                    interrupted();z.putNextEntry(new ZipEntry(f.getName()));try(InputStream in=new FileInputStream(f)){int n;while((n=in.read(block))!=-1){interrupted();z.write(block,0,n);}}z.closeEntry();}
            }
            final File results=directory;final int rot=prepared.orientation;
            final String description=w+" × "+h+" · "+((encodedAt-start)/1000.0)+" s\n32-pixel sensor-edge crop · manual LUT "+profile.temperature+" K · automatic LUT "+selection.lutKelvin+" K";
            runOnUiThread(()->{if(destroyed){remove(results);return;}resultDirectory=results;previews=views;pw=previewWidth;ph=previewHeight;orientation=rot;report=receipt;summary=description;mode=2;setBusy(false);show();});delivered=true;
        }catch(Exception|LinkageError|OutOfMemoryError e){runOnUiThread(()->{if(destroyed)return;setBusy(false);status.setText("Scene render stopped: "+(e instanceof OutOfMemoryError?"Not enough memory for this RAW size.":e.getMessage()));});}
        finally{if(full!=null)full.recycle();if(!delivered)remove(directory);}},"HB76-full-scene");worker.start();
    }
    private void show() {
        image.setImageDrawable(null);if(shown!=null)shown.recycle();shown=rotated(previews[mode],pw,ph,orientation);image.setImageBitmap(shown);
        String name=mode==0?"Neutral DNG colour":mode==1?"Manual profile LUT":"Automatic profile LUT";image.setContentDescription(name);
        status.setText(name+"\n"+summary+"\nScene preview; saved JPEG is the full-resolution automatic-colour view.");
    }
    private void save(Uri uri,String name) {
        File file=new File(resultDirectory,name);setBusy(true);worker=new Thread(()->{try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(uri,"w")){
            if(out==null)throw new IOException("Cannot save output");byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){interrupted();out.write(b,0,n);}
            runOnUiThread(()->{if(destroyed)return;setBusy(false);status.setText(name.endsWith(".zip")?"Scene comparison saved. Send the ZIP back for image and seam assessment.":"Full-resolution automatic-colour JPEG saved.");});
        }catch(Exception e){runOnUiThread(()->{if(destroyed)return;setBusy(false);status.setText("Save stopped: "+e.getMessage());});}},"HB76-export");worker.start();
    }
    @Override protected void onDestroy(){destroyed=true;if(worker!=null)worker.interrupt();clear();super.onDestroy();}
}
