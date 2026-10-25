package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import java.io.IOException;

/** Optional JPEG sharpening; independent of the imported look and diagnostics. */
public final class HasselbladSharpen87Settings {
    private HasselbladSharpen87Settings() {}
    public static boolean enabled(Context context) {
        return context!=null&&context.getSharedPreferences("hasselblad-sharpen87",Context.MODE_PRIVATE)
                .getBoolean("enabled",false);
    }
    public static void setEnabled(Context context,boolean enabled)throws IOException {
        if(!context.getSharedPreferences("hasselblad-sharpen87",Context.MODE_PRIVATE).edit()
                .putBoolean("enabled",enabled).commit())throw new IOException("Could not save sharpening setting");
    }
}
