package com.particlesdevs.photoncamera.hasselblad;
/** Select exactly the Stage76 preview sites before the pointwise colour transform. */
public final class HasselbladPreview77 {
    private HasselbladPreview77() {}
    private static int first(int y,int step){return (step-y%step)%step;}
    public static short[] sample(short[] rgb,int width,int y,int rows,int step) {
        if(width<1||rows<1||y<0||step<1||rgb.length!=(long)width*rows*3)throw new IllegalArgumentException("Invalid preview band");
        int first=first(y,step),count=first>=rows?0:1+(rows-1-first)/step,pw=(width+step-1)/step;
        short[] out=new short[pw*count*3];int i=0;
        for(int row=first;row<rows;row+=step)for(int x=0;x<width;x+=step) {
            int src=(row*width+x)*3;out[i++]=rgb[src];out[i++]=rgb[src+1];out[i++]=rgb[src+2];
        }
        return out;
    }
    public static void place(int[] pixels,int[] target,int width,int y,int rows,int step) {
        if(width<1||rows<1||y<0||step<1)throw new IllegalArgumentException("Invalid preview placement");
        int first=first(y,step),count=first>=rows?0:1+(rows-1-first)/step,pw=(width+step-1)/step;
        if(pixels.length!=count*pw)throw new IllegalArgumentException("Preview size mismatch");
        if(count!=0)System.arraycopy(pixels,0,target,((y+first)/step)*pw,pixels.length);
    }
}
