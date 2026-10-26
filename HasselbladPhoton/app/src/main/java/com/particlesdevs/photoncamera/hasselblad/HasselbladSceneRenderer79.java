package com.particlesdevs.photoncamera.hasselblad;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** Headless automatic-colour path extracted from Stage78; no Android/UI dependencies. */
public final class HasselbladSceneRenderer79 {
    private HasselbladSceneRenderer79() {}
    public interface Sink {
        void begin(int width, int height) throws IOException;
        void band(int y, int rows, int width, int[] argb) throws IOException;
    }
    public static final class Sample {
        public final int sensorX, sensorY;
        public final short[] bayer, rgb;
        Sample(int x, int y, short[] bayer, short[] rgb) {
            sensorX=x; sensorY=y; this.bayer=bayer; this.rgb=rgb;
        }
    }
    public static final class Result {
        public int rawWidth, rawHeight, width, height, orientation, kelvin, checkedSites, workers;
        public long preparationNs, referenceNs, demosaicNs, colourNs, belowBlack, atWhite, gainClips;
        public int gainMaps;
        public boolean sharpeningApplied;
        public final List<Sample> samples=new ArrayList<>();
    }
    private static void interrupted() throws IOException {
        if (Thread.currentThread().isInterrupted()) throw new IOException("Capture cancelled");
    }
    public static Result render(File dng, HasselbladProfile43 profile, int workers, Sink sink) throws IOException {
        return render(dng,profile,workers,true,sink);
    }
    public static Result render(File dng,HasselbladProfile43 profile,int workers,boolean diagnostics,Sink sink)throws IOException {
        return render(dng,profile,workers,diagnostics,false,sink);
    }
    public static Result render(File dng,HasselbladProfile43 profile,int workers,boolean diagnostics,boolean sharpening,Sink sink)throws IOException {
        return render(dng,profile,workers,diagnostics,sharpening?HasselbladSharpen91.DEFAULT:HasselbladSharpen91.OFF,sink);
    }
    public static Result render(File dng,HasselbladProfile43 profile,int workers,boolean diagnostics,HasselbladSharpen91 sharpening,Sink sink)throws IOException {
        interrupted();
        if(sharpening==null)throw new IOException("Missing sharpening settings");
        if (!profile.hasAutomaticIlluminant || !profile.hasNativeFinishing)
            throw new IOException("Import the Stage56 automatic .hbc profile on Saved DNG colour first.");
        if (workers<1 || workers>4) throw new IOException("Invalid renderer worker count");
        Result r=new Result(); r.workers=workers;
        long t=System.nanoTime();
        var prepared=HasselbladDngTileReader.readPrepared78(dng).frame;
        r.preparationNs=System.nanoTime()-t; t=System.nanoTime();
        r.checkedSites=diagnostics?HasselbladDngTileReader.validatePrepared78(dng,prepared):0;
        r.referenceNs=System.nanoTime()-t;
        var m=prepared.metadata;
        r.rawWidth=m.width; r.rawHeight=m.height;
        r.width=HasselbladFrame77.width(m.width); r.height=HasselbladFrame77.width(m.height);
        r.orientation=prepared.orientation;
        r.belowBlack=prepared.belowBlack; r.atWhite=prepared.atWhite; r.gainClips=prepared.gainClips; r.gainMaps=m.gainMapCount;
        if (m.illuminant.error!=null) throw new IOException("Automatic LUT unavailable: "+m.illuminant.error);
        var selection=HasselbladIlluminant56.estimate(m.illuminant.colorMatrix1,m.illuminant.colorMatrix2,
                m.illuminant.light1,m.illuminant.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        r.kelvin=selection.lutKelvin;
        double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,
                m.calibration2,m.analogBalance,m.asShotNeutral);
        double[] params=profile.parameters(camera), grid=profile.gridAtTemperature(r.kelvin);
        interrupted(); sink.begin(r.width,r.height);
        int middle=((r.height/2)/64)*64, last=((r.height-64)/64)*64;
        HasselbladSharpen86.Stream sharp=sharpening.active()?new HasselbladSharpen86.Stream(r.width,r.height,sharpening,(y,rows,gradated)->{
            interrupted();
            sink.band(y,rows,r.width,HasselbladProfile43.srgb16ToArgb(profile.outputGradatedRgb16(gradated)));
        }):null;
        try {
            for (int y=0;y<r.height;y+=64) {
                interrupted(); t=System.nanoTime();
                short[] rgb=HasselbladFrame77.band(prepared.bayer,m.width,m.height,y,workers);
                r.demosaicNs+=System.nanoTime()-t;
                int rows=Math.min(64,r.height-y);
                if (diagnostics && rows==64 && (y==0 || y==middle || y==last)) {
                    int tile=r.width>=256?256:64;
                    int x=Math.max(0,Math.min(r.width-64,((r.width/2)/tile)*tile-16))&~1;
                    short[] input=new short[128*128], out=new short[64*64*3];
                    for(int yy=0;yy<128;yy++) System.arraycopy(prepared.bayer,(y+yy)*m.width+x,input,yy*128,128);
                    for(int yy=0;yy<64;yy++) System.arraycopy(rgb,(yy*r.width+x)*3,out,yy*64*3,64*3);
                    r.samples.add(new Sample(x+32,y+32,input,out));
                }
                t=System.nanoTime();
                short[] colour=HasselbladRenderer42.render(rgb,params,grid,profile.curve,
                        profile.gridWidth,profile.gridHeight,1);
                interrupted();
                if(sharp==null) {
                    short[] automatic=profile.finishRgb16(colour);
                    sink.band(y,rows,r.width,HasselbladProfile43.srgb16ToArgb(automatic));
                } else sharp.accept(y,rows,HasselbladRenderer42.defaultGradation(colour));
                r.colourNs+=System.nanoTime()-t;
            }
            if(sharp!=null) {
                t=System.nanoTime();sharp.finish();r.colourNs+=System.nanoTime()-t;
                r.sharpeningApplied=true;
            }
        }finally{if(sharp!=null)sharp.abort();}
        interrupted(); return r;
    }
}
