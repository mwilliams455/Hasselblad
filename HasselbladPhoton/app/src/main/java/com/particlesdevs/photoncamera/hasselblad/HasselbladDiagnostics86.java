package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import java.io.IOException;

/** Explicit opt-in for capture probes, cached comparisons and public capture JSON. */
public final class HasselbladDiagnostics86 {
    private HasselbladDiagnostics86() {}
    public static boolean enabled(Context context) {
        return context!=null&&context.getSharedPreferences("hasselblad-capture86",Context.MODE_PRIVATE)
                .getBoolean("diagnostics",false);
    }
    public static void setEnabled(Context context,boolean enabled)throws IOException {
        if(!context.getSharedPreferences("hasselblad-capture86",Context.MODE_PRIVATE).edit()
                .putBoolean("diagnostics",enabled).commit())throw new IOException("Could not save diagnostic setting");
    }
}
