package com.particlesdevs.photoncamera.hasselblad;

import java.io.IOException;
import java.util.Arrays;

/** Display-domain tone guide, not a RAW colour transform or calibrated JPEG preview. */
public final class HasselbladPreview89 {
    public static final int SIZE = 1024;
    private HasselbladPreview89() {}

    public static final class Tone {
        public final int film;
        private final byte[] rgba;
        private Tone(int film, byte[] rgba) { this.film=film; this.rgba=rgba; }
        public byte[] texture() { return rgba.clone(); }
    }

    public static Tone build(HasselbladProfile43 profile, HasselbladTone83 pack) throws IOException {
        pack.validateProfile(profile);
        if (Thread.currentThread().isInterrupted()) throw new IOException("Preview preparation cancelled");
        // Curve 7 contains the required companding. An identity RAW ramp would
        // apply that encoding twice to the already display-encoded camera feed.
        short[] reference = neutral(pack.curve(7));
        short[] selected = neutral(profile.curve);
        float[] base = luminance(profile.finishRgb16(reference));
        float[] target = luminance(profile.finishRgb16(selected));
        if (Thread.currentThread().isInterrupted()) throw new IOException("Preview preparation cancelled");
        return new Tone(profile.film, relativeTable(base, target));
    }

    private static short[] neutral(float[] curve) throws IOException {
        short[] rgb = new short[65536*3];
        float previous = -1;
        for (int i=0;i<65536;i++) {
            float value=curve[i];
            if (!Float.isFinite(value)||value<previous||value<0||value>65535)
                throw new IOException("Preview needs a monotonic tone curve");
            previous=value;
            // Same truncation as hb42_render's film lookup.
            Arrays.fill(rgb,3*i,3*i+3,(short)(int)value);
        }
        return rgb;
    }

    static double decode(double v) { return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4); }
    static double encode(double v) { return v<=.0031308?v*12.92:1.055*Math.pow(v,1/2.4)-.055; }
    private static float[] luminance(short[] rgb) {
        float[] out=new float[rgb.length/3];
        for(int i=0;i<out.length;i++) out[i]=(float)encode(
                .2126*decode((rgb[3*i]&65535)/65535.)+
                .7152*decode((rgb[3*i+1]&65535)/65535.)+
                .0722*decode((rgb[3*i+2]&65535)/65535.));
        return out;
    }

    /** F(selected)(inverse(F(no-film))(display Y)); common finishing is not reapplied. */
    static byte[] relativeTable(float[] base,float[] target) throws IOException {
        if(base.length!=target.length||base.length<2)throw new IOException("Invalid preview ramps");
        for(int i=0;i<base.length;i++) {
            if(!Float.isFinite(base[i])||!Float.isFinite(target[i])||base[i]<0||base[i]>1||target[i]<0||target[i]>1||
                    (i>0&&(base[i]<base[i-1]||target[i]<target[i-1])))
                throw new IOException("Unsupported preview response");
        }
        if(base[base.length-1]-base[0]<.9)throw new IOException("Preview reference range is too small");
        byte[] out=new byte[SIZE*4];
        int upper=1;
        boolean identity=Arrays.equals(base,target);
        for(int i=0;i<SIZE;i++) {
            double x=i/(double)(SIZE-1),y;
            while(upper<base.length-1&&base[upper]<x)upper++;
            if(identity)y=x;
            else if(x<=base[0])y=target[0];
            else if(x>=base[base.length-1])y=target[target.length-1];
            else {
                int lower=upper-1;
                double span=base[upper]-base[lower];
                y=span>0?target[lower]+(target[upper]-target[lower])*(x-base[lower])/span:target[upper];
            }
            int code=(int)Math.round(Math.max(0,Math.min(1,y))*65535);
            out[4*i]=(byte)(code>>>8);out[4*i+1]=(byte)code;out[4*i+3]=(byte)255;
        }
        return out;
    }
}
