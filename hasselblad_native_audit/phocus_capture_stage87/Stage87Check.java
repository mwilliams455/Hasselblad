package com.particlesdevs.photoncamera.hasselblad;
import android.content.Context;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public final class Stage87Check {
    static int checks,frames;static long pixels;
    interface Task {void run()throws Exception;}
    static void ok(boolean b){if(!b)throw new AssertionError("Check "+checks);checks++;}
    static void rejected(Task t)throws Exception {try{t.run();}catch(IOException expected){checks++;return;}throw new AssertionError("Expected failure");}
    static final class Output implements HasselbladSceneRenderer79.Sink {
        int[] pixels;int next,w;boolean cancel,fail;Context toggle;
        public void begin(int width,int height)throws IOException {
            w=width;pixels=new int[width*height];
            if(toggle!=null)HasselbladSharpen87Settings.setEnabled(toggle,false);
        }
        public void band(int y,int rows,int width,int[] argb)throws IOException {
            if(fail)throw new IOException("Injected sink failure");
            if(y!=next||width!=w||argb.length!=rows*w)throw new AssertionError("Band shape/order");
            System.arraycopy(argb,0,pixels,y*w,argb.length);next+=rows;
            if(cancel)Thread.currentThread().interrupt();
        }
    }
    static int[] reference(HasselbladProfile43 p,int w,int h,boolean sharp)throws Exception {
        short[] rgb=new short[w*h*3];
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)for(int c=0;c<3;c++)rgb[(y*w+x)*3+c]=HasselbladFrame77.value(x,y,c);
        double[] m=HasselbladDngTileReader.identity(),ones={1,1,1};
        double[] camera=HasselbladRenderer42.cameraToD50(m,m,m,m,ones,ones);
        short[] colour=HasselbladRenderer42.render(rgb,p.parameters(camera),p.gridAtTemperature(5000),p.curve,p.gridWidth,p.gridHeight,1);
        if(!sharp)return HasselbladProfile43.srgb16ToArgb(p.finishRgb16(colour));
        short[] gradation=HasselbladRenderer42.defaultGradation(colour);int[] result=new int[w*h];
        // Same already-phone-validated comparison sequence, independently partitioned into 7-row bands.
        HasselbladSharpen86.Stream stream=new HasselbladSharpen86.Stream(w,h,(y,n,out)->{
            int[] argb=HasselbladProfile43.srgb16ToArgb(p.outputGradatedRgb16(out));System.arraycopy(argb,0,result,y*w,argb.length);
        });
        try{for(int y=0;y<h;y+=7){int n=Math.min(7,h-y);stream.accept(y,n,Arrays.copyOfRange(gradation,y*w*3,(y+n)*w*3));}stream.finish();}
        finally{stream.abort();}
        return result;
    }
    static void compare(HasselbladProfile43 p,int w,int h,boolean sharp,boolean diagnostics)throws Exception {
        HasselbladDngTileReader.width=w+64;HasselbladDngTileReader.height=h+64;
        HasselbladDngTileReader.checks=0;HasselbladDngTileReader.reads=0;HasselbladFrame77.calls=0;
        byte[] encoded=p.encoded();Output out=new Output();Context context=new Context();
        if(sharp){HasselbladSharpen87Settings.setEnabled(context,true);out.toggle=context;}
        var r=HasselbladSceneRenderer79.render(new File("fixture"),p,2,diagnostics,HasselbladSharpen87Settings.enabled(context),out);
        ok(Arrays.equals(reference(p,w,h,sharp),out.pixels));ok(out.next==h);
        ok(!sharp||!Arrays.equals(reference(p,w,h,false),out.pixels));
        ok(r.sharpeningApplied==sharp&&r.kelvin==5000&&r.orientation==6);
        ok(HasselbladDngTileReader.reads==1&&HasselbladFrame77.calls==(h+63)/64);
        ok(HasselbladDngTileReader.checks==(diagnostics?1:0));
        ok(diagnostics?!r.samples.isEmpty():r.samples.isEmpty());
        ok(Arrays.equals(encoded,p.encoded()));ok(!HasselbladSharpen87Settings.enabled(context));
        frames++;pixels+=(long)w*h;
    }
    public static void main(String[] args)throws Exception {
        Context c=new Context();ok(!HasselbladSharpen87Settings.enabled(c)&&!HasselbladSharpen87Settings.enabled(null));
        HasselbladDiagnostics86.setEnabled(c,true);ok(!HasselbladSharpen87Settings.enabled(c));
        HasselbladSharpen87Settings.setEnabled(c,true);HasselbladDiagnostics86.setEnabled(c,false);
        ok(HasselbladSharpen87Settings.enabled(c)&&!HasselbladDiagnostics86.enabled(c));
        c.fail=true;rejected(()->HasselbladSharpen87Settings.setEnabled(c,false));ok(HasselbladSharpen87Settings.enabled(c));
        c.fail=false;HasselbladSharpen87Settings.setEnabled(c,false);ok(!HasselbladSharpen87Settings.enabled(c));
        int profiles=0;HasselbladProfile43 first=null;
        for(int i=1;i<args.length;i++)try(InputStream in=Files.newInputStream(Path.of(args[i]))) {
            HasselbladProfile43 p=HasselbladProfile43.read(in);if(first==null)first=p;profiles++;
            for(int[] size:new int[][]{{65,65},{256,192},{4032,130}})for(boolean sharp:new boolean[]{false,true})
                compare(p,size[0],size[1],sharp,false);
            compare(p,256,192,true,true);compare(p,256,192,false,true);
        }
        if(first==null)throw new AssertionError("No test profile");
        final HasselbladProfile43 profile=first;
        for(boolean sharp:new boolean[]{false,true}) {
            Output cancel=new Output();cancel.cancel=true;
            rejected(()->HasselbladSceneRenderer79.render(new File("fixture"),profile,1,false,sharp,cancel));ok(Thread.interrupted());
            Output failure=new Output();failure.fail=true;
            rejected(()->HasselbladSceneRenderer79.render(new File("fixture"),profile,1,false,sharp,failure));
        }
        Output legacy=new Output();var old=HasselbladSceneRenderer79.render(new File("fixture"),profile,1,false,legacy);
        ok(!old.sharpeningApplied&&Arrays.equals(legacy.pixels,reference(profile,256,192,false)));
        String result="{\"status\":\"PASS_CAPTURE_FINISHING\",\"checks\":"+checks+",\"frames\":"+frames+",\"argb_pixels_compared\":"+pixels+",\"max_abs_difference\":0,\"profiles_checked\":"+profiles+",\"default_off\":true,\"independent_preferences\":true,\"setting_changes_do_not_change_inflight_render\":true,\"diagnostics_do_not_change_pixels\":true,\"cancellation_and_sink_failures_propagate\":true,\"demosaic_is_test_adapter\":true,\"device_tested\":false}";
        Files.writeString(Path.of(args[0],"STAGE87_HOST_VALIDATION.json"),result+"\n");System.out.println(result);
    }
}
