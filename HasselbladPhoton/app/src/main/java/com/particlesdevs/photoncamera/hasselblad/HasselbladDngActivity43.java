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
import android.widget.TextView;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import com.google.android.material.button.MaterialButton;
import com.particlesdevs.photoncamera.app.base.BaseActivity;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;

/** Opt-in, read-only saved-DNG preview. No capture renderer hooks. */
public final class HasselbladDngActivity43 extends BaseActivity {
    private TextView status;
    private ImageView image;
    private MaterialButton importProfile,open,toggle,copy;
    private HasselbladProfile43 profile;
    private Bitmap experiment,baseline;
    private boolean busy,showBaseline;
    private String report;
    private Thread worker;
    private final ActivityResultLauncher<String[]> profilePicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null)loadProfile(uri);});
    private final ActivityResultLauncher<String[]> dngPicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null)loadDng(uri);});
    private AtomicFile profileFile(){return new AtomicFile(new File(getFilesDir(),"stage43-colour.hbc"));}
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(root,(view,insets)->{
            Insets bars=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(pad+bars.left,pad+bars.top,pad+bars.right,pad+bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        TextView title=new TextView(this);title.setText("Saved DNG colour · Stage43");title.setTextSize(22);root.addView(title);
        status=new TextView(this);status.setText("Import your .hbc colour profile, then open a saved DNG. " +
            "The preview uses that DNG’s calibration and white balance. Camera photos still use Photon.");root.addView(status);
        importProfile=new MaterialButton(this);importProfile.setText("Import colour profile");
        importProfile.setOnClickListener(v->{if(!busy)profilePicker.launch(new String[]{"*/*"});});root.addView(importProfile);
        open=new MaterialButton(this);open.setText("Open saved DNG");
        open.setOnClickListener(v->{if(!busy)dngPicker.launch(new String[]{"*/*"});});root.addView(open);
        toggle=new MaterialButton(this);toggle.setText("Show same-RAW baseline");
        toggle.setOnClickListener(v->{showBaseline=!showBaseline;show();});root.addView(toggle);
        copy=new MaterialButton(this);copy.setText("Copy render report");
        copy.setOnClickListener(v->{
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            if(clipboard!=null&&report!=null)clipboard.setPrimaryClip(ClipData.newPlainText("Stage43",report));
        });root.addView(copy);
        image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        root.addView(image,new LinearLayout.LayoutParams(-1,0,1));
        MaterialButton back=new MaterialButton(this);back.setText("Back");back.setOnClickListener(v->finish());root.addView(back);
        setContentView(root);setBusy(true);
        worker=new Thread(()->{
            HasselbladProfile43 stored=null;
            try(InputStream in=profileFile().openRead()){stored=HasselbladProfile43.read(in);}catch(Exception ignored){}
            final HasselbladProfile43 loaded=stored;
            runOnUiThread(()->{if(isFinishing()||isDestroyed())return;profile=loaded;setBusy(false);
                if(profile!=null)status.setText("Colour profile ready. Open a saved standard-resolution DNG.\n"+
                    "Experimental preview; camera photos still use Photon.");});
        },"HB43-profile-restore");worker.start();
    }
    private void setBusy(boolean value) {
        busy=value;importProfile.setEnabled(!busy);open.setEnabled(!busy&&profile!=null);
        toggle.setEnabled(!busy&&experiment!=null);copy.setEnabled(!busy&&report!=null);
    }
    private void clearPreview() {
        image.setImageDrawable(null);
        if(experiment!=null)experiment.recycle();if(baseline!=null)baseline.recycle();
        experiment=baseline=null;report=null;showBaseline=false;
    }
    private void fail(Throwable error) {
        runOnUiThread(()->{if(isFinishing()||isDestroyed())return;
            setBusy(false);status.setText("Could not render: "+error.getMessage());});
    }
    private void loadProfile(Uri uri) {
        if(busy)return;clearPreview();setBusy(true);status.setText("Checking colour profile…");
        worker=new Thread(()->{
            try(InputStream in=getContentResolver().openInputStream(uri)) {
                HasselbladProfile43 loaded=HasselbladProfile43.read(in);
                // Validate core parameters before replacing the last usable profile.
                HasselbladRenderer42.render(new short[]{0,0,0},loaded.parameters(new double[]{1,0,0,0,1,0,0,0,1}),
                    loaded.grid,loaded.curve,loaded.gridWidth,loaded.gridHeight,1);
                AtomicFile file=profileFile();FileOutputStream out=null;
                try {out=file.startWrite();out.write(loaded.encoded());file.finishWrite(out);}
                catch(Exception e){if(out!=null)file.failWrite(out);throw e;}
                runOnUiThread(()->{if(isFinishing()||isDestroyed())return;
                    profile=loaded;setBusy(false);status.setText("Profile ready · look temperature "+loaded.temperature+
                        " K. Open a saved DNG. Its own white balance will be used.");});
            }catch(Exception|LinkageError e){fail(e);}
        },"HB43-profile-import");worker.start();
    }
    private static Bitmap bitmap(int[] rgb,HasselbladDngTileReader.PreviewResult p) {
        Bitmap base=Bitmap.createBitmap(rgb,p.width,p.height,Bitmap.Config.ARGB_8888);
        if(p.orientation==1)return base;
        Matrix m=new Matrix();m.postRotate(p.orientation==3?180:p.orientation==6?90:270);
        Bitmap rotated=Bitmap.createBitmap(base,0,0,p.width,p.height,m,false);
        if(rotated!=base)base.recycle();return rotated;
    }
    private void show() {
        image.setImageBitmap(showBaseline?baseline:experiment);
        image.setContentDescription(showBaseline?"Same RAW neutral sRGB baseline":"Experimental colour preview");
        toggle.setText(showBaseline?"Show experimental render":"Show same-RAW baseline");
    }
    private void loadDng(Uri uri) {
        if(busy||profile==null)return;
        clearPreview();setBusy(true);status.setText("Preparing and rendering the saved DNG…");
        final HasselbladProfile43 look=profile;
        worker=new Thread(()->{
            File temporary=null;Bitmap rendered=null,reference=null;
            try {
                long start=SystemClock.elapsedRealtime();
                temporary=File.createTempFile("hb43-",".dng",getCacheDir());
                try(InputStream in=getContentResolver().openInputStream(uri);FileOutputStream out=new FileOutputStream(temporary)) {
                    if(in==null)throw new IOException("Cannot open DNG");
                    byte[] buffer=new byte[65536];long bytes=0;int n;
                    while((n=in.read(buffer))!=-1) {
                        if(Thread.currentThread().isInterrupted())throw new IOException("DNG preview cancelled");
                        bytes+=n;if(bytes>256L*1024*1024)throw new IOException("DNG exceeds 256 MB preview limit");
                        out.write(buffer,0,n);
                    }
                }
                long copied=SystemClock.elapsedRealtime();
                HasselbladDngTileReader.PreviewResult p=HasselbladDngTileReader.readPreview(temporary,1048576);
                long prepared=SystemClock.elapsedRealtime();
                var meta=p.metadata;
                double[] camera=HasselbladRenderer42.cameraToD50(meta.forwardMatrix1,meta.forwardMatrix2,
                    meta.calibration1,meta.calibration2,meta.analogBalance,meta.asShotNeutral);
                double[] params=look.parameters(camera),display=HasselbladRenderer42.xyzToSrgb();
                long calibrated=SystemClock.elapsedRealtime();
                short[] rgb=HasselbladRenderer42.render(p.cameraRgb16,params,look.grid,look.curve,look.gridWidth,look.gridHeight,1);
                long core=SystemClock.elapsedRealtime();
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG preview cancelled");
                rendered=bitmap(look.display(rgb),p);reference=bitmap(HasselbladProfile43.baseline(p.cameraRgb16,camera,display),p);
                long done=SystemClock.elapsedRealtime();
                JSONObject j=new JSONObject();j.put("schema","hasselblad-stage43-device-dng-v1");j.put("status","RENDERED_EXPERIMENTAL");
                j.put("raw_width",meta.width);j.put("raw_height",meta.height);j.put("preview_width",p.width);j.put("preview_height",p.height);
                j.put("sample_step",p.step);j.put("orientation",p.orientation);
                j.put("copy_milliseconds",copied-start);j.put("raw_preparation_milliseconds",prepared-copied);
                j.put("calibration_milliseconds",calibrated-prepared);j.put("core_milliseconds",core-calibrated);
                j.put("display_milliseconds",done-core);j.put("total_milliseconds",done-start);
                j.put("gainmap_count",meta.gainMapCount);j.put("input_negative_channels_clipped",p.negativeChannels);
                j.put("input_over_unity_channels_clipped",p.overUnityChannels);
                j.put("wb_owner",1);j.put("camera_matrix_source","selected DNG ForwardMatrix and AsShotNeutral");
                j.put("lut_temperature_manual",look.temperature);j.put("model_code",look.model);j.put("film_code",look.film);j.put("working_space_code",look.space);
                j.put("display_adapter","explicit internal basis to sRGB");j.put("host_reference_compared",false);
                j.put("source_dng_modified",false);j.put("phone_sensor_adaptation_experimental",true);
                j.put("capture_renderer_changed",false);j.put("full_phocus_equivalence",false);
                final Bitmap result=rendered,base=reference;final String receipt=j.toString();
                runOnUiThread(()->{
                    if(isFinishing()||isDestroyed()){result.recycle();base.recycle();return;}
                    experiment=result;baseline=base;report=receipt;showBaseline=false;setBusy(false);show();
                    status.setText("Experimental DNG preview · "+p.width+" × "+p.height+" · "+(done-start)+" ms total\n"+
                        "Uses this DNG’s white balance. Camera photos still use Photon.");
                });rendered=reference=null;
            }catch(Exception|LinkageError e){fail(e);}
            finally {
                if(temporary!=null)temporary.delete();
                if(rendered!=null)rendered.recycle();if(reference!=null)reference.recycle();
            }
        },"HB43-saved-dng-render");worker.start();
    }
    @Override protected void onDestroy() {
        if(worker!=null)worker.interrupt();clearPreview();super.onDestroy();
    }
}
