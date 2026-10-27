package com.particlesdevs.photoncamera.hasselblad;
import java.io.IOException;
import java.util.Arrays;
public final class Frame99Check {
 static void require(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
  int cases=0,max=0;
  for(int rw:new int[]{128,130,318,642})for(int rh:new int[]{128,130,194}){
   int w=HasselbladFrame97.width(rw),h=HasselbladFrame97.width(rh);short[] raw=new short[rw*rh];double[] n={.337,1,.639};
   for(int y=0;y<rh;y++)for(int x=0;x<rw;x++){
    int ch=(y%2==0&&x%2==0)?0:(y%2==1&&x%2==1)?2:1;
    double v=(Math.sin(x*.71+y*.39)>.1?33000:1600)*(1+.03*Math.sin(x*.27+ch));
    raw[y*rw+x]=(short)(v*n[ch]);
   }
   raw[63*rw+65]=0;raw[96*rw+70]=(short)65535;
   short[] copy=raw.clone(),whole=new short[w*h*3];
   for(int y=0;y<h;y+=64){short[] b=HasselbladFrame97.band(raw,rw,rh,y,1,n);System.arraycopy(b,0,whole,y*w*3,b.length);}
   int hw=w+30,hh=h+30;short[] halo=new short[hw*hh*3],expected=new short[w*h*3];byte[] flags=new byte[hw*hh];
   for(int y=0;y<hh;y++)for(int x=0;x<hw;x++){
    int sx=Math.max(0,Math.min(w-1,x-15)),sy=Math.max(0,Math.min(h-1,y-15)),i=y*hw+x;
    System.arraycopy(whole,(sy*w+sx)*3,halo,i*3,3);int v=raw[(y+17)*rw+x+17]&65535;flags[i]=(byte)(v==0?1:v==65535?2:0);
   }
   require(HasselbladFrame99.filterNative(halo,flags,hw,hh,expected,n[0],n[2])==0);
   for(int workers:new int[]{1,4}){
    HasselbladFrame99.Stream stream=new HasselbladFrame99.Stream(raw,rw,rh,workers,n);
    for(int y=0;y<h;y+=64){short[] got=stream.band(y);for(int i=0;i<got.length;i++){int d=Math.abs((got[i]&65535)-(expected[y*w*3+i]&65535));max=Math.max(max,d);require(d<=1);}}
    stream.abort();try{stream.band(0);throw new AssertionError();}catch(IOException good){}
   }
   require(Arrays.equals(raw,copy));cases++;
  }
  short[] raw=new short[128*130];HasselbladFrame99.Stream stream=new HasselbladFrame99.Stream(raw,128,130,1,new double[]{1,1,1});
  try{stream.band(64);throw new AssertionError();}catch(IOException good){}
  Thread.currentThread().interrupt();try{stream.band(0);throw new AssertionError();}catch(IOException good){}finally{Thread.interrupted();}
  for(double[] bad:new double[][]{null,{}, {0,1,1},{Double.NaN,1,1},{1,0,1},{1,1,32}})try{new HasselbladFrame99.Stream(raw,128,130,1,bad);throw new AssertionError();}catch(IOException good){}
  short[] rgb=new short[31*31*3],out=new short[]{123,123,123};byte[] flags=new byte[31*31];
  require(HasselbladFrame99.filterNative(rgb,flags,31,31,out,Double.NaN,1)==-2);require(out[0]==123&&out[1]==123&&out[2]==123);
  require(HasselbladFrame99.filterNative(rgb,flags,31,31,rgb,1,1)==-1);
  System.out.println("PASS Stage99 Java/JNI: "+cases+" dimensions, workers, full-image/stream seams and tails, cancellation; max error "+max);
 }
}
