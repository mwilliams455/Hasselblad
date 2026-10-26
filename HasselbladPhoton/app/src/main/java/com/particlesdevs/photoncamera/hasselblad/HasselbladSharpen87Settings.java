package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import java.io.IOException;

/** Optional JPEG sharpening; independent of the imported look and diagnostics. */
public final class HasselbladSharpen87Settings {
    private HasselbladSharpen87Settings() {}
    public static synchronized HasselbladSharpen91 snapshot(Context context) {
        if(context==null)return HasselbladSharpen91.OFF;
        var prefs=context.getSharedPreferences("hasselblad-sharpen87",Context.MODE_PRIVATE);
        try {
            String saved=prefs.getString("controls91",null);
            if(saved!=null)return HasselbladSharpen91.decode(saved);
            return new HasselbladSharpen91(prefs.getBoolean("enabled",false),100,0);
        }catch(IllegalArgumentException|ClassCastException invalid){return HasselbladSharpen91.OFF;}
    }
    public static boolean enabled(Context context){return snapshot(context).enabled;}
    public static synchronized void setEnabled(Context context,boolean enabled)throws IOException {
        var old=snapshot(context);save(context,new HasselbladSharpen91(enabled,old.amount,old.noise));
    }
    public static synchronized void setParameters(Context context,int amount,int noise)throws IOException {
        save(context,new HasselbladSharpen91(snapshot(context).enabled,amount,noise));
    }
    public static synchronized void save(Context context,HasselbladSharpen91 value)throws IOException {
        if(context==null||value==null)throw new IOException("Sharpening settings unavailable");
        var prefs=context.getSharedPreferences("hasselblad-sharpen87",Context.MODE_PRIVATE);
        String previous=snapshot(context).encode();
        // One value prevents mixed tuples; Android commit updates memory even on disk failure.
        if(!prefs.edit().putString("controls91",value.encode()).commit()) {
            prefs.edit().putString("controls91",previous).commit();
            throw new IOException("Could not save sharpening settings; previous selection restored in memory");
        }
    }
}
