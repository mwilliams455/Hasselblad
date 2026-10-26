package com.particlesdevs.photoncamera.hasselblad;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** One running calculation plus one replaceable pending calculation. No unbounded frame queue. */
public final class HasselbladPreview92Worker<T> implements AutoCloseable {
    public interface Work<T>{T run() throws Exception;}
    public interface Sink<T>{void accept(T value,Throwable error);}
    private final ExecutorService executor=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"HB-preview92");t.setDaemon(true);return t;});
    private long epoch;
    private boolean running,closed;
    private Job<T> pending;
    private static final class Job<T> {
        final long epoch;final Work<T> work;final Sink<T> sink;
        Job(long epoch,Work<T> work,Sink<T> sink){this.epoch=epoch;this.work=work;this.sink=sink;}
    }
    public synchronized void invalidate(){epoch++;pending=null;}
    public synchronized void offer(Work<T> work,Sink<T> sink){
        if(closed)return;pending=new Job<>(epoch,work,sink);
        if(!running){running=true;executor.execute(this::drain);}
    }
    private void drain(){
        while(true){
            Job<T> job;
            synchronized(this){job=pending;pending=null;if(job==null||closed){running=false;return;}}
            T value=null;Throwable error=null;
            try{value=job.work.run();}catch(Exception|LinkageError|OutOfMemoryError e){error=e;}
            // The owner also validates its session/revision inside the sink: invalidation may race delivery.
            boolean deliver;synchronized(this){deliver=!closed&&job.epoch==epoch;}
            if(deliver)job.sink.accept(value,error);
        }
    }
    @Override public synchronized void close(){closed=true;invalidate();executor.shutdownNow();}
}
