package com.particlesdevs.photoncamera.hasselblad;
import android.content.Context;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

/** Real settings, stream, scene renderer and JNI; RAW/demosaic remain Stage87 fixtures. */
public final class Stage91Check {
    static int checks,frames;
    static void ok(boolean value){if(!value)throw new AssertionError("Check "+checks);checks++;}
    interface Task{void run()throws Exception;}
    static void reject(Task task)throws Exception{try{task.run();}catch(IllegalArgumentException|IOException e){checks++;return;}throw new AssertionError("Expected rejection");}
    static short[] input(int w,int h){short[] data=new short[w*h*3];for(int i=0;i<data.length;i++)data[i]=(short)((i*73L+(i/7)*193L+17)&65535);return data;}
    static void write(Path path,short[] values)throws Exception{ByteBuffer b=ByteBuffer.allocate(values.length*2).order(ByteOrder.LITTLE_ENDIAN);b.asShortBuffer().put(values);Files.write(path,b.array());}
    static void settings()throws Exception {
        Context c=new Context();ok(!HasselbladSharpen87Settings.snapshot(c).enabled);
        var prefs=c.getSharedPreferences("hasselblad-sharpen87",0);
        prefs.edit().putBoolean("enabled",true).commit();var legacy=HasselbladSharpen87Settings.snapshot(c);
        ok(legacy.active()&&legacy.amount==100&&legacy.noise==0);
        HasselbladSharpen87Settings.setParameters(c,50,8);var shot=HasselbladSharpen87Settings.snapshot(c);
        HasselbladSharpen87Settings.setEnabled(c,false);var off=HasselbladSharpen87Settings.snapshot(c);
        ok(!off.active()&&off.amount==50&&off.noise==8&&shot.active());
        HasselbladSharpen87Settings.setEnabled(c,true);prefs.reload();
        ok(HasselbladSharpen87Settings.snapshot(c).encode().equals(shot.encode()));
        c.fail=true;c.failUpdatesMemory=true;
        reject(()->HasselbladSharpen87Settings.save(c,new HasselbladSharpen91(false,200,32)));
        ok(HasselbladSharpen87Settings.snapshot(c).encode().equals(shot.encode()));
        prefs.reload();ok(HasselbladSharpen87Settings.snapshot(c).encode().equals(shot.encode()));c.fail=false;
        HasselbladDiagnostics86.setEnabled(c,true);ok(HasselbladSharpen87Settings.snapshot(c).encode().equals(shot.encode()));
        for(int[] pair:new int[][]{{-1,0},{201,0},{0,-1},{100,33}})reject(()->HasselbladSharpen87Settings.setParameters(c,pair[0],pair[1]));
        ok(HasselbladSharpen87Settings.snapshot(c).encode().equals(shot.encode()));
        AtomicReference<Throwable> error=new AtomicReference<>();
        var a=new HasselbladSharpen91(true,25,2);var b=new HasselbladSharpen91(false,175,31);
        HasselbladSharpen87Settings.save(c,a);
        Thread writer=new Thread(()->{try{for(int i=0;i<200;i++)HasselbladSharpen87Settings.save(c,(i&1)==0?a:b);}catch(Throwable e){error.set(e);}});
        writer.start();for(int i=0;i<200;i++){String v=HasselbladSharpen87Settings.snapshot(c).encode();ok(v.equals(a.encode())||v.equals(b.encode()));}writer.join();ok(error.get()==null);
        for(String bad:new String[]{"", "1:2:100:0", "1:1:201:0", "1:1:100:33", "2:1:100:0", "1:1:xx:0"}){
            prefs.edit().putString("controls91",bad).commit();ok(!HasselbladSharpen87Settings.snapshot(c).active());
        }
    }
    static void stream(Path work,int w,int h,HasselbladSharpen91 selection,int band)throws Exception {
        short[] in=input(w,h),out=new short[in.length];int[] next={0};
        var s=new HasselbladSharpen86.Stream(w,h,selection,(y,n,pixels)->{ok(y==next[0]);next[0]+=n;System.arraycopy(pixels,0,out,y*w*3,pixels.length);});
        for(int y=0;y<h;y+=band){int n=Math.min(band,h-y);s.accept(y,n,Arrays.copyOfRange(in,y*w*3,(y+n)*w*3));}s.finish();ok(next[0]==h);
        String name=w+"_"+h+"_"+selection.amount+"_"+selection.noise+"_"+band;
        write(work.resolve(name+".actual.u16"),out);
        if(selection.amount==0)ok(Arrays.equals(in,out));frames++;
    }
    static int[] reference(HasselbladProfile43 p,HasselbladSharpen91 settings)throws Exception {
        int w=256,h=130;short[] raw=new short[w*h*3];
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)for(int c=0;c<3;c++)raw[(y*w+x)*3+c]=HasselbladFrame77.value(x,y,c);
        double[] m=HasselbladDngTileReader.identity(),ones={1,1,1};
        short[] colour=HasselbladRenderer42.render(raw,p.parameters(HasselbladRenderer42.cameraToD50(m,m,m,m,ones,ones)),p.gridAtTemperature(5000),p.curve,p.gridWidth,p.gridHeight,1);
        if(!settings.active())return HasselbladProfile43.srgb16ToArgb(p.finishRgb16(colour));
        short[] gradated=HasselbladRenderer42.defaultGradation(colour);int[] expected=new int[w*h];
        var stream=new HasselbladSharpen86.Stream(w,h,settings,(y,n,data)->{
            int[] argb=HasselbladProfile43.srgb16ToArgb(p.outputGradatedRgb16(data));System.arraycopy(argb,0,expected,y*w,argb.length);
        });
        for(int y=0;y<h;y+=7){int n=Math.min(7,h-y);stream.accept(y,n,Arrays.copyOfRange(gradated,y*w*3,(y+n)*w*3));}stream.finish();return expected;
    }
    static int[] scene(HasselbladProfile43 p,HasselbladSharpen91 selection)throws Exception {
        HasselbladDngTileReader.width=320;HasselbladDngTileReader.height=194;
        Context change=new Context();HasselbladSharpen87Settings.save(change,selection);
        var frozen=HasselbladSharpen87Settings.snapshot(change);int[] result=new int[256*130],next={0};
        var r=HasselbladSceneRenderer79.render(new File("fixture"),p,2,false,frozen,new HasselbladSceneRenderer79.Sink(){
            public void begin(int w,int h)throws IOException{ok(w==256&&h==130);HasselbladSharpen87Settings.save(change,new HasselbladSharpen91(!selection.enabled,200,32));}
            public void band(int y,int n,int w,int[] pixels){ok(y==next[0]);next[0]+=n;System.arraycopy(pixels,0,result,y*w,pixels.length);}
        });
        ok(next[0]==130&&r.sharpeningApplied==selection.active());
        ok(Arrays.equals(result,reference(p,selection)));ok(HasselbladSharpen87Settings.snapshot(change).enabled!=frozen.enabled);
        return result;
    }
    public static void main(String[] args)throws Exception {
        Path work=Path.of(args[0]);settings();
        for(int[] size:new int[][]{{1,1},{65,65},{256,130},{4032,130}})
            for(int[] pair:new int[][]{{0,0},{1,0},{50,0},{100,0},{150,0},{100,8},{100,32},{200,32}})
                for(int band:new int[]{1,7,64})stream(work,size[0],size[1],new HasselbladSharpen91(true,pair[0],pair[1]),band);
        short[] window=input(65,5);
        ok(Arrays.equals(HasselbladSharpen86.window(window,65,3),HasselbladSharpen86.window91(window,65,3,100,0)));
        for(int[] p:new int[][]{{-1,0},{201,0},{100,-1},{100,33}})reject(()->HasselbladSharpen86.window91(window,65,3,p[0],p[1]));
        reject(()->HasselbladSharpen86.window91(new short[4],65,3,100,0));
        try(InputStream in=Files.newInputStream(Path.of(args[1]))) {
            var profile=HasselbladProfile43.read(in);byte[] before=profile.encoded();
            int[] off=scene(profile,HasselbladSharpen91.OFF),normal=scene(profile,HasselbladSharpen91.DEFAULT);
            ok(Arrays.equals(off,scene(profile,new HasselbladSharpen91(true,0,32))));
            ok(Arrays.equals(off,scene(profile,new HasselbladSharpen91(false,200,32))));
            ok(Arrays.equals(normal,Stage87Check.reference(profile,256,130,true)));
            ok(!Arrays.equals(normal,scene(profile,new HasselbladSharpen91(true,50,0))));
            ok(!Arrays.equals(normal,scene(profile,new HasselbladSharpen91(true,150,0))));
            ok(!Arrays.equals(normal,scene(profile,new HasselbladSharpen91(true,100,32))));
            ok(Arrays.equals(before,profile.encoded()));
        }
        Files.writeString(work.resolve("STAGE91_JAVA.json"),"{\"checks\":"+checks+",\"stream_frames\":"+frames+"}\n");
    }
}
