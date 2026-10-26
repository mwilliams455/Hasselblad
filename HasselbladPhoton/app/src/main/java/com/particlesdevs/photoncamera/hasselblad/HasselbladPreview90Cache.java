package com.particlesdevs.photoncamera.hasselblad;

import java.util.LinkedHashMap;
import java.util.Map;
import java.io.IOException;

/** Three immutable tone tables, keyed by complete profile AND pack contents. */
public final class HasselbladPreview90Cache {
    private static final int LIMIT=3;
    private static final Map<String,HasselbladPreview89.Tone> tables=new LinkedHashMap<>(4,.75f,true);
    private HasselbladPreview90Cache() {}
    public static HasselbladPreview89.Tone get(HasselbladProfile43 profile,HasselbladTone83 pack)throws Exception {
        // A same-film import or a changed no-film reference must not hit an old table.
        pack.validateProfile(profile);
        String key=HasselbladLook84.sha256(profile.encoded())+":"+HasselbladLook84.sha256(pack.encoded());
        if(Thread.currentThread().isInterrupted())throw new IOException("Preview load cancelled");
        synchronized(tables){HasselbladPreview89.Tone old=tables.get(key);if(old!=null)return old;}
        HasselbladPreview89.Tone built=HasselbladPreview89.build(profile,pack);
        if(Thread.currentThread().isInterrupted())throw new IOException("Preview load cancelled");
        synchronized(tables){
            HasselbladPreview89.Tone old=tables.get(key);if(old!=null)return old;
            tables.put(key,built);
            if(tables.size()>LIMIT)tables.remove(tables.keySet().iterator().next());
        }
        return built;
    }
}
