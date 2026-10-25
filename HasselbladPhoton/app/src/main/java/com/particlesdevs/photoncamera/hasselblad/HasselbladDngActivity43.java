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
    private MaterialButton importProfile,open,toggle,copy,device75,scene76;
    private HasselbladProfile43 profile;
    private Bitmap experiment,highlight,finished,automatic,automaticOnly,rawPrepared,baseline;
    private boolean busy;
    private int previewMode;
    private String previewSummary;
    private String report;
    private Thread worker;
    private final ActivityResultLauncher<String[]> profilePicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null)loadProfile(uri);});
    private final ActivityResultLauncher<String[]> dngPicker=registerForActivityResult(
        new ActivityResultContracts.OpenDocument(),uri->{if(uri!=null)loadDng(uri);});
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(12*getResources().getDisplayMetrics().density);
        ViewCompat.setOnApplyWindowInsetsListener(root,(view,insets)->{
            Insets bars=insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(pad+bars.left,pad+bars.top,pad+bars.right,pad+bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        TextView title=new TextView(this);title.setText("Saved DNG colour");title.setTextSize(22);root.addView(title);
        status=new TextView(this);status.setText("Import your .hbc colour profile, then open a saved DNG. " +
            "The preview uses that DNG’s calibration and white balance. Tone comparison uses the same saved-DNG calibration.");root.addView(status);
        MaterialButton tone83=new MaterialButton(this);tone83.setText("Tone curve comparison");
        tone83.setOnClickListener(v->{if(!busy)startActivity(new android.content.Intent(this,HasselbladTone83Activity.class));});root.addView(tone83);
        importProfile=new MaterialButton(this);importProfile.setText("Import colour profile");
        importProfile.setOnClickListener(v->{if(!busy)profilePicker.launch(new String[]{"*/*"});});root.addView(importProfile);
        open=new MaterialButton(this);open.setText("Open saved DNG");
        open.setOnClickListener(v->{if(!busy)dngPicker.launch(new String[]{"*/*"});});root.addView(open);
        toggle=new MaterialButton(this);toggle.setText("Show highlight reconstruction");
        toggle.setOnClickListener(v->{previewMode=nextMode();show();});root.addView(toggle);
        scene76=new MaterialButton(this);scene76.setText("Stage76 · full-scene colour and LUTs");
        scene76.setOnClickListener(v->{if(!busy)startActivity(new android.content.Intent(this,HasselbladScene76Activity.class));});root.addView(scene76);
        MaterialButton scene77=new MaterialButton(this);scene77.setText("Stage77 · faster full-scene colour and LUTs");
        scene77.setOnClickListener(v->{if(!busy)startActivity(new android.content.Intent(this,HasselbladScene77Activity.class));});root.addView(scene77);
        MaterialButton capture79=new MaterialButton(this);capture79.setText("Last camera photo · colour and save report");
        capture79.setOnClickListener(v->{if(!busy)startActivity(new android.content.Intent(this,HasselbladCapture79Activity.class));});root.addView(capture79);
        MaterialButton scene78=new MaterialButton(this);scene78.setText("Stage78 · faster RAW preparation and colour");
        scene78.setOnClickListener(v->{if(!busy)startActivity(new android.content.Intent(this,HasselbladScene78Activity.class));});root.addView(scene78);
        device75=new MaterialButton(this);device75.setText("Stage75 · demosaic + colour tile test");
        device75.setOnClickListener(v->{if(!busy)startActivity(new android.content.Intent(this,HasselbladDevice75Activity.class));});
        root.addView(device75);
        copy=new MaterialButton(this);copy.setText("Copy render report");
        copy.setOnClickListener(v->{
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            if(clipboard!=null&&report!=null)clipboard.setPrimaryClip(ClipData.newPlainText("Stage58",report));
        });root.addView(copy);
        image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        root.addView(image,new LinearLayout.LayoutParams(-1,0,1));
        MaterialButton back=new MaterialButton(this);back.setText("Back");back.setOnClickListener(v->finish());root.addView(back);
        setContentView(root);setBusy(true);
        worker=new Thread(()->{
            HasselbladProfile43 stored=null;
            try{stored=HasselbladLookStore84.read(this);}catch(Exception ignored){}
            final HasselbladProfile43 loaded=stored;
            runOnUiThread(()->{if(isFinishing()||isDestroyed())return;profile=loaded;setBusy(false);
                if(profile!=null)status.setText("Profile ready: "+HasselbladLook84.label(profile.film)+". Open a saved standard-resolution DNG.");});
        },"HB43-profile-restore");worker.start();
    }
    private void setBusy(boolean value) {
        busy=value;scene76.setEnabled(!busy);device75.setEnabled(!busy);importProfile.setEnabled(!busy);open.setEnabled(!busy&&profile!=null);
        toggle.setEnabled(!busy&&experiment!=null);copy.setEnabled(!busy&&report!=null);
    }
    private void clearPreview() {
        image.setImageDrawable(null);
        if(experiment!=null)experiment.recycle();if(highlight!=null)highlight.recycle();if(finished!=null)finished.recycle();if(automatic!=null)automatic.recycle();if(automaticOnly!=null)automaticOnly.recycle();if(rawPrepared!=null)rawPrepared.recycle();if(baseline!=null)baseline.recycle();
        experiment=highlight=finished=automatic=automaticOnly=rawPrepared=baseline=null;report=null;previewMode=0;previewSummary=null;
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
                if(loaded.hasNativeFinishing)loaded.finishRgb16(new short[]{0,0,0});
                HasselbladLookStore84.importProfile(this,loaded);
                runOnUiThread(()->{if(isFinishing()||isDestroyed())return;
                    profile=loaded;setBusy(false);status.setText(loaded.hasAutomaticIlluminant?"Automatic-colour profile ready: "+HasselbladLook84.label(loaded.film)+". Open a saved DNG. Its own white balance will be used.":
                        "Profile ready · look temperature "+loaded.temperature+" K. Open a saved DNG. Its own white balance will be used.");});
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
    private int nextMode() {
        int next=(previewMode+1)%7;
        if(next==2&&finished==null)next=3;
        if(next==3&&automatic==null)next=4;
        if(next==4&&automaticOnly==null)next=5;
        if(next==5&&rawPrepared==null)next=6;
        return next;
    }
    private void show() {
        image.setImageBitmap(previewMode==0?experiment:previewMode==1?highlight:previewMode==2?finished:previewMode==3?automatic:previewMode==4?automaticOnly:previewMode==5?rawPrepared:baseline);
        String label=previewMode==0?"Original colour preview":previewMode==1?
            "Highlight reconstruction · experimental":previewMode==2?"Native finishing · experimental":
            previewMode==3?"Automatic colour · reconstruction on":
            previewMode==4?"Automatic colour · reconstruction off":
            previewMode==5?"Automatic colour · DNG preparation":"Same-RAW neutral baseline";
        image.setContentDescription(label);
        int next=nextMode();toggle.setText(next==1?"Show highlight reconstruction":next==2?
            "Show native finishing":next==3?"Show automatic colour":next==4?"Show automatic colour only":next==5?"Show DNG preparation":next==6?"Show neutral baseline":"Show original colour preview");
        if(report!=null)try {
            JSONObject j=new JSONObject(report);j.put("displayed_preview",previewMode==0?"original":
                previewMode==1?"highlight":previewMode==2?"native_finishing":previewMode==3?"automatic_colour":previewMode==4?"automatic_colour_only":previewMode==5?"automatic_dng_preparation":"neutral");
            j.put("displayed_lut_temperature",previewMode==6?JSONObject.NULL:
                j.get(previewMode>=3&&previewMode<=5?"lut_temperature_selected":"lut_temperature_manual"));
            j.put("displayed_highlight_reconstruction",previewMode>=1&&previewMode<=3);
            j.put("displayed_native_finishing",previewMode>=2&&previewMode<=5);
            j.put("displayed_raw_preparation",previewMode==5?"DNG common range and pre-demosaic clipping":"legacy Stage43 preparation");
            j.put("displayed_finishing_input",previewMode==5?"automatic colour from DNG-prepared RGB16":previewMode==4?"automatic colour from prepared RGB16":
                previewMode==2||previewMode==3?"colour from highlight-reconstructed RGB16":JSONObject.NULL);report=j.toString();
        }catch(org.json.JSONException ignored){}
        if(previewSummary!=null)status.setText(label+"\n"+previewSummary);
    }
    private void loadDng(Uri uri) {
        if(busy||profile==null)return;
        clearPreview();setBusy(true);status.setText("Preparing and rendering the saved DNG…");
        final HasselbladProfile43 look=profile;
        worker=new Thread(()->{
            File temporary=null;Bitmap rendered=null,reconstructed=null,completed=null,autoCompleted=null,onlyCompleted=null,rawCompleted=null,reference=null;
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
                HasselbladDngTileReader.PreviewResult p=HasselbladDngTileReader.readPreviewWithPreparation58(temporary,1048576);
                long prepared=SystemClock.elapsedRealtime();
                var meta=p.metadata;
                double[] camera=HasselbladRenderer42.cameraToD50(meta.forwardMatrix1,meta.forwardMatrix2,
                    meta.calibration1,meta.calibration2,meta.analogBalance,meta.asShotNeutral);
                double[] params=look.parameters(camera),display=HasselbladRenderer42.xyzToSrgb();
                long calibrated=SystemClock.elapsedRealtime();
                short[] rgb=HasselbladRenderer42.render(p.cameraRgb16,params,look.grid,look.curve,look.gridWidth,look.gridHeight,1);
                long core=SystemClock.elapsedRealtime();
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG preview cancelled");
                var highlightPlan=HasselbladPreparedHighlight54.prepare(camera,meta.asShotNeutral);
                short[] highlightInput=highlightPlan.reconstruct(p.cameraRgb16);
                long recovered=SystemClock.elapsedRealtime();
                short[] highlightRgb=HasselbladRenderer42.render(highlightInput,look.parameters(highlightPlan.afterMatrix),
                    look.grid,look.curve,look.gridWidth,look.gridHeight,1);
                long highlightCore=SystemClock.elapsedRealtime();
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG preview cancelled");
                short[] finishedRgb=look.hasNativeFinishing?look.finishRgb16(highlightRgb):null;
                long finishedAt=SystemClock.elapsedRealtime();
                HasselbladIlluminant56.Result selection=null;
                short[] automaticRgb=null;String automaticFallback="Import an automatic-colour profile";
                if(look.hasAutomaticIlluminant) {
                    automaticFallback=meta.illuminant.error;
                    if(automaticFallback==null)try {
                        selection=HasselbladIlluminant56.estimate(meta.illuminant.colorMatrix1,meta.illuminant.colorMatrix2,
                            meta.illuminant.light1,meta.illuminant.light2,meta.calibration1,meta.calibration2,
                            meta.analogBalance,meta.asShotNeutral);
                    }catch(IllegalArgumentException e){automaticFallback=e.getMessage();}
                    if(selection!=null) {
                        short[] colour=HasselbladRenderer42.render(highlightInput,look.parameters(highlightPlan.afterMatrix),
                            look.gridAtTemperature(selection.lutKelvin),look.curve,look.gridWidth,look.gridHeight,1);
                        automaticRgb=look.finishRgb16(colour);
                    }
                }
                long automaticAt=SystemClock.elapsedRealtime();
                short[] automaticOnlyRgb=null;
                if(selection!=null) {
                    short[] colour=HasselbladRenderer42.render(p.cameraRgb16,params,look.gridAtTemperature(selection.lutKelvin),
                        look.curve,look.gridWidth,look.gridHeight,1);
                    automaticOnlyRgb=look.finishRgb16(colour);
                }
                long automaticOnlyAt=SystemClock.elapsedRealtime();
                short[] rawPreparedRgb=null;
                if(selection!=null) {
                    short[] colour=HasselbladRenderer42.render(p.preparation58.rgb16,params,look.gridAtTemperature(selection.lutKelvin),
                        look.curve,look.gridWidth,look.gridHeight,1);
                    rawPreparedRgb=look.finishRgb16(colour);
                }
                long rawPreparedAt=SystemClock.elapsedRealtime();
                if(Thread.currentThread().isInterrupted())throw new IOException("DNG preview cancelled");
                if(rawPreparedRgb!=null)rawCompleted=bitmap(HasselbladProfile43.srgb16ToArgb(rawPreparedRgb),p);
                if(automaticOnlyRgb!=null)onlyCompleted=bitmap(HasselbladProfile43.srgb16ToArgb(automaticOnlyRgb),p);
                if(automaticRgb!=null)autoCompleted=bitmap(HasselbladProfile43.srgb16ToArgb(automaticRgb),p);
                if(finishedRgb!=null)completed=bitmap(HasselbladProfile43.srgb16ToArgb(finishedRgb),p);
                rendered=bitmap(look.display(rgb),p);reconstructed=bitmap(look.display(highlightRgb),p);
                reference=bitmap(HasselbladProfile43.baseline(p.cameraRgb16,camera,display),p);
                long done=SystemClock.elapsedRealtime();
                long ceiling=0,changed=0;
                for(int i=0;i<p.cameraRgb16.length;i++) {
                    if((p.cameraRgb16[i]&65535)==65535)ceiling++;
                    if(rgb[i]!=highlightRgb[i])changed++;
                }
                JSONObject j=new JSONObject();j.put("schema","hasselblad-stage58-device-dng-v1");j.put("status","RENDERED_EXPERIMENTAL_COMPARISON");
                j.put("raw_width",meta.width);j.put("raw_height",meta.height);j.put("preview_width",p.width);j.put("preview_height",p.height);
                j.put("sample_step",p.step);j.put("orientation",p.orientation);
                j.put("copy_milliseconds",copied-start);j.put("raw_preparation_milliseconds",prepared-copied);
                j.put("calibration_milliseconds",calibrated-prepared);j.put("core_milliseconds",core-calibrated);
                j.put("highlight_preparation_milliseconds",recovered-core);
                j.put("highlight_colour_core_milliseconds",highlightCore-recovered);
                j.put("finishing_milliseconds",finishedAt-highlightCore);
                j.put("automatic_colour_milliseconds",automaticAt-finishedAt);
                j.put("automatic_colour_only_milliseconds",automaticOnlyAt-automaticAt);
                j.put("dng_preparation_colour_milliseconds",rawPreparedAt-automaticOnlyAt);
                j.put("display_milliseconds",done-rawPreparedAt);j.put("total_milliseconds",done-start);
                j.put("gainmap_count",meta.gainMapCount);j.put("input_negative_channels_clipped",p.negativeChannels);
                j.put("input_over_unity_channels_clipped",p.overUnityChannels);
                j.put("input_clipping_counter_domain","legacy Stage43 final RGB16 encoding; excludes earlier gain-map clamps");
                var audit=p.preparation58;
                j.put("dng_preparation_available",rawPreparedRgb!=null);
                j.put("dng_preparation_normalization","(raw - site black) / (WhiteLevel - maximum black in plane)");
                j.put("dng_preparation_clip_order","range 0..1; each GainMap upper clamp; bilinear; RGB16");
                j.put("raw_audit_scope","unique decoded Bayer rows used for preview; not whole RAW");
                j.put("raw_decoded_sites",audit.decodedSites);
                j.put("raw_sites_below_black",audit.rawBelowBlack);
                j.put("raw_sites_at_or_above_whitelevel",audit.rawAtOrAboveWhite);
                j.put("raw_whitelevel_is_metadata_not_measured_saturation",true);
                j.put("range_lower_clipped_sites",audit.rangeLowerClipped);
                j.put("range_upper_clipped_sites",audit.rangeUpperClipped);
                j.put("gainmap_upper_clip_events",audit.gainClipEvents);
                j.put("gainmap_upper_clipped_sites",audit.gainClippedSites);
                j.put("gainmap_clipped_sites_below_whitelevel",audit.gainClippedBelowWhite);
                j.put("diagnostic_unclamped_negative_channels",audit.unclampedNegativeChannels);
                j.put("diagnostic_unclamped_over_unity_channels",audit.unclampedOverUnityChannels);
                j.put("diagnostic_unclamped_values_used_for_render",false);
                j.put("dng_preparation_changed_rgb16_channels",audit.changedPreparedChannels);
                j.put("dng_preparation_unequal_black_levels",audit.unequalBlackLevels);
                j.put("dng_sdk_bit_exact_parity",false);
                j.put("wb_owner",1);j.put("camera_matrix_source","selected DNG ForwardMatrix and AsShotNeutral");
                j.put("highlight_input_domain","post-gainmap bilinear prepared RGB16; already clamped to 0..65535");
                j.put("highlight_clipping_levels_source","existing prepared-RGB encoding ceiling, not measured sensor saturation");
                j.put("highlight_wb_source","selected DNG AsShotNeutral; max-normalized reciprocal ratios");
                j.put("highlight_wb_factorization","post_matrix = existing_camera_to_D50 * diag(1/gainRatios)");
                j.put("highlight_prepared_ceiling_channels",ceiling);j.put("highlight_changed_colour_channels",changed);
                j.put("highlight_analytic_equal_gain_limit",highlightPlan.analyticEqualGainLimit);
                j.put("highlight_cpu_arithmetic",true);j.put("original_preview_available",true);
                j.put("original_raw_graph_reproduced",false);j.put("lost_raw_headroom_recovered",false);
                j.put("lut_temperature_manual",look.temperature);j.put("model_code",look.model);j.put("film_code",look.film);j.put("working_space_code",look.space);
                j.put("automatic_colour_available",automaticRgb!=null);
                j.put("automatic_colour_only_available",automaticOnlyRgb!=null);
                j.put("automatic_comparison_lut_and_finishing_shared",selection!=null);
                j.put("automatic_colour_only_input","prepared RGB16; highlight reconstruction bypassed");
                j.put("illuminant_selection_status",selection!=null?"SELECTED_FROM_DNG_WHITE_POINT":"MANUAL_FALLBACK");
                j.put("illuminant_fallback_reason",automaticFallback==null?JSONObject.NULL:automaticFallback);
                j.put("illuminant_source","selected DNG ColorMatrix, calibration illuminants, calibration, AnalogBalance and AsShotNeutral");
                j.put("metadata_white_point_kelvin",selection==null?JSONObject.NULL:selection.kelvin);
                j.put("native_quantized_kelvin",selection==null?JSONObject.NULL:selection.nativeKelvin);
                j.put("lut_temperature_selected",selection==null?look.temperature:selection.lutKelvin);
                j.put("illuminant_iterations",selection==null?0:selection.iterations);
                j.put("illuminant_neutral_ratio_residual",selection==null?JSONObject.NULL:selection.residual);
                j.put("illuminant_is_physical_lamp_measurement",false);j.put("DNG_white_balance_changed",false);
                j.put("native_finishing_available",look.hasNativeFinishing);
                j.put("native_finishing_input","colour and film RGB16; reconstruction depends on displayed comparison");
                j.put("native_gradation_version",1);j.put("native_gradation_defaults_only",true);
                j.put("native_finishing_output","CPU special profile 0 to 2; sRGB16 then rounded to 8-bit");
                j.put("native_live_display_reproduced",false);j.put("scene_fitted_parameters",0);
                j.put("display_adapter","legacy comparison plus optional bounded native CPU sRGB output");j.put("host_reference_compared",false);
                j.put("source_dng_modified",false);j.put("phone_sensor_adaptation_experimental",true);
                j.put("capture_renderer_changed",false);j.put("full_phocus_equivalence",false);
                final Bitmap result=rendered,enhanced=reconstructed,finish=completed,auto=autoCompleted,only=onlyCompleted,raw=rawCompleted,base=reference;final String receipt=j.toString();
                final String automaticSummary=selection!=null?"Automatic comparison available at "+selection.lutKelvin+" K. ":
                    "Automatic look unavailable; manual profile retained. ";
                runOnUiThread(()->{
                    if(isFinishing()||isDestroyed()){result.recycle();enhanced.recycle();if(finish!=null)finish.recycle();if(auto!=null)auto.recycle();if(only!=null)only.recycle();if(raw!=null)raw.recycle();base.recycle();return;}
                    experiment=result;highlight=enhanced;finished=finish;automatic=auto;automaticOnly=only;rawPrepared=raw;baseline=base;report=receipt;previewMode=0;
                    previewSummary=p.width+" × "+p.height+" · "+(done-start)+" ms total\n"+
                        automaticSummary+"Uses this DNG’s white balance. Tone comparison uses the same saved-DNG calibration.";
                    setBusy(false);show();
                });rendered=reconstructed=completed=autoCompleted=onlyCompleted=rawCompleted=reference=null;
            }catch(Exception|LinkageError e){fail(e);}
            finally {
                if(temporary!=null)temporary.delete();
                if(rendered!=null)rendered.recycle();if(reference!=null)reference.recycle();
                if(reconstructed!=null)reconstructed.recycle();if(completed!=null)completed.recycle();if(autoCompleted!=null)autoCompleted.recycle();if(onlyCompleted!=null)onlyCompleted.recycle();if(rawCompleted!=null)rawCompleted.recycle();
            }
        },"HB43-saved-dng-render");worker.start();
    }
    @Override protected void onDestroy() {
        if(worker!=null)worker.interrupt();clearPreview();super.onDestroy();
    }
}
