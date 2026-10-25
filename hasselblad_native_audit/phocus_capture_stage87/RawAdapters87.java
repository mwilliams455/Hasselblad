package com.particlesdevs.photoncamera.hasselblad;
/** Explicit RAW/demosaic adapters: these tests exercise finishing integration only. */
class HasselbladDngTileReader {
    static int checks,reads,width=320,height=256;
    static double[] identity(){return new double[]{1,0,0,0,1,0,0,0,1};}
    static class Ill {String error;double[] colorMatrix1=identity(),colorMatrix2=identity();int light1=17,light2=21;}
    static class Meta {
        int width=HasselbladDngTileReader.width,height=HasselbladDngTileReader.height,gainMapCount=0;
        Ill illuminant=new Ill();double[] forwardMatrix1=identity(),forwardMatrix2=identity(),calibration1=identity(),calibration2=identity(),analogBalance={1,1,1},asShotNeutral={1,1,1};
    }
    static class Frame {Meta metadata=new Meta();int orientation=6;long belowBlack,atWhite,gainClips;short[] bayer=new short[width*height];}
    static class Prepared {Frame frame=new Frame();}
    static Prepared readPrepared78(java.io.File f){reads++;return new Prepared();}
    static int validatePrepared78(java.io.File f,Frame p){checks++;return 49152;}
}
class HasselbladFrame77 {
    static int calls;
    static int width(int raw){return raw-64;}
    static short value(int x,int y,int c){return (short)((x*71+y*127+c*4013+((x/9+y/11)%2)*18000)&65535);}
    static short[] band(short[] b,int w,int h,int y,int workers){
        calls++;int width=w-64,rows=Math.min(64,h-64-y);short[] out=new short[width*rows*3];
        for(int row=0;row<rows;row++)for(int x=0;x<width;x++)for(int c=0;c<3;c++)out[(row*width+x)*3+c]=value(x,y+row,c);
        return out;
    }
}
class HasselbladIlluminant56 {
    static class Selection {int lutKelvin=5000;}
    static Selection estimate(double[] a,double[] b,int c,int d,double[] e,double[] f,double[] g,double[] h){return new Selection();}
}
