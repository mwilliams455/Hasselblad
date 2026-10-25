package com.particlesdevs.photoncamera.hasselblad;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.*;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import com.google.android.material.button.MaterialButton;
import com.particlesdevs.photoncamera.app.base.BaseActivity;
import org.json.JSONObject;
import java.io.*;
import java.util.*;

/** Normal camera look controls. No profile is changed merely by opening this screen. */
public final class HasselbladLook84Activity extends BaseActivity {
    private TextView status,active,last;
    private MaterialButton curve0,curve1;
    private CheckBox diagnostics;
    private boolean updatingDiagnostics;
    private final List<MaterialButton> controls=new ArrayList<>();
    private boolean busy;
    private volatile boolean destroyed;
    private Thread worker;
    private String profileHash;
    private final ActivityResultLauncher<String[]> profilePicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null&&!busy)importFile(uri,false);});
    private final ActivityResultLauncher<String[]> packPicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null&&!busy)importFile(uri,true);});
    private MaterialButton button(LinearLayout root,String label,Runnable action) {
        MaterialButton b=new MaterialButton(this);b.setText(label);b.setOnClickListener(v->{if(!busy)action.run();});root.addView(b);controls.add(b);return b;
    }
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);scroll.addView(root);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(scroll,(view,insets)->{Insets b=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(pad+b.left,pad+b.top,pad+b.right,pad+b.bottom);return WindowInsetsCompat.CONSUMED;});
        TextView title=new TextView(this);title.setText("Hasselblad rendering");title.setTextSize(22);root.addView(title);
        active=new TextView(this);active.setTextSize(18);root.addView(active);
        TextView help=new TextView(this);help.setText("The selected curve applies to saved JPEGs. The live viewfinder does not yet show this look. " +
            "Use standard RAW, 4:3 and no digital zoom for the Hasselblad capture path.");root.addView(help);
        status=new TextView(this);root.addView(status);
        curve1=button(root,"Use curve 1 · deeper midtones",()->select(1));
        curve0=button(root,"Use curve 0 · brighter midtones",()->select(0));
        button(root,"Import automatic colour profile (.hbc)",()->profilePicker.launch(new String[]{"*/*"}));
        button(root,"Import tone pack (.hbt)",()->packPicker.launch(new String[]{"*/*"}));
        button(root,"Compare tone curves on a saved DNG",()->startActivity(new Intent(this,HasselbladTone83Activity.class)));
        button(root,"Compare sharpening on a saved DNG",()->startActivity(new Intent(this,HasselbladSharp86Activity.class)));
        diagnostics=new CheckBox(this);diagnostics.setText("Capture diagnostics");
        diagnostics.setChecked(HasselbladDiagnostics86.enabled(this));root.addView(diagnostics);
        diagnostics.setOnCheckedChangeListener((button,checked)->{if(updatingDiagnostics||busy)return;
            run("Saving diagnostic preference…",()->{HasselbladDiagnostics86.setEnabled(this,checked);
                if(!checked){HasselbladCapture79.clearDiagnostics86(this);HasselbladSceneDiagnostics.reset();HasselbladDomainDiagnostics.clear();}
                return checked?"Diagnostics enabled for new captures.":"Diagnostics off. New captures create no capture JSON or cached comparison files.";});});
        TextView diagnosticHelp=new TextView(this);diagnosticHelp.setText("Leave diagnostics off for ordinary photos. Enable only for a requested capture investigation. Choose Save → JPEG in camera settings for JPEG-only shooting. Explicit saved-DNG comparisons remain available.");root.addView(diagnosticHelp);
        last=new TextView(this);last.setTextIsSelectable(true);root.addView(last);
        button(root,"Last photo details and export",()->startActivity(new Intent(this,HasselbladCapture79Activity.class)));
        button(root,"Refresh",()->refresh(null));button(root,"Back",this::finish);setContentView(scroll);
    }
    @Override protected void onResume(){super.onResume();if(!busy)refresh(null);}
    private void busy(boolean value){busy=value;if(diagnostics!=null)diagnostics.setEnabled(!value);for(MaterialButton b:controls)b.setEnabled(!value);curve0.setEnabled(false);curve1.setEnabled(false);}
    private interface Work {String run()throws Exception;}
    private void run(String message,Work task) {
        busy(true);status.setText(message);
        worker=new Thread(()->{String result;try{result=task.run();}catch(Exception|LinkageError e){result="Could not update: "+e.getMessage();}
            final String text=result;runOnUiThread(()->{if(!destroyed){busy(false);refresh(text);}});},"HB84-look");worker.start();
    }
    private void select(int film) {
        final String expected=profileHash;
        run("Saving curve selection…",()->{HasselbladProfile43 selected=HasselbladLookStore84.select(this,expected,film);
            return HasselbladLook84.label(selected.film)+" saved for subsequent camera JPEGs.";});
    }
    private void importFile(Uri uri,boolean tonePack) {
        run("Checking imported file…",()->{
            try(InputStream in=getContentResolver().openInputStream(uri)) {
                if(tonePack){HasselbladLookStore84.importPack(this,HasselbladTone83.read(in));return "Tone pack ready. Select curve 0 or 1.";}
                HasselbladProfile43 p=HasselbladProfile43.read(in);
                if(!p.hasAutomaticIlluminant||!p.hasNativeFinishing)throw new IOException("Choose an automatic .hbc profile with native finishing.");
                p.finishRgb16(HasselbladRenderer42.render(new short[]{0,0,0},p.parameters(new double[]{1,0,0,0,1,0,0,0,1}),p.grid,p.curve,p.gridWidth,p.gridHeight,1));
                HasselbladLookStore84.importProfile(this,p);return "Colour profile imported. Active look: "+HasselbladLook84.label(p.film)+".";
            }
        });
    }
    private void refresh(String notice) {
        if(busy||destroyed)return;busy(true);
        worker=new Thread(()->{String activeText="No automatic colour profile imported.",detail="Import your automatic .hbc profile first.",hash=null;
            int film=-1;boolean compatible=false;
            try {
                HasselbladProfile43 p=HasselbladLookStore84.read(this);film=p.film;hash=HasselbladLook84.sha256(p.encoded());
                activeText="Active look: "+HasselbladLook84.label(film);
                detail=p.hasAutomaticIlluminant&&p.hasNativeFinishing?"Automatic LUT selection and native sRGB finishing enabled.":"This profile is not compatible with normal camera rendering. Import an automatic .hbc profile.";
                try{HasselbladLookStore84.readPack(this).validateProfile(p);compatible=true;}
                catch(FileNotFoundException e){detail+="\nImport the tone pack to switch curves.";}
                catch(Exception e){detail+="\nCurve switching unavailable: "+e.getMessage();}
            }catch(FileNotFoundException e) {/* First import. */}
            catch(Exception e){detail="Profile unavailable: "+e.getMessage();}
            String capture;
            try {
                String text=HasselbladCapture79.lastReport(this);
                if(!text.startsWith("{"))capture=text;
                else {
                    JSONObject j=new JSONObject(text);String state=j.optString("status");
                    if("HASSELBLAD_SHUTTER_RENDERED".equals(state))
                        capture="Last saved photo: "+(j.has("film_curve_code")?HasselbladLook84.label(j.getInt("film_curve_code")):"curve not recorded by the older build")+"\nAutomatic LUT "+j.optInt("automatic_lut_kelvin")+" K";
                    else if("RAW_ONLY_SAVED".equals(state))capture="Last capture: RAW only. No JPEG tone curve was applied.";
                    else if("PHOTON_FALLBACK".equals(state))capture="Last capture routed to Photon: "+j.optString("reason");
                    else capture="Last capture: "+state+"\n"+j.optString("reason");
                }
            }catch(Exception e){capture="Last photo report unavailable.";}
            final String a=activeText,d=detail,s=hash,c=capture;final int f=film;final boolean enabled=compatible;
            runOnUiThread(()->{if(destroyed)return;profileHash=s;active.setText(a);last.setText(c);status.setText((notice==null?"":notice+"\n")+d);
                updatingDiagnostics=true;diagnostics.setChecked(HasselbladDiagnostics86.enabled(this));updatingDiagnostics=false;
                busy(false);curve0.setEnabled(enabled&&f!=0);curve1.setEnabled(enabled&&f!=1);
                curve0.setText(f==0?"Curve 0 · active":"Use curve 0 · brighter midtones");curve1.setText(f==1?"Curve 1 · active":"Use curve 1 · deeper midtones");});
        },"HB84-status");worker.start();
    }
    @Override protected void onDestroy(){destroyed=true;if(worker!=null)worker.interrupt();super.onDestroy();}
}
