package com.particlesdevs.photoncamera.hasselblad;

import java.io.IOException;

/** Reconstructs camera RGB from a controlled HAL preview, then uses the JPEG colour/finishing code. */
public final class HasselbladPreview92 {
    public static final int SIDE=33,WIDTH=SIDE*SIDE,HEIGHT=SIDE;
    private HasselbladPreview92(){}
    public static final class Input {
        final double[] inverse, gains, camera, normalization;
        final float[][] curves;
        final double exposure;
        public final int kelvin;
        public Input(double[] transform,double[] gains,float[][] curves,double[] camera,
                     double[] normalization,double exposure,int kelvin)throws IOException {
            check(transform,9);check(gains,3);check(camera,9);check(normalization,3);
            if(!Double.isFinite(exposure)||exposure<1./64||exposure>64||kelvin<2000||kelvin>10000)
                throw new IOException("Preview exposure or illuminant unavailable");
            for(int i=0;i<3;i++)if(gains[i]<=0||normalization[i]<=0||normalization[i]>2)
                throw new IOException("Invalid preview gain");
            if(curves==null||curves.length!=3)throw new IOException("Missing HAL tone curves");
            this.curves=new float[3][];
            for(int c=0;c<3;c++) {
                float[] a=curves[c];
                if(a==null||a.length<4||a.length>2048||a.length%2!=0)throw new IOException("Invalid HAL curve shape");
                for(int i=0;i<a.length;i++)if(!Float.isFinite(a[i])||a[i]<0||a[i]>1)throw new IOException("Invalid HAL curve value");
                if(a[0]!=0||a[1]!=0||a[a.length-2]!=1||a[a.length-1]!=1)throw new IOException("Unsupported HAL curve endpoints");
                for(int i=2;i<a.length;i+=2)if(a[i]<=a[i-2]||a[i+1]<=a[i-1])throw new IOException("HAL curve is not invertible");
                this.curves[c]=a.clone();
            }
            inverse=inverse(transform);this.gains=gains.clone();this.camera=camera.clone();
            this.normalization=normalization.clone();this.exposure=exposure;this.kelvin=kelvin;
        }
    }
    public static final class Cube {
        private final byte[] bytes;
        public final int film,kelvin;
        Cube(byte[] bytes,int film,int kelvin){this.bytes=bytes;this.film=film;this.kelvin=kelvin;}
        public byte[] texture(){return bytes.clone();}
    }
    private static void check(double[] a,int n)throws IOException {
        if(a==null||a.length!=n)throw new IOException("Missing preview colour metadata");
        for(double v:a)if(!Double.isFinite(v)||Math.abs(v)>10000)throw new IOException("Invalid preview colour metadata");
    }
    static double[] inverse(double[] a)throws IOException {
        double[] b={a[4]*a[8]-a[5]*a[7],a[2]*a[7]-a[1]*a[8],a[1]*a[5]-a[2]*a[4],
            a[5]*a[6]-a[3]*a[8],a[0]*a[8]-a[2]*a[6],a[2]*a[3]-a[0]*a[5],
            a[3]*a[7]-a[4]*a[6],a[1]*a[6]-a[0]*a[7],a[0]*a[4]-a[1]*a[3]};
        double d=a[0]*b[0]+a[1]*b[3]+a[2]*b[6];
        if(!Double.isFinite(d)||Math.abs(d)<1e-7)throw new IOException("Singular HAL colour matrix");
        for(int i=0;i<9;i++){b[i]/=d;if(!Double.isFinite(b[i])||Math.abs(b[i])>100)throw new IOException("Unstable HAL colour inverse");}return b;
    }
    static double undoCurve(float[] curve,double value) {
        int upper=2;while(upper<curve.length-2&&curve[upper+1]<value)upper+=2;
        int lower=upper-2;double t=(value-curve[lower+1])/(curve[upper+1]-curve[lower+1]);
        return curve[lower]+Math.max(0,Math.min(1,t))*(curve[upper]-curve[lower]);
    }
    static short[] cameraRgb(Input in,double[] display)throws IOException {
        if(display.length%3!=0)throw new IOException("Invalid RGB input");
        short[] raw=new short[display.length];
        for(int j=0;j<display.length;j+=3) {
            double r=undoCurve(in.curves[0],display[j]),g=undoCurve(in.curves[1],display[j+1]),b=undoCurve(in.curves[2],display[j+2]);
            for(int c=0;c<3;c++) {
                double v=(in.inverse[3*c]*r+in.inverse[3*c+1]*g+in.inverse[3*c+2]*b)/in.gains[c];
                v*=in.normalization[c]*in.exposure;
                raw[j+c]=(short)(int)(Math.max(0,Math.min(1,v))*65535.);
            }
        }return raw;
    }
    public static Cube build(HasselbladProfile43 profile,Input input)throws IOException {
        if(!profile.hasAutomaticIlluminant||!profile.hasNativeFinishing)throw new IOException("Automatic colour profile required");
        if(Thread.currentThread().isInterrupted())throw new IOException("Preview cancelled");
        double[] display=new double[SIDE*SIDE*SIDE*3];
        for(int g=0;g<SIDE;g++)for(int b=0;b<SIDE;b++)for(int r=0;r<SIDE;r++) {
            int i=((g*WIDTH)+(b*SIDE+r))*3;display[i]=r/(double)(SIDE-1);display[i+1]=g/(double)(SIDE-1);display[i+2]=b/(double)(SIDE-1);
        }
        short[] raw=cameraRgb(input,display);
        short[] colour=HasselbladRenderer42.render(raw,profile.parameters(input.camera),profile.gridAtTemperature(input.kelvin),profile.curve,profile.gridWidth,profile.gridHeight,1);
        int[] output=HasselbladProfile43.srgb16ToArgb(profile.finishRgb16(colour));
        byte[] rgba=new byte[output.length*4];
        for(int i=0;i<output.length;i++){rgba[4*i]=(byte)(output[i]>>>16);rgba[4*i+1]=(byte)(output[i]>>>8);rgba[4*i+2]=(byte)output[i];rgba[4*i+3]=(byte)255;}
        if(Thread.currentThread().isInterrupted())throw new IOException("Preview cancelled");
        return new Cube(rgba,profile.film,input.kelvin);
    }
}
