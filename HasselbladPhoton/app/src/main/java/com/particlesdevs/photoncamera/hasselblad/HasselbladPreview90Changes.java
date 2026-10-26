package com.particlesdevs.photoncamera.hasselblad;

import java.util.concurrent.CopyOnWriteArraySet;
import java.util.concurrent.atomic.AtomicLong;

/** Process-local invalidation for committed profile, tone-pack and preview changes. */
public final class HasselbladPreview90Changes {
    private static final AtomicLong revision=new AtomicLong();
    private static final CopyOnWriteArraySet<Runnable> listeners=new CopyOnWriteArraySet<>();
    private HasselbladPreview90Changes() {}
    public static long revision(){return revision.get();}
    static void subscribe(Runnable listener){listeners.add(listener);}
    static void unsubscribe(Runnable listener){listeners.remove(listener);}
    public static void changed(){
        revision.incrementAndGet();
        for(Runnable listener:listeners)try{listener.run();}catch(RuntimeException ignored){/* A preview cannot prevent a saved setting. */}
    }
}
