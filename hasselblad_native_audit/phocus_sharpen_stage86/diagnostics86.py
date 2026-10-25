"""JVM adapters exercise the real diagnostic preference and renderer branch."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONTEXT='''package android.content;
public final class Context {
 public static final int MODE_PRIVATE=0; public final Prefs prefs=new Prefs();
 public Prefs getSharedPreferences(String name,int mode){return prefs;}
 public static final class Prefs {
  public boolean value,fail;public boolean getBoolean(String key,boolean fallback){return value;}
  public Editor edit(){return new Editor(this);}
 }
 public static final class Editor {
  private final Prefs p;private boolean pending;Editor(Prefs p){this.p=p;}
  public Editor putBoolean(String key,boolean value){pending=value;return this;}
  public boolean commit(){if(p.fail)return false;p.value=pending;return true;}
 }
}
'''
STUBS='''package com.particlesdevs.photoncamera.hasselblad;
class HasselbladDngTileReader {
 static int checks;
 static class Ill {String error;double[] colorMatrix1,colorMatrix2;int light1,light2;}
 static class Meta {int width=320,height=256,gainMapCount=0;Ill illuminant=new Ill();double[] forwardMatrix1,forwardMatrix2,calibration1,calibration2,analogBalance,asShotNeutral;}
 static class Frame {Meta metadata=new Meta();int orientation=1;long belowBlack,atWhite,gainClips;short[] bayer=new short[320*256];}
 static class Prepared {Frame frame=new Frame();}
 static Prepared readPrepared78(java.io.File f){return new Prepared();}
 static int validatePrepared78(java.io.File f,Frame p){checks++;return 49152;}
}
class HasselbladFrame77 {
 static int width(int raw){return raw-64;}
 static short[] band(short[] b,int w,int h,int y,int workers){int width=w-64,rows=Math.min(64,h-64-y);short[] out=new short[width*rows*3];for(int i=0;i<out.length;i++)out[i]=(short)(i+y*width*3);return out;}
}
class HasselbladIlluminant56 {
 static class Selection {int lutKelvin=5000;}
 static Selection estimate(double[] a,double[] b,int c,int d,double[] e,double[] f,double[] g,double[] h){return new Selection();}
}
class HasselbladRenderer42 {
 static double[] cameraToD50(double[] a,double[] b,double[] c,double[] d,double[] e,double[] f){return new double[9];}
 static short[] render(short[] rgb,double[] p,double[] g,float[] c,int w,int h,int owner){return rgb;}
}
class HasselbladProfile43 {
 boolean hasAutomaticIlluminant=true,hasNativeFinishing=true;float[] curve=new float[65536];int gridWidth=2,gridHeight=2;
 double[] parameters(double[] camera){return new double[38];}
 double[] gridAtTemperature(int kelvin){return new double[8];}
 short[] finishRgb16(short[] input){return input;}
 static int[] srgb16ToArgb(short[] input){int[] out=new int[input.length/3];for(int i=0;i<out.length;i++)out[i]=input[3*i]&65535;return out;}
}
'''
CHECK='''package com.particlesdevs.photoncamera.hasselblad;
import android.content.Context;import java.io.*;import java.util.*;
public final class Diagnostics86Check {
 public static void main(String[] args)throws Exception {
  Context c=new Context();if(HasselbladDiagnostics86.enabled(c)||HasselbladDiagnostics86.enabled(null))throw new AssertionError();
  HasselbladDiagnostics86.setEnabled(c,true);if(!HasselbladDiagnostics86.enabled(c))throw new AssertionError();
  c.prefs.fail=true;try{HasselbladDiagnostics86.setEnabled(c,false);throw new AssertionError();}catch(IOException expected){}
  if(!HasselbladDiagnostics86.enabled(c))throw new AssertionError();c.prefs.fail=false;
  HasselbladDiagnostics86.setEnabled(c,false);if(HasselbladDiagnostics86.enabled(c))throw new AssertionError();
  List<Integer> off=new ArrayList<>(),on=new ArrayList<>();
  var no=HasselbladSceneRenderer79.render(new File("fixture"),new HasselbladProfile43(),1,false,sink(off));
  if(HasselbladDngTileReader.checks!=0||no.checkedSites!=0||!no.samples.isEmpty())throw new AssertionError();
  var yes=HasselbladSceneRenderer79.render(new File("fixture"),new HasselbladProfile43(),1,true,sink(on));
  if(HasselbladDngTileReader.checks!=1||yes.checkedSites!=49152||yes.samples.size()!=3)throw new AssertionError();
  if(!off.equals(on)||off.size()!=256*192)throw new AssertionError();
  System.out.println("{\\"status\\":\\"PASS_DIAGNOSTICS_ADAPTERS\\",\\"default_off\\":true,\\"failed_preference_write_rejected\\":true,\\"off_skips_reference_probe_and_samples\\":true,\\"adapter_pixels_identical\\":49152,\\"android_storage_tested\\":false}");
 }
 static HasselbladSceneRenderer79.Sink sink(List<Integer> pixels){return new HasselbladSceneRenderer79.Sink(){
  public void begin(int w,int h){}public void band(int y,int rows,int w,int[] argb){if(y*w!=pixels.size())throw new AssertionError();for(int p:argb)pixels.add(p);}
 };}
}
'''
def check(work,compiler):
 dest=work/'diagnostic-adapters';dest.mkdir(exist_ok=True);classes=dest/'classes';classes.mkdir(exist_ok=True)
 for name,text in [('Context.java',CONTEXT),('Stubs.java',STUBS),('Diagnostics86Check.java',CHECK)]: (dest/name).write_text(text)
 java=ROOT/'HasselbladPhoton/app/src/main/java/com/particlesdevs/photoncamera/hasselblad'
 sources=[dest/n for n in ('Context.java','Stubs.java','Diagnostics86Check.java')]+[java/n for n in ('HasselbladDiagnostics86.java','HasselbladSceneRenderer79.java')]
 subprocess.run(compiler+['--release','17','-d',str(classes),*map(str,sources)],check=True)
 return json.loads(subprocess.check_output(['java','-cp',str(classes),'com.particlesdevs.photoncamera.hasselblad.Diagnostics86Check'],text=True))
