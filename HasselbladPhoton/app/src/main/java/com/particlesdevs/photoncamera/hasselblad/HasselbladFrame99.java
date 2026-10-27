package com.particlesdevs.photoncamera.hasselblad;
import java.io.IOException;
import java.util.HashMap;
/** Bounded chroma correction over cached, unchanged Stage97 source RGB bands. */
public final class HasselbladFrame99 {
    static {System.loadLibrary("hbfringe99");}
    private HasselbladFrame99() {}
    public static native int filterNative(short[] rgb,byte[] rawFlags,int width,int height,short[] out,double nr,double nb);
    public static final class Stream {
        private final short[] prepared;
        private final int rw,rh,width,height,workers;
        private final double[] neutral;
        private final HashMap<Integer,short[]> cache=new HashMap<>();
        private int nextY;
        private boolean closed;
        public Stream(short[] raw,int rawWidth,int rawHeight,int workerCount,double[] n)throws IOException {
            if(rawWidth<128||rawWidth>8192||rawHeight<128||rawHeight>8192||raw==null||
               (long)rawWidth*rawHeight>16777216L||raw.length!=(long)rawWidth*rawHeight||workerCount<1||workerCount>4||n==null||n.length!=3)
                throw new IOException("Invalid fringe input");
            for(double v:n)if(!Double.isFinite(v)||v<=0)throw new IOException("Invalid RAW neutral");
            double nr=n[0]/n[1],nb=n[2]/n[1];
            if(!Double.isFinite(nr)||!Double.isFinite(nb)||nr<.0625||nr>16||nb<.0625||nb>16)throw new IOException("Unsupported RAW neutral");
            prepared=raw;rw=rawWidth;rh=rawHeight;width=HasselbladFrame97.width(rw);height=HasselbladFrame97.width(rh);workers=workerCount;neutral=n.clone();
        }
        public short[] band(int y)throws IOException {
            if(closed||y!=nextY||y>=height)throw new IOException("Out-of-order fringe band");
            if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
            int rows=Math.min(64,height-y),hw=width+30,hh=rows+30;
            short[] halo=new short[hw*hh*3],out=new short[width*rows*3];byte[] flags=new byte[hw*hh];
            int first=Math.max(0,y-15)/64*64;
            cache.keySet().removeIf(key->key<first);
            for(int yy=0;yy<hh;yy++){
                int sy=Math.max(0,Math.min(height-1,y+yy-15)),key=sy/64*64;
                short[] band=cache.get(key);
                if(band==null){band=HasselbladFrame97.band(prepared,rw,rh,key,workers,neutral);cache.put(key,band);}
                for(int xx=0;xx<hw;xx++){
                    int sx=Math.max(0,Math.min(width-1,xx-15)),i=yy*hw+xx;
                    System.arraycopy(band,((sy-key)*width+sx)*3,halo,i*3,3);
                    int value=prepared[(y+yy+17)*rw+xx+17]&65535;
                    flags[i]=(byte)(value==0?1:value==65535?2:0);
                }
            }
            int code=filterNative(halo,flags,hw,hh,out,neutral[0]/neutral[1],neutral[2]/neutral[1]);
            if(code!=0)throw new IOException("Fringe band rejected: "+code);
            if(Thread.currentThread().isInterrupted())throw new IOException("Render cancelled");
            nextY+=rows;return out;
        }
        public void abort(){closed=true;cache.clear();}
    }
}
