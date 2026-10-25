package com.particlesdevs.photoncamera.hasselblad;

import java.io.IOException;
import java.util.Arrays;

/** Bounded full-resolution SDR sharpening; receives RGB16 after default gradation. */
public final class HasselbladSharpen86 {
    static {System.loadLibrary("hbsharp86");}
    private HasselbladSharpen86() {}
    // The window contains one real neighbour row above/below the requested rows.
    static native short[] window(short[] gradated, int width, int rows);
    public interface Sink {void band(int y,int rows,short[] rgb16)throws IOException;}
    public static final class Stream {
        private final int width,height;
        private final Sink sink;
        private short[] pending,previous;
        private int pendingY,pendingRows,received;
        private boolean ended;
        public Stream(int width,int height,Sink sink) {
            if(width<1||width>8192||height<1||height>8192||(long)width*height>16777216||sink==null)
                throw new IllegalArgumentException("Invalid sharpening dimensions");
            this.width=width;this.height=height;this.sink=sink;
        }
        private void check()throws IOException {
            if(ended)throw new IOException("Sharpening stream already closed");
            if(Thread.currentThread().isInterrupted()){abort();throw new IOException("Render cancelled");}
        }
        public void accept(int y,int rows,short[] input)throws IOException {
            check();
            if(y!=received||rows<1||rows>64||rows>height-y||input==null||input.length!=width*rows*3)
                throw new IOException("Unexpected sharpening band");
            try {
                if(pending!=null)emit(input);
                pending=input.clone();pendingY=y;pendingRows=rows;received+=rows;
            }catch(IOException|RuntimeException|Error e){abort();throw e;}
        }
        private void emit(short[] next)throws IOException {
            int stride=width*3;
            short[] window=new short[(pendingRows+2)*stride];
            System.arraycopy(previous==null?pending:previous,0,window,0,stride);
            System.arraycopy(pending,0,window,stride,pending.length);
            System.arraycopy(next==null?pending:next,next==null?pending.length-stride:0,
                    window,window.length-stride,stride);
            short[] output=HasselbladSharpen86.window(window,width,pendingRows);
            if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
            sink.band(pendingY,pendingRows,output);
            previous=Arrays.copyOfRange(pending,pending.length-stride,pending.length);
        }
        public void finish()throws IOException {
            check();if(received!=height)throw new IOException("Incomplete sharpening frame");
            try{emit(null);}finally{abort();}
        }
        public void abort(){ended=true;pending=null;previous=null;}
    }
}
