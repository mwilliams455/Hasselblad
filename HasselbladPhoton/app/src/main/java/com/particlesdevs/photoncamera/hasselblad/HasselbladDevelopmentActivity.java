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
import com.particlesdevs.photoncamera.R;
import com.particlesdevs.photoncamera.app.base.BaseActivity;

/** An explicit native-development check; it never accesses or modifies a photo. */
public final class HasselbladDevelopmentActivity extends BaseActivity {
    private HasselbladNativeCheck.Report latestReport;

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
        runCheck();
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
