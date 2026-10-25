package com.particlesdevs.photoncamera.hasselblad;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

public final class Stage86Check {
    static int checks;
    interface Task{void run()throws Exception;}
    static void ok(boolean b){if(!b)throw new AssertionError();checks++;}
    static void reject(Task t)throws Exception{try{t.run();}catch(IOException|IllegalArgumentException e){checks++;return;}throw new AssertionError("Malformed stream accepted");}
    static short[] read(Path p)throws IOException{byte[] b=Files.readAllBytes(p);short[] s=new short[b.length/2];ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(s);return s;}
    public static void main(String[] args)throws Exception {
        Path work=Path.of(args[0]);int frames=0;long channels=0;
        for(String line:Files.readAllLines(work.resolve("cases.txt"))) {
            String[] v=line.split(" ");int w=Integer.parseInt(v[1]),h=Integer.parseInt(v[2]);
            short[] source=read(work.resolve(v[0]+".input")),expected=read(work.resolve(v[0]+".expected"));
            for(int chunk:new int[]{1,7,63,64}) {
                short[] actual=new short[source.length];int[] next={0};
                HasselbladSharpen86.Stream stream=new HasselbladSharpen86.Stream(w,h,(y,rows,out)->{
                    if(y!=next[0])throw new IOException("Output reordered");next[0]+=rows;System.arraycopy(out,0,actual,y*w*3,out.length);});
                for(int y=0;y<h;y+=chunk){int rows=Math.min(chunk,h-y);short[] band=Arrays.copyOfRange(source,y*w*3,(y+rows)*w*3);
                    stream.accept(y,rows,band);Arrays.fill(band,(short)999);}
                stream.finish();ok(next[0]==h);ok(Arrays.equals(expected,actual));
                reject(()->stream.finish());reject(()->stream.accept(0,1,new short[w*3]));
                frames++;channels+=source.length;
            }
        }
        reject(()->HasselbladSharpen86.window(null,1,1));
        reject(()->HasselbladSharpen86.window(new short[9],0,1));
        reject(()->HasselbladSharpen86.window(new short[9],8193,1));
        reject(()->HasselbladSharpen86.window(new short[9],1,65));
        reject(()->HasselbladSharpen86.window(new short[8],1,1));
        reject(()->new HasselbladSharpen86.Stream(0,1,(y,n,s)->{}));
        reject(()->new HasselbladSharpen86.Stream(8192,8192,(y,n,s)->{}));
        HasselbladSharpen86.Stream bad=new HasselbladSharpen86.Stream(8,2,(y,n,s)->{});
        reject(bad::finish);reject(()->bad.accept(1,1,new short[24]));reject(()->bad.accept(0,3,new short[72]));
        reject(()->bad.accept(0,1,new short[23]));bad.accept(0,1,new short[24]);
        Thread.currentThread().interrupt();reject(()->bad.accept(1,1,new short[24]));ok(Thread.interrupted());reject(bad::finish);
        HasselbladSharpen86.Stream failed=new HasselbladSharpen86.Stream(8,2,(y,n,s)->{throw new IOException("Injected sink failure");});
        failed.accept(0,1,new short[24]);reject(()->failed.accept(1,1,new short[24]));reject(failed::finish);
        HasselbladProfile43 profile;
        try(InputStream in=Files.newInputStream(work.resolve("synthetic.hbc"))){profile=HasselbladProfile43.read(in);}
        Random random=new Random(86);short[] rgb=new short[4096*3];for(int i=0;i<rgb.length;i++)rgb[i]=(short)random.nextInt(65536);
        ok(Arrays.equals(profile.finishRgb16(rgb),profile.outputGradatedRgb16(HasselbladRenderer42.defaultGradation(rgb))));
        int privateProfiles=0;
        for(int i=1;i<args.length;i++)try(InputStream in=Files.newInputStream(Path.of(args[i]))) {
            HasselbladProfile43 p=HasselbladProfile43.read(in);byte[] bytes=p.encoded();
            ok(Arrays.equals(p.finishRgb16(rgb),p.outputGradatedRgb16(HasselbladRenderer42.defaultGradation(rgb))));
            ok(Arrays.equals(bytes,p.encoded()));privateProfiles++;
        }
        String result="{\"status\":\"PASS_JNI_STREAMING\",\"checks\":"+checks+",\"partitioned_frames\":"+frames+
            ",\"rgb16_channels_compared\":"+channels+",\"max_abs_difference\":0,\"private_profiles_checked\":"+privateProfiles+"}";
        Files.writeString(work.resolve("STAGE86_JNI_VALIDATION.json"),result+"\n");System.out.println(result);
    }
}
