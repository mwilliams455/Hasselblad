package com.particlesdevs.photoncamera.hasselblad;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.View;
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
import java.io.InputStream;

/** Explicit saved-RAW colour preview. The camera capture pipeline is not called. */
public final class HasselbladRenderActivity42 extends BaseActivity {
    private ImageView image;
    private TextView status;
    private MaterialButton open,toggle,copy;
    private Bitmap experiment,baseline;
    private boolean busy,showBaseline;
    private String report;
    private final ActivityResultLauncher<String[]> picker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null)load(uri);});
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(16*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(root,(view,insets)->{
            Insets bars=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(pad+bars.left,pad+bars.top,pad+bars.right,pad+bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        TextView title=new TextView(this);title.setText("Experimental colour · Stage42");
        title.setTextSize(22);root.addView(title);
        status=new TextView(this);status.setText("Open the prepared .hb42 saved-RAW preview. " +
            "Compare the new colour render with the same RAW's neutral baseline. " +
            "Camera photos still use Photon.");root.addView(status);
        open=new MaterialButton(this);open.setText("Open saved-RAW experiment");
        open.setOnClickListener(v->{if(!busy)picker.launch(new String[]{"*/*"});});root.addView(open);
        toggle=new MaterialButton(this);toggle.setText("Show same-RAW baseline");toggle.setEnabled(false);
        toggle.setOnClickListener(v->{showBaseline=!showBaseline;show();});root.addView(toggle);
        copy=new MaterialButton(this);copy.setText("Copy render report");copy.setEnabled(false);
        copy.setOnClickListener(v->{
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            if(clipboard!=null&&report!=null)clipboard.setPrimaryClip(ClipData.newPlainText("Stage42",report));
        });root.addView(copy);
        image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setContentDescription("Saved RAW colour comparison");
        root.addView(image,new LinearLayout.LayoutParams(-1,0,1));
        MaterialButton back=new MaterialButton(this);back.setText("Back");back.setOnClickListener(v->finish());
        root.addView(back);setContentView(root);
    }
    private void show() {
        image.setImageBitmap(showBaseline?baseline:experiment);
        toggle.setText(showBaseline?"Show experimental render":"Show same-RAW baseline");
        image.setContentDescription(showBaseline?"Same RAW neutral sRGB baseline":"Experimental Phocus-derived colour render");
    }
    private static Bitmap bitmap(int[] rgb,HasselbladRenderBundle42 b) {
        Bitmap base=Bitmap.createBitmap(rgb,b.width,b.height,Bitmap.Config.ARGB_8888);
        if(b.orientation==1)return base;
        Matrix rotation=new Matrix();rotation.postRotate(90);
        Bitmap rotated=Bitmap.createBitmap(base,0,0,b.width,b.height,rotation,false);
        if(rotated!=base)base.recycle();return rotated;
    }
    private void load(Uri uri) {
        if(busy)return;
        busy=true;report=null;open.setEnabled(false);toggle.setEnabled(false);copy.setEnabled(false);
        image.setImageDrawable(null);
        if(experiment!=null)experiment.recycle();if(baseline!=null)baseline.recycle();
        experiment=baseline=null;
        status.setText("Rendering saved RAW colour on this device…");
        new Thread(()->{
            try(InputStream input=getContentResolver().openInputStream(uri)) {
                HasselbladRenderBundle42 b=HasselbladRenderBundle42.read(input);
                long start=SystemClock.elapsedRealtime();
                short[] rgb=HasselbladRenderer42.render(b.input,b.parameters,b.grid,b.curve,
                    b.gridWidth,b.gridHeight,b.wbOwner);
                long coreMs=SystemClock.elapsedRealtime()-start;
                boolean match=b.matches(rgb);
                final Bitmap rendered=bitmap(b.display(rgb),b),reference=bitmap(b.baseline,b);
                JSONObject json=new JSONObject();json.put("schema","hasselblad-stage42-device-render-v1");
                json.put("status",match?"PASS_EXACT_RGB16":"OUTPUT_DIFFERS_FROM_HOST");
                json.put("pixels",b.width*b.height);json.put("core_milliseconds",coreMs);
                json.put("reference_rgb16_exact",match);json.put("wb_owner",b.wbOwner);
                json.put("lut_temperature",b.temperature);json.put("model_code",b.model);
                json.put("film_code",b.film);json.put("working_space_code",b.space);
                json.put("display_adapter","explicit internal basis to sRGB");
                json.put("phone_sensor_adaptation_experimental",true);
                json.put("capture_renderer_changed",false);json.put("full_phocus_equivalence",false);
                final String result=json.toString();
                runOnUiThread(()->{
                    if(isFinishing()||isDestroyed()){rendered.recycle();reference.recycle();return;}
                    experiment=rendered;baseline=reference;report=result;busy=false;showBaseline=false;
                    open.setEnabled(true);toggle.setEnabled(true);copy.setEnabled(true);show();
                    status.setText("Experimental render · "+b.width+" × "+b.height+" · "+coreMs+" ms\n"+
                        (match?"RGB16 output matches the host reference exactly.":"RGB16 differs from the host reference. Copy the report.")+
                        "\nPhone colour adaptation is experimental; camera photos still use Photon.");
                });
            } catch(Exception|LinkageError error) {
                runOnUiThread(()->{
                    if(isFinishing()||isDestroyed())return;
                    busy=false;open.setEnabled(true);
                    status.setText("Preview could not be rendered: "+error.getMessage());
                });
            }
        },"HB42-saved-raw-render").start();
    }
    @Override protected void onDestroy() {
        if(image!=null)image.setImageDrawable(null);
        if(experiment!=null)experiment.recycle();if(baseline!=null)baseline.recycle();
        super.onDestroy();
    }
}
