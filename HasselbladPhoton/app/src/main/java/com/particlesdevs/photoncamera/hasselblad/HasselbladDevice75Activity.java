package com.particlesdevs.photoncamera.hasselblad;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
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

/** User-invoked saved-DNG experiments only. Never called by the camera shutter. */
public final class HasselbladDevice75Activity extends BaseActivity {
    private static final String[] REGIONS={"Centre","Upper left","Upper right","Lower left","Lower right"};
    private TextView status;
    private ImageView image;
    private MaterialButton check,open,look,crop,export,copy;
    private volatile boolean destroyed;
    private boolean busy,passed;
    private Thread worker;
    private String report;
    private byte[] archive;
    private Bitmap bitmap;
    private final List<int[][]> views=new ArrayList<>();
    private int region,mode,orientation;
    private String colourSummary="";
    private final ActivityResultLauncher<String[]> picker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null&&!busy)runDng(uri);});
    private final ActivityResultLauncher<String> saver=registerForActivityResult(
        new ActivityResultContracts.CreateDocument("application/zip"),uri->{if(uri!=null&&!busy)save(uri);});
    private MaterialButton button(LinearLayout root,String text,Runnable action) {
        MaterialButton b=new MaterialButton(this);b.setText(text);b.setOnClickListener(v->{if(!busy)action.run();});root.addView(b);return b;
    }
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);scroll.addView(root);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(scroll,(view,insets)->{Insets b=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(pad+b.left,pad+b.top,pad+b.right,pad+b.bottom);return WindowInsetsCompat.CONSUMED;});
        TextView title=new TextView(this);title.setText("Stage75 · demosaic and colour tiles");title.setTextSize(22);root.addView(title);
        status=new TextView(this);status.setText("Run the device check, then select a saved DNG. This shows five enlarged 64 × 64 crops. " +
            "Colour and LUT views are experimental; complete-photo rendering is not enabled.");root.addView(status);
        check=button(root,"1 · Run device check",this::runChecks);
        open=button(root,"2 · Open saved DNG",()->picker.launch(new String[]{"*/*"}));
        crop=button(root,"Next crop",()->{region=(region+1)%views.size();show();});
        look=button(root,"Next colour / LUT view",()->{mode=(mode+1)%3;show();});
        image=new ImageView(this);image.setAdjustViewBounds(true);image.setMinimumHeight((int)(220*getResources().getDisplayMetrics().density));
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);root.addView(image,new LinearLayout.LayoutParams(-1,-2));
        copy=button(root,"Copy test report",()->{ClipboardManager c=getSystemService(ClipboardManager.class);
            if(c!=null&&report!=null)c.setPrimaryClip(ClipData.newPlainText("Stage75",report));});
        TextView privacy=new TextView(this);privacy.setText("Export contains the actual prepared photo crops and RGB16 output for private host comparison. " +
            "It does not include your profile, calibration matrices or full DNG.");root.addView(privacy);
        export=button(root,"3 · Export private comparison ZIP",()->saver.launch("Hasselblad_Stage75_Device_Comparison.zip"));
        button(root,"Back",this::finish);setContentView(scroll);busy(false);
    }
    private void busy(boolean b) {busy=b;check.setEnabled(!b);open.setEnabled(!b&&passed);
        crop.setEnabled(!b&&!views.isEmpty());look.setEnabled(!b&&!views.isEmpty());
        export.setEnabled(!b&&archive!=null);copy.setEnabled(!b&&report!=null);}
    private void clear() {archive=null;report=null;views.clear();region=mode=0;image.setImageDrawable(null);
        if(bitmap!=null){bitmap.recycle();bitmap=null;}}
    private JSONObject base()throws Exception {
        return new JSONObject().put("schema","hasselblad-stage75-device-v1")
            .put("version_name",BuildConfig.VERSION_NAME).put("version_code",BuildConfig.VERSION_CODE)
            .put("source_commit",BuildConfig.HB75_SOURCE).put("supported_abis",new JSONArray(Arrays.asList(Build.SUPPORTED_ABIS)))
            .put("process_is_64_bit",android.os.Process.is64Bit()).put("native_library","hbfinal74")
            .put("capture_renderer_changed",false).put("full_phocus_colour_equivalence",false)
            .put("saved_dng_host_parity",false).put("synthetic_device_parity",passed);
    }
    private static void entry(ZipOutputStream z,String name,byte[] data)throws IOException {
        z.putNextEntry(new ZipEntry(name));z.write(data);z.closeEntry();
    }
    private static void words(ZipOutputStream z,String name,short[] data)throws IOException {entry(z,name,HasselbladDevice75Buffers.encode(data));}
    private void failure(Throwable error) {runOnUiThread(()->{if(destroyed)return;busy(false);status.setText("Test stopped: "+error.getMessage());});}
    private void runChecks() {
        clear();passed=false;busy(true);status.setText("Comparing actual Android RGB16 against host fixtures…");
        worker=new Thread(()->{try {
            JSONObject j=base();JSONArray results=new JSONArray();boolean exact=true;int values=0;
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(ZipOutputStream z=new ZipOutputStream(bytes)) {
                String[] names={"neutral64","colour64","random23"};int[] widths={64,64,23},heights={64,64,31};
                for(int k=0;k<names.length;k++) {
                    String name=names[k];int w=widths[k],h=heights[k];short[] in,expected;
                    try(InputStream a=getAssets().open("stage75/"+name+".input.u16le");InputStream b=getAssets().open("stage75/"+name+".rgb.u16le")) {
                        in=HasselbladDevice75Buffers.decode(a,(w+64)*(h+64));expected=HasselbladDevice75Buffers.decode(b,w*h*3);
                    }
                    long start=SystemClock.elapsedRealtimeNanos();short[] actual=HasselbladDevice75Buffers.render(in,w,h);
                    long elapsed=SystemClock.elapsedRealtimeNanos()-start;
                    int first=HasselbladDevice75Buffers.firstMismatch(expected,actual);
                    short[] repeat=HasselbladDevice75Buffers.render(in,w,h);
                    boolean stable=Arrays.equals(actual,repeat);exact&=first==-1&&stable;values+=actual.length;
                    results.put(new JSONObject().put("name",name).put("width",w).put("height",h).put("first_mismatch",first)
                        .put("repeat_exact",stable).put("milliseconds",elapsed/1e6));
                    words(z,name+".input.u16le",in);words(z,name+".rgb.u16le",actual);
                    if(!exact)break;
                }
                HasselbladDevice75Buffers.rejectionChecks();
                j.put("synthetic_device_parity",exact).put("fixtures",results).put("compared_channels",values)
                    .put("rejected_input_checks",true).put("status",exact?"PASS_SYNTHETIC_DEVICE_RGB16":"FAIL_SYNTHETIC_DEVICE_RGB16");
                entry(z,"report.json",j.toString(2).getBytes(StandardCharsets.UTF_8));
            }
            final boolean success=exact;final String receipt=j.toString(2);final byte[] zip=bytes.toByteArray();
            runOnUiThread(()->{if(destroyed)return;passed=success;report=receipt;archive=zip;busy(false);
                status.setText(success?"Synthetic device check passed exactly. Select a saved DNG to test its crops, colours and LUTs.":
                    "Device output mismatch. Export this ZIP; saved-DNG rendering is disabled.");});
        }catch(Exception|LinkageError e){failure(e);}},"HB75-device-check");worker.start();
    }
    private static byte[] digest(File f)throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(f)){
            byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1){if(Thread.currentThread().isInterrupted())throw new IOException("Cancelled");md.update(b,0,n);}}
        return md.digest();
    }
    private void runDng(Uri uri) {
        if(!passed)return;clear();busy(true);status.setText("Reading five real Bayer tiles and applying the saved colour profile…");
        worker=new Thread(()->{File temp=null;try {
            temp=File.createTempFile("hb75-",".dng",getCacheDir());long totalStart=SystemClock.elapsedRealtime();
            try(InputStream in=getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(temp)) {
                if(in==null)throw new IOException("Cannot open DNG");byte[] b=new byte[65536];long count=0;int n;
                while((n=in.read(b))!=-1){if(Thread.currentThread().isInterrupted())throw new IOException("Cancelled");
                    count+=n;if(count>HasselbladDngTileReader.MAX_FILE_BYTES)throw new IOException("DNG exceeds 256 MB");out.write(b,0,n);}
            }
            byte[] before=digest(temp);long copied=SystemClock.elapsedRealtime();
            HasselbladProfile43 profile=null;String profileError="Import an .hbc profile on the Saved DNG colour screen.";
            try(InputStream in=new AtomicFile(new File(getFilesDir(),"stage43-colour.hbc")).openRead()){profile=HasselbladProfile43.read(in);}
            catch(Exception e){profileError="Colour profile unavailable: "+e.getMessage();}
            List<int[][]> images=new ArrayList<>();JSONObject j=base();JSONArray tiles=new JSONArray();int rotate=1;
            String summary=profile==null?profileError:"Manual LUT "+profile.temperature+" K.";
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(ZipOutputStream z=new ZipOutputStream(bytes)) {
                for(int r=0;r<5;r++) {
                    long t0=SystemClock.elapsedRealtimeNanos();var tile=HasselbladDngTileReader.readBounded75(temp,r);var m=tile.metadata;
                    long t1=SystemClock.elapsedRealtimeNanos();short[] rgb=HasselbladDevice75Buffers.render(tile.bayer,64,64);
                    long t2=SystemClock.elapsedRealtimeNanos();short[] repeat=HasselbladDevice75Buffers.render(tile.bayer,64,64);
                    if(!Arrays.equals(rgb,repeat))throw new IOException("Saved-DNG repeat mismatch");
                    double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
                    int[][] display=new int[3][];display[0]=HasselbladProfile43.baseline(rgb,camera,HasselbladRenderer42.xyzToSrgb());
                    JSONObject item=new JSONObject().put("region",REGIONS[r]).put("prefix","tile"+r).put("width",64).put("height",64)
                        .put("input_stride",128).put("source_width",128).put("source_height",128).put("halo",32).put("cfa","RGGB")
                        .put("sensor_x",tile.x).put("sensor_y",tile.y).put("raw_width",m.width).put("raw_height",m.height)
                        .put("orientation",tile.orientation).put("repeat_exact",true).put("input_unchanged",true)
                        .put("prepare_milliseconds",(t1-t0)/1e6).put("native_milliseconds",(t2-t1)/1e6)
                        .put("gainmap_count",m.gainMapCount).put("raw_below_black",tile.belowBlack)
                        .put("raw_at_white",tile.atWhite).put("gain_clip_events",tile.gainClips);
                    long colourStart=SystemClock.elapsedRealtimeNanos();
                    if(profile!=null) {
                        short[] colour=HasselbladRenderer42.render(rgb,profile.parameters(camera),profile.grid,profile.curve,profile.gridWidth,profile.gridHeight,1);
                        if(profile.hasNativeFinishing){colour=profile.finishRgb16(colour);display[1]=HasselbladProfile43.srgb16ToArgb(colour);}
                        else display[1]=profile.display(colour);
                        item.put("manual_lut_kelvin",profile.temperature).put("native_finishing",profile.hasNativeFinishing);
                        words(z,"tile"+r+".manual-colour.u16le",colour);
                        if(profile.hasAutomaticIlluminant)try {
                            if(m.illuminant.error!=null)throw new IllegalArgumentException(m.illuminant.error);
                            var sel=HasselbladIlluminant56.estimate(m.illuminant.colorMatrix1,m.illuminant.colorMatrix2,m.illuminant.light1,m.illuminant.light2,
                                m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
                            short[] auto=HasselbladRenderer42.render(rgb,profile.parameters(camera),profile.gridAtTemperature(sel.lutKelvin),profile.curve,profile.gridWidth,profile.gridHeight,1);
                            auto=profile.finishRgb16(auto);display[2]=HasselbladProfile43.srgb16ToArgb(auto);
                            item.put("automatic_lut_kelvin",sel.lutKelvin);words(z,"tile"+r+".automatic-srgb.u16le",auto);
                            summary="Manual LUT "+profile.temperature+" K · automatic LUT "+sel.lutKelvin+" K.";
                        }catch(IllegalArgumentException e){item.put("automatic_unavailable",e.getMessage());if(r==0)summary+=" Automatic LUT unavailable: "+e.getMessage();}
                    }
                    item.put("colour_milliseconds",(SystemClock.elapsedRealtimeNanos()-colourStart)/1e6);
                    words(z,"tile"+r+".input.u16le",tile.bayer);words(z,"tile"+r+".rgb.u16le",rgb);
                    images.add(display);tiles.put(item);rotate=tile.orientation;
                }
                if(!MessageDigest.isEqual(before,digest(temp)))throw new IOException("Private DNG copy changed");
                j.put("status","SAVED_DNG_RENDERED_HOST_COMPARISON_PENDING").put("tiles",tiles)
                    .put("copy_milliseconds",copied-totalStart).put("total_milliseconds",SystemClock.elapsedRealtime()-totalStart)
                    .put("preparation","Stage58 common-range float normalization; clamp; ordered GainMaps; truncate to uint16 BEFORE demosaic")
                    .put("no_white_balance_before_demosaic",true).put("highlight_reconstruction",false)
                    .put("private_copy_unchanged",true).put("original_opened_read_only",true)
                    .put("physical_camera_id","not independently established from DNG; no Camera2 guess")
                    .put("sensor_adaptation_experimental",true).put("private_profile_included",false)
                    .put("rgb_layout","little-endian unsigned uint16, tightly packed RGB; sensor orientation")
                    .put("colour_summary",summary);
                entry(z,"report.json",j.toString(2).getBytes(StandardCharsets.UTF_8));
            }
            final String receipt=j.toString(2),label=summary;final byte[] zip=bytes.toByteArray();final int rot=rotate;
            runOnUiThread(()->{if(destroyed)return;views.addAll(images);orientation=rot;colourSummary=label;report=receipt;archive=zip;busy(false);show();});
        }catch(Exception|LinkageError e){failure(e);}finally{if(temp!=null)temp.delete();}},"HB75-saved-DNG");worker.start();
    }
    private void show() {
        int[] pixels=views.get(region)[mode];image.setImageDrawable(null);if(bitmap!=null){bitmap.recycle();bitmap=null;}
        String name=mode==0?"Neutral DNG colour":mode==1?"Manual profile LUT":"Automatic profile LUT";
        if(pixels!=null){Bitmap base=Bitmap.createBitmap(pixels,64,64,Bitmap.Config.ARGB_8888);Matrix m=new Matrix();
            m.postRotate(orientation==3?180:orientation==6?90:orientation==8?270:0);
            bitmap=Bitmap.createBitmap(base,0,0,64,64,m,false);if(bitmap!=base)base.recycle();image.setImageBitmap(bitmap);}
        image.setContentDescription(REGIONS[region]+" · "+name);
        status.setText(REGIONS[region]+" · "+name+" · enlarged 64 × 64 crop\n"+(pixels==null?"This LUT view is unavailable. ":"")+
            colourSummary+"\nSaved-DNG host parity pending. Experimental sensor colour adaptation.");
    }
    private void save(Uri uri) {
        final byte[] data=archive;if(data==null)return;busy(true);
        worker=new Thread(()->{try(OutputStream out=getContentResolver().openOutputStream(uri,"w")) {
            if(out==null)throw new IOException("Cannot save ZIP");out.write(data);
            runOnUiThread(()->{if(destroyed)return;busy(false);status.setText("Comparison ZIP saved. Send it back for exact host comparison.");});
        }catch(Exception e){failure(e);}},"HB75-export");worker.start();
    }
    @Override protected void onDestroy(){destroyed=true;if(worker!=null)worker.interrupt();clear();super.onDestroy();}
}
