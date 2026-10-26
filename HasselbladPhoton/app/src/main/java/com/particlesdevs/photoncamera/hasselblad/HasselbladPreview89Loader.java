package com.particlesdevs.photoncamera.hasselblad;

import java.util.concurrent.*;
import java.util.function.Consumer;

/** One worker and at most one pending load. Only the latest request may publish. */
public final class HasselbladPreview89Loader {
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,10,TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(1),task->{Thread t=new Thread(task,"HB89-preview");t.setDaemon(true);return t;},
            new ThreadPoolExecutor.DiscardOldestPolicy());
    private long generation;
    private Future<?> pending;
    public HasselbladPreview89Loader(){worker.allowCoreThreadTimeOut(true);}
    public synchronized void load(Callable<HasselbladPreview89.Tone> source,Consumer<HasselbladPreview89.Tone> sink) {
        cancel();final long token=generation;
        sink.accept(null); // Never retain the previous profile while loading a different one.
        pending=worker.submit(()->{
            HasselbladPreview89.Tone tone=null;
            try{tone=source.call();}catch(Exception|LinkageError ignored){/* Original feed remains usable. */}
            synchronized(this){if(token==generation&&!Thread.currentThread().isInterrupted())sink.accept(tone);}
        });
    }
    public synchronized void cancel(){generation++;if(pending!=null){pending.cancel(true);pending=null;}worker.getQueue().clear();}
    public synchronized void close(){cancel();worker.shutdownNow();}
}
