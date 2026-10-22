package com.particlesdevs.photoncamera.hasselblad;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.Toast;

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
