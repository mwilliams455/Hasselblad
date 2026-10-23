package com.particlesdevs.photoncamera.hasselblad;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.os.Bundle;
import android.net.Uri;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.button.MaterialButton;
import org.json.JSONObject;
import com.particlesdevs.photoncamera.R;
import com.particlesdevs.photoncamera.app.base.BaseActivity;

/** An explicit native-development check; it never accesses or modifies a photo. */
public final class HasselbladDevelopmentActivity extends BaseActivity {
    private HasselbladNativeCheck.Report latestReport;
    private volatile JSONObject latestDomainReport;
    private boolean domainBusy;
    private volatile String latestStage8Json;
    private boolean stage8Busy;
    private volatile String latestStage26Json;
    private boolean stage26Busy;
    private volatile String latestStage32Json;
    private boolean stage32Busy;
    private Uri latestStage32SourceUri;
    private volatile String latestStage34Json;
    private boolean stage34Busy;
    private Uri latestStage34SidecarUri;
    private volatile String latestStage36Json;
    private boolean stage36Busy;
    private final ActivityResultLauncher<String[]> stage32DocumentPicker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) runStage32(uri);
            });

    private final ActivityResultLauncher<String[]> stage34SidecarPicker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) runStage34(uri);
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_hasselblad_development);
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.hasselblad_check_root), (view, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        MaterialToolbar toolbar = findViewById(R.id.hasselblad_check_toolbar);
        toolbar.setNavigationIcon(androidx.appcompat.R.drawable.abc_ic_ab_back_material);
        toolbar.setNavigationOnClickListener(view -> finish());
        findViewById(R.id.hasselblad_check_run).setOnClickListener(view -> runCheck());
        findViewById(R.id.hasselblad_check_copy).setOnClickListener(view -> {
            if (latestReport == null) return;
            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText("Hasselblad native development check",
                        latestReport.asText() + "\n" + HasselbladDevelopmentPolicy.captureSummary()
                                + "\n" + HasselbladCaptureSaveStatus.latest().display()));
                Toast.makeText(this, R.string.hasselblad_check_copied, Toast.LENGTH_SHORT).show();
            }
        });
        MaterialButton domainRun=findViewById(R.id.hasselblad_domain_run);
        domainRun.setOnClickListener(view -> runDomain());
        findViewById(R.id.hasselblad_domain_copy).setOnClickListener(view -> {
            JSONObject report=latestDomainReport;
            if (report==null) return;
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            if (clipboard!=null) {
                clipboard.setPrimaryClip(ClipData.newPlainText(
                        "Hasselblad Domain1 diagnostic JSON", report.toString()));
                Toast.makeText(this, "Domain1 JSON copied", Toast.LENGTH_SHORT).show();
            }
        });
        ((TextView)findViewById(R.id.hasselblad_domain_summary)).setText(
                "Domain1 has not run. Take one RAW photo first, then return here. "+
                "This check never changes saved colour.");
        findViewById(R.id.hasselblad_stage6_arm).setOnClickListener(view -> {
            HasselbladGpuStageProbe.arm();
            refreshStage6();
            Toast.makeText(this, "Stage6 armed for the next verified RAW+JPEG capture",
                    Toast.LENGTH_LONG).show();
        });
        findViewById(R.id.hasselblad_stage6_copy).setOnClickListener(view -> {
            try {
                JSONObject data=new JSONObject(HasselbladGpuStageProbe.latestJson());
                String status=data.optString("status");
                if (!"completed".equals(status) && !"skipped".equals(status)) return;
                ClipboardManager clipboard=getSystemService(ClipboardManager.class);
                if (clipboard!=null) {
                    clipboard.setPrimaryClip(ClipData.newPlainText(
                            "Hasselblad Stage6 GPU diagnostic JSON", data.toString()));
                    Toast.makeText(this,"Stage6 report copied",Toast.LENGTH_SHORT).show();
                }
            } catch (Exception ignored) {}
        });
        findViewById(R.id.hasselblad_stage8_run).setOnClickListener(view -> runStage8());
        findViewById(R.id.hasselblad_stage8_copy).setOnClickListener(view -> {
            String json=latestStage8Json;
            if (json==null) return;
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            if (clipboard!=null) {
                clipboard.setPrimaryClip(ClipData.newPlainText(
                        "Hasselblad Stage8 native profile preparation JSON",json));
                Toast.makeText(this,"Stage8 report copied",Toast.LENGTH_SHORT).show();
            }
        });
        findViewById(R.id.hasselblad_stage26_run).setOnClickListener(view -> runStage26());
        findViewById(R.id.hasselblad_stage26_copy).setOnClickListener(view -> {
            String json = latestStage26Json;
            if (json == null) return;
            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText(
                        "Hasselblad Stage26 neutral JNI synthetic diagnostic", json));
                Toast.makeText(this, "Stage26 JSON copied", Toast.LENGTH_SHORT).show();
            }
        });
        findViewById(R.id.hasselblad_stage32_pick).setOnClickListener(view -> {
            if (!stage32Busy) stage32DocumentPicker.launch(new String[]{"*/*"});
        });
        findViewById(R.id.hasselblad_stage32_copy).setOnClickListener(view -> {
            String json = latestStage32Json;
            if (json == null) return;
            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText(
                        "Hasselblad Stage32 picked DNG neutral tile diagnostic", json));
                Toast.makeText(this, "Stage32 report JSON copied", Toast.LENGTH_SHORT).show();
            }
        });
        findViewById(R.id.hasselblad_stage34_pick_sidecar).setOnClickListener(view -> {
            if (!stage32Busy && !stage34Busy && latestStage32SourceUri != null) {
                stage34SidecarPicker.launch(new String[]{"*/*"});
            }
        });
        findViewById(R.id.hasselblad_stage36_run).setOnClickListener(view -> runStage36());
        findViewById(R.id.hasselblad_stage36_copy).setOnClickListener(view -> {
            String json = latestStage36Json;
            if (json == null) return;
            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText(
                        "Hasselblad Stage36 original versus Photon neutral PCS tile", json));
                Toast.makeText(this, "Stage36 JSON copied", Toast.LENGTH_SHORT).show();
            }
        });
        findViewById(R.id.hasselblad_stage34_copy).setOnClickListener(view -> {
            String json = latestStage34Json;
            if (json == null) return;
            ClipboardManager clipboard = getSystemService(ClipboardManager.class);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText(
                        "Hasselblad Stage34 original versus saved DNG metadata provenance", json));
                Toast.makeText(this, "Stage34 report JSON copied", Toast.LENGTH_SHORT).show();
            }
        });
        refreshStage6();
        runCheck();
    }

    @Override protected void onResume() {
        super.onResume();
        if (findViewById(R.id.hasselblad_stage6_status) != null) refreshStage6();
    }
    private void refreshStage6() {
        ((TextView)findViewById(R.id.hasselblad_stage6_status))
                .setText(HasselbladGpuStageProbe.status());
        boolean copied = false;
        try {
            String state=new JSONObject(HasselbladGpuStageProbe.latestJson())
                    .optString("status");
            copied="completed".equals(state)||"skipped".equals(state);
        } catch (Exception ignored) {}
        findViewById(R.id.hasselblad_stage6_copy).setEnabled(copied);
        findViewById(R.id.hasselblad_stage6_arm)
                .setEnabled(!HasselbladGpuStageProbe.isArmed());
    }

    /** Synthetic LUT preparation only; never touches camera/RAW/rendering. */
    private void runStage8() {
        if(stage8Busy)return;
        stage8Busy=true;
        latestStage8Json=null;
        findViewById(R.id.hasselblad_stage8_run).setEnabled(false);
        findViewById(R.id.hasselblad_stage8_copy).setEnabled(false);
        ((TextView)findViewById(R.id.hasselblad_stage8_status)).setText(
                "Checking recorded X2D native fixture outputs and synthetic 6144-word profiles...");
        new Thread(() -> {
            final String result=HasselbladProfilePreparationCheck.run();
            runOnUiThread(() -> {
                if(isFinishing()||isDestroyed())return;
                latestStage8Json=result;
                stage8Busy=false;
                findViewById(R.id.hasselblad_stage8_run).setEnabled(true);
                findViewById(R.id.hasselblad_stage8_copy).setEnabled(true);
                boolean passed=false;
                try { passed="PASS".equals(new JSONObject(result).optString("status")); }
                catch (Exception ignored) { }
                ((TextView)findViewById(R.id.hasselblad_stage8_status)).setText(
                        (passed?"Stage8 PASS":"Stage8 NOT PASSED")
                        +" — original native fixture and full-size synthetic profile tests."
                        +"\nNo vendor camera LUT, photographic pixel renderer or calibrated AWB is enabled."
                        +"\nPhoton colour unchanged. Copy JSON for diagnostic details.");
            });
        },"HB-stage8-profile-on-demand").start();
    }

    /** Synthetic neutral PCS matrix test: no original MAIN processing or photo writes. */
    private void runStage26() {
        if (stage26Busy) return;
        stage26Busy = true;
        latestStage26Json = null;
        MaterialButton button = findViewById(R.id.hasselblad_stage26_run);
        button.setEnabled(false);
        findViewById(R.id.hasselblad_stage26_copy).setEnabled(false);
        ((TextView) findViewById(R.id.hasselblad_stage26_status)).setText(
                "Checking bounded Stage24 native linear colour tiles, without accessing photos...");
        new Thread(() -> {
            final String json = HasselbladColourReferenceCheck.run();
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                latestStage26Json = json;
                stage26Busy = false;
                button.setEnabled(true);
                findViewById(R.id.hasselblad_stage26_copy).setEnabled(true);
                boolean passed = false;
                try { passed = "PASS".equals(new JSONObject(json).optString("status")); }
                catch (Exception ignored) { }
                ((TextView) findViewById(R.id.hasselblad_stage26_status)).setText(
                        (passed ? "Stage26 PASS" : "Stage26 NOT PASSED")
                        + " — Stage24 colourimetry through Android JNI, synthetic pixels only."
                        + "\nNo Hasselblad MAIN CCM/gamma/LUT pixel parity; no HNCS look."
                        + "\nNo RAW photo read, saved JPEG change or WB calibration."
                        + "\nCopy JSON for timing, pass counts and scope.");
            });
        }, "HB-stage26-neutral-on-demand").start();
    }

    /**
     * Stage32 is entirely separate from camera capture/save. The system document
     * picker gives read access to ONE chosen DNG; only bounded local statistics
     * are reported, and private temporary bytes are deleted when finished.
     */
    private void runStage32(Uri uri) {
        if (stage32Busy || stage34Busy || stage36Busy) return;
        stage32Busy = true;
        latestStage32Json = null;
        latestStage32SourceUri = null;
        latestStage34Json = null;
        latestStage34SidecarUri = null;
        latestStage36Json = null;
        findViewById(R.id.hasselblad_stage36_run).setEnabled(false);
        findViewById(R.id.hasselblad_stage36_copy).setEnabled(false);
        ((TextView) findViewById(R.id.hasselblad_stage36_status))
                .setText("Stage36 not run. Re-select your matched DNG and capture JSON.");
        findViewById(R.id.hasselblad_stage34_pick_sidecar).setEnabled(false);
        findViewById(R.id.hasselblad_stage34_copy).setEnabled(false);
        ((TextView)findViewById(R.id.hasselblad_stage34_status)).setText(
                "Stage34: choose Stage32 DNG successfully, then its matching capture JSON.");
        MaterialButton pick = findViewById(R.id.hasselblad_stage32_pick);
        pick.setEnabled(false);
        findViewById(R.id.hasselblad_stage32_copy).setEnabled(false);
        ((TextView) findViewById(R.id.hasselblad_stage32_status)).setText(
                "Reading selected DNG in a bounded local worker; saved images remain untouched...");
        new Thread(() -> {
            final String report = HasselbladRealDngDiagnostic.inspect(
                    getApplicationContext(), uri);
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                stage32Busy = false;
                latestStage32Json = report;
                pick.setEnabled(true);
                findViewById(R.id.hasselblad_stage32_copy).setEnabled(true);
                String status = "INVALID_REPORT";
                try { status = new JSONObject(report).optString("status", "INVALID_REPORT"); }
                catch (Exception ignored) { }
                if ("PASS_REAL_DNG_NEUTRAL_CENTRE_TILE_ONLY".equals(status)) {
                    latestStage32SourceUri = uri;
                    findViewById(R.id.hasselblad_stage34_pick_sidecar).setEnabled(true);
                    ((TextView)findViewById(R.id.hasselblad_stage34_status)).setText(
                            "Stage34 ready: select the matching .capture.json saved with this DNG.");
                }
                ((TextView) findViewById(R.id.hasselblad_stage32_status)).setText(
                        "Stage32: " + status
                        + "\nA single 32 x 32 existing DNG centre tile; no original photo modified."
                        + "\nOnly a DNG-neutral PCS calculation when metadata and native bridge permit."
                        + "\nNeither Hasselblad HNCS nor original MAIN pixel equivalence is claimed."
                        + "\nCopy JSON for file hash, support checks and numerical statistics.");
            });
        }, "HB-stage32-user-picked-dng").start();
    }

    /**
     * Stage34 never mutates or auto-discovers a photo: it reopens the very same
     * user-picked DNG, and only the explicitly chosen matching capture sidecar.
     * A private hash comparison binds the two, then DNG AsShotNeutral is compared
     * with original Camera2 and Photon-effective neutral without exporting them.
     */
    private void runStage34(Uri sidecarUri) {
        if (stage34Busy || stage32Busy || stage36Busy
                || latestStage32SourceUri == null || latestStage32Json == null) return;
        stage34Busy = true;
        latestStage34Json = null;
        latestStage34SidecarUri = null;
        latestStage36Json = null;
        findViewById(R.id.hasselblad_stage36_run).setEnabled(false);
        findViewById(R.id.hasselblad_stage36_copy).setEnabled(false);
        ((TextView) findViewById(R.id.hasselblad_stage36_status))
                .setText("Stage36 requires a passed Stage34 re-bound DNG and capture sidecar.");
        final Uri dngUri = latestStage32SourceUri;
        final String stage32 = latestStage32Json;
        findViewById(R.id.hasselblad_stage32_pick).setEnabled(false);
        findViewById(R.id.hasselblad_stage34_pick_sidecar).setEnabled(false);
        findViewById(R.id.hasselblad_stage34_copy).setEnabled(false);
        ((TextView) findViewById(R.id.hasselblad_stage34_status)).setText(
                "Checking SHA-bound Camera2 capture record and DNG AsShotNeutral metadata...");
        new Thread(() -> {
            final String json = HasselbladDngWbProvenance34.verify(
                    getApplicationContext(), dngUri, sidecarUri, stage32);
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                latestStage34Json = json;
                stage34Busy = false;
                findViewById(R.id.hasselblad_stage32_pick).setEnabled(true);
                findViewById(R.id.hasselblad_stage34_pick_sidecar).setEnabled(true);
                findViewById(R.id.hasselblad_stage34_copy).setEnabled(true);
                String status = "NOT_PROVEN";
                String origin = "unknown";
                try {
                    JSONObject result = new JSONObject(json);
                    status = result.optString("status", status);
                    origin = result.optString("DNG_AsShotNeutral_origin", origin);
                } catch (Exception ignored) { }
                if ("PASS_RECORD_BINDING_AND_DNG_WB_TAG_INSPECTED".equals(status)) {
                    latestStage34SidecarUri = sidecarUri;
                    findViewById(R.id.hasselblad_stage36_run).setEnabled(true);
                    ((TextView) findViewById(R.id.hasselblad_stage36_status)).setText(
                            "Stage36 ready: run the two-neutral PCS comparison on the same DNG tile.");
                }
                ((TextView) findViewById(R.id.hasselblad_stage34_status)).setText(
                        "Stage34: " + status
                        + "\nDNG AsShotNeutral source: " + origin
                        + "\nOnly locally selected existing files were read."
                        + "\nSaved JPEG/DNG unchanged; this is not Hasselblad HNCS."
                        + "\nCopy the privacy-safe JSON for exact comparison flags.");
            });
        }, "HB-stage34-WB-provenance").start();
    }

    /**
     * Independent, explicitly requested Stage36 diagnostic on the exact same
     * DNG and sidecar previously selected for Stage32 and Stage34. Does not
     * hook, capture, alter, display or save a photograph.
     */
    private void runStage36() {
        if (stage36Busy || stage32Busy || stage34Busy
                || latestStage32SourceUri == null || latestStage34SidecarUri == null
                || latestStage32Json == null || latestStage34Json == null) return;
        stage36Busy = true;
        latestStage36Json = null;
        final Uri dngUri = latestStage32SourceUri;
        final Uri sidecarUri = latestStage34SidecarUri;
        final String stage32 = latestStage32Json, stage34 = latestStage34Json;
        findViewById(R.id.hasselblad_stage32_pick).setEnabled(false);
        findViewById(R.id.hasselblad_stage34_pick_sidecar).setEnabled(false);
        findViewById(R.id.hasselblad_stage36_run).setEnabled(false);
        findViewById(R.id.hasselblad_stage36_copy).setEnabled(false);
        ((TextView) findViewById(R.id.hasselblad_stage36_status)).setText(
                "Rechecking original RAW/frame provenance and computing two 1024-pixel native PCS tiles...");
        new Thread(() -> {
            final String report = HasselbladDualNeutralDiagnostic36.compare(
                    getApplicationContext(), dngUri, sidecarUri, stage32, stage34);
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                stage36Busy = false;
                latestStage36Json = report;
                findViewById(R.id.hasselblad_stage32_pick).setEnabled(true);
                findViewById(R.id.hasselblad_stage34_pick_sidecar).setEnabled(true);
                findViewById(R.id.hasselblad_stage36_run).setEnabled(true);
                findViewById(R.id.hasselblad_stage36_copy).setEnabled(true);
                String status = "NOT_PROVEN";
                try { status = new JSONObject(report).optString("status", status); }
                catch (Exception ignored) { }
                ((TextView) findViewById(R.id.hasselblad_stage36_status)).setText(
                        "Stage36: " + status
                        + "\nIdentical centre RAW samples and calibration; only Camera2 vs Photon neutral differs."
                        + "\nOutput: scene-linear sRGB differences, not perceptual colour error."
                        + "\nOriginal DNG/JPEG untouched; Hasselblad HNCS remains unimplemented."
                        + "\nCopy JSON for numeric differences and validity details.");
            });
        }, "HB-stage36-dual-neutral-on-demand").start();
    }

    private void runDomain() {
        if (domainBusy) return;
        domainBusy=true;
        latestDomainReport=null;
        MaterialButton button=findViewById(R.id.hasselblad_domain_run);
        button.setEnabled(false);
        findViewById(R.id.hasselblad_domain_copy).setEnabled(false);
        ((TextView)findViewById(R.id.hasselblad_domain_summary)).setText(
                "Evaluating the last verified physical sensor on a background thread...");
        new Thread(() -> {
            final JSONObject result=HasselbladDomainDiagnostics.evaluateLatest();
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                latestDomainReport=result;
                domainBusy=false;
                button.setEnabled(true);
                findViewById(R.id.hasselblad_domain_copy).setEnabled(true);
                ((TextView)findViewById(R.id.hasselblad_domain_summary))
                        .setText(HasselbladDomainDiagnostics.summary(result)+
                                "\nNo shipping white-balance policy; Photon renders all photos."+
                                "\nCopy the complete JSON to inspect valid/excluded points.");
            });
        }, "HB-domain-on-demand").start();
    }

    private void runCheck() {
        latestReport = HasselbladNativeCheck.run();
        ((TextView) findViewById(R.id.hasselblad_check_result)).setText(latestReport.summary());
        ((TextView) findViewById(R.id.hasselblad_check_policy)).setText(
                HasselbladDevelopmentPolicy.captureSummary());
        ((TextView) findViewById(R.id.hasselblad_check_provenance)).setText(latestReport.provenance);
        ((TextView) findViewById(R.id.hasselblad_check_details)).setText(latestReport.details);
        ((TextView) findViewById(R.id.hasselblad_check_capture_json)).setText(
                HasselbladCaptureSaveStatus.latest().display());
    }
}
