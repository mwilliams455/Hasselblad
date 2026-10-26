package com.particlesdevs.photoncamera.hasselblad;

import java.util.concurrent.Callable;
import java.util.function.Consumer;

/** Live subscription independent of Activity recreation; never publishes an older tone. */
public final class HasselbladPreview90Controller implements AutoCloseable {
    public static final class Frame {
        private static final Frame EMPTY=new Frame(null,-1);
        private final HasselbladPreview89.Tone tone;
        private final long revision;
        private Frame(HasselbladPreview89.Tone tone,long revision){this.tone=tone;this.revision=revision;}
        public static Frame empty(){return EMPTY;}
        public HasselbladPreview89.Tone currentTone(){
            return revision==HasselbladPreview90Changes.revision()?tone:null;
        }
    }
    private final HasselbladPreview89Loader loader=new HasselbladPreview89Loader();
    private final Callable<HasselbladPreview89.Tone> source;
    private final Consumer<Frame> sink;
    private final Runnable listener=this::refresh;
    private volatile boolean active;
    private boolean closed;
    public HasselbladPreview90Controller(Callable<HasselbladPreview89.Tone> source,Consumer<Frame> sink){
        this.source=source;this.sink=sink;
    }
    public synchronized void start(){
        if(closed||active)return;
        active=true;HasselbladPreview90Changes.subscribe(listener);refresh();
    }
    private synchronized void refresh(){
        if(!active||closed)return;
        final long revision=HasselbladPreview90Changes.revision();
        loader.load(source,tone->{
            // Do not take this controller's lock while the loader holds its lock.
            if(active&&revision==HasselbladPreview90Changes.revision())sink.accept(new Frame(tone,revision));
        });
    }
    public synchronized void stop(){
        active=false;HasselbladPreview90Changes.unsubscribe(listener);loader.cancel();sink.accept(Frame.empty());
    }
    @Override public synchronized void close(){if(!closed){stop();closed=true;loader.close();}}
}
