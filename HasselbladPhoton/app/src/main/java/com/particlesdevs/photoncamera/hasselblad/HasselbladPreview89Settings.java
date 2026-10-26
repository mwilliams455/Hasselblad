package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import java.io.IOException;

/** Preview preference only; never changes exposure, RAW, JPEG or sharpening settings. */
public final class HasselbladPreview89Settings {
    private HasselbladPreview89Settings() {}
    public static boolean enabled(Context c){return c!=null&&c.getSharedPreferences("hasselblad-preview89",Context.MODE_PRIVATE).getBoolean("enabled",true);}
    public static void setEnabled(Context c,boolean value)throws IOException {
        boolean committed=c.getSharedPreferences("hasselblad-preview89",Context.MODE_PRIVATE).edit().putBoolean("enabled",value).commit();
        // Android may update in-memory preferences even when disk commit fails.
        HasselbladPreview90Changes.changed();
        if(!committed)
            throw new IOException("Could not save preview setting");
    }
    public static HasselbladPreview89.Tone load(Context c)throws Exception {
        if(!enabled(c))return null;
        HasselbladProfile43 profile;HasselbladTone83 pack;
        synchronized(HasselbladLookStore84.class) {
            profile=HasselbladLookStore84.read(c);pack=HasselbladLookStore84.readPack(c);
        }
        return HasselbladPreview90Cache.get(profile,pack);
    }
}
