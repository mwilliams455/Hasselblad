package com.particlesdevs.photoncamera.hasselblad;

import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import com.google.android.material.button.MaterialButton;
import com.particlesdevs.photoncamera.app.base.BaseActivity;
import java.io.OutputStream;

/** Small last-capture receipt/export surface; never blocks the camera processing thread. */
public final class HasselbladCapture79Activity extends BaseActivity {
    private TextView status;
    private MaterialButton save;
    private volatile boolean destroyed;
    private final ActivityResultLauncher<String> exporter=registerForActivityResult(
            new ActivityResultContracts.CreateDocument("application/zip"),uri->{
                if(uri==null)return;save.setEnabled(false);
                new Thread(()->{
                    String message;
                    try(OutputStream out=getContentResolver().openOutputStream(uri,"w")) {
                        if(out==null)throw new java.io.IOException("Cannot open export");
                        HasselbladCapture79.export(getApplicationContext(),out);message="Capture comparison saved.";
                    }catch(Exception e){message="Export stopped: "+e.getMessage();}
                    final String text=message;
                    runOnUiThread(()->{if(!destroyed){status.setText(text);save.setEnabled(true);}});
                },"HB82-export").start();
            });
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);scroll.addView(root);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(scroll,(v,insets)->{Insets b=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(pad+b.left,pad+b.top,pad+b.right,pad+b.bottom);return WindowInsetsCompat.CONSUMED;});
        TextView title=new TextView(this);title.setText("Stage82 · shutter colour");title.setTextSize(22);root.addView(title);
        TextView help=new TextView(this);help.setText("Use the imported automatic .hbc profile, standard RAW, 4:3 and no digital zoom. Take a normal PHOTO. " +
                "Compatible captures use the validated colour renderer with a 32-pixel edge crop; other captures use Photon and record the reason below. " +
                "For the first comparison, select RAW + JPEG and also render that saved DNG through Stage78. " +
                "This export includes the last Stage82 JPEG, report and small Bayer/RGB samples, including a completed render if public saving fails. It excludes the full DNG and profile.");root.addView(help);
        status=new TextView(this);status.setTextIsSelectable(true);root.addView(status);
        MaterialButton refresh=new MaterialButton(this);refresh.setText("Refresh last capture report");refresh.setOnClickListener(v->refresh());root.addView(refresh);
        save=new MaterialButton(this);save.setText("Export last shutter comparison ZIP");
        save.setOnClickListener(v->exporter.launch("Hasselblad_Stage82_Shutter_Comparison.zip"));root.addView(save);
        MaterialButton back=new MaterialButton(this);back.setText("Back");back.setOnClickListener(v->finish());root.addView(back);
        setContentView(scroll);refresh();
    }
    private void refresh(){try{status.setText(HasselbladCapture79.lastReport(this));}catch(Exception e){status.setText("Report unavailable: "+e.getMessage());}}
    @Override protected void onDestroy(){destroyed=true;super.onDestroy();}
}
