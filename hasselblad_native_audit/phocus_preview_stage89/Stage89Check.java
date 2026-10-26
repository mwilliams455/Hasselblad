package com.particlesdevs.photoncamera.hasselblad;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import android.content.Context;

public final class Stage89Check {
    static int checks;
    static void check(boolean yes,String why){checks++;if(!yes)throw new AssertionError(why);}
    interface Task{void run()throws Exception;}
    static void reject(Task task)throws Exception{try{task.run();throw new AssertionError("accepted invalid input");}catch(IOException expected){checks++;}}
    static int code(byte[] b,int i){return (b[4*i]&255)*256+(b[4*i+1]&255);}
    public static void main(String[] args)throws Exception {
        Path work=Path.of(args[0]);float[] base=new float[65536],target=new float[65536];
        for(int i=0;i<base.length;i++){base[i]=i/65535f;target[i]=base[i]*base[i];}
        byte[] identity=HasselbladPreview89.relativeTable(base,base),dark=HasselbladPreview89.relativeTable(base,target);
        for(int i=0;i<1024;i++){
            check(Math.abs(code(identity,i)-Math.round(i*65535./1023))==0,"identity");
            check(Math.abs(code(dark,i)-Math.round(Math.pow(i/1023.,2)*65535))<=1,"analytic dark response");
        }
        reject(()->HasselbladPreview89.relativeTable(new float[]{0,Float.NaN,1},new float[]{0,.5f,1}));
        reject(()->HasselbladPreview89.relativeTable(new float[]{0,.7f,.6f,1},new float[]{0,.3f,.6f,1}));
        reject(()->HasselbladPreview89.relativeTable(new float[]{0,.2f},new float[]{0,1}));
        byte[] plateau=HasselbladPreview89.relativeTable(new float[]{0,.5f,.5f,1},new float[]{0,.2f,.3f,1});
        for(int i=1;i<1024;i++)check(code(plateau,i)>=code(plateau,i-1),"plateau response monotonic");

        Context context=new Context();
        check(HasselbladPreview89Settings.enabled(context),"preview default enabled");
        check(!HasselbladSharpen87Settings.enabled(context),"sharpening stays off");
        check(!HasselbladDiagnostics86.enabled(context),"diagnostics stay off");
        HasselbladPreview89Settings.setEnabled(context,false);
        check(!HasselbladPreview89Settings.enabled(context),"preview off persisted");
        check(HasselbladPreview89Settings.load(context)==null,"off does not read profile");
        HasselbladSharpen87Settings.setEnabled(context,true);
        check(!HasselbladPreview89Settings.enabled(context),"sharp independent");
        context.fail=true;reject(()->HasselbladPreview89Settings.setEnabled(context,true));context.fail=false;
        HasselbladPreview89Settings.setEnabled(context,true);
        check(HasselbladSharpen87Settings.enabled(context),"preview leaves sharpening alone");

        List<HasselbladPreview89.Tone> tones=new ArrayList<>();
        for(int i=1;i<args.length;i+=2){
            HasselbladProfile43 p;HasselbladTone83 pack;
            try(InputStream in=Files.newInputStream(Path.of(args[i]))){p=HasselbladProfile43.read(in);}
            try(InputStream in=Files.newInputStream(Path.of(args[i+1]))){pack=HasselbladTone83.read(in);}
            byte[] before=p.encoded();float[] curve=p.curve.clone();
            HasselbladPreview89.Tone tone=HasselbladPreview89.build(p,pack);tones.add(tone);
            byte[] table=tone.texture();check(table.length==4096,"texture size");
            check(Arrays.equals(before,p.encoded())&&Arrays.equals(curve,p.curve),"profile unchanged");
            for(int j=1;j<1024;j++)check(code(table,j)>=code(table,j-1),"profile tone monotonic");
            byte first=table[0];table[0]++;check(tone.texture()[0]==first,"defensive texture");
            Files.write(work.resolve("tone-"+tones.size()+".rgba"),tone.texture());
            p.curve[1]=Float.NaN;reject(()->HasselbladPreview89.build(p,pack));
            System.out.println("PROFILE "+tones.size()+" film="+tone.film+" table_mid="+code(tone.texture(),512));
        }
        HasselbladPreview89.Tone a=tones.get(0),b=tones.get(tones.size()-1);
        HasselbladPreview89Loader loader=new HasselbladPreview89Loader();
        List<HasselbladPreview89.Tone> delivered=Collections.synchronizedList(new ArrayList<>());
        CountDownLatch started=new CountDownLatch(1),release=new CountDownLatch(1),latest=new CountDownLatch(1);
        loader.load(()->{started.countDown();for(;;)try{release.await();break;}catch(InterruptedException ignored){}return a;},delivered::add);
        check(started.await(3,TimeUnit.SECONDS),"worker started");
        loader.load(()->b,t->{delivered.add(t);if(t!=null)latest.countDown();});release.countDown();
        check(latest.await(3,TimeUnit.SECONDS),"latest published");
        check(delivered.size()==3&&delivered.get(0)==null&&delivered.get(1)==null&&delivered.get(2)==b,"stale load suppressed");
        CountDownLatch bad=new CountDownLatch(2);AtomicBoolean wrong=new AtomicBoolean();
        loader.load(()->{throw new IOException("missing pack");},t->{if(t!=null)wrong.set(true);bad.countDown();});
        check(bad.await(3,TimeUnit.SECONDS)&&!wrong.get(),"missing profile falls back");
        CountDownLatch block=new CountDownLatch(1),begun=new CountDownLatch(1),finished=new CountDownLatch(1);
        AtomicInteger count=new AtomicInteger();
        loader.load(()->{begun.countDown();try{block.await();}finally{finished.countDown();}return a;},t->count.incrementAndGet());
        check(begun.await(3,TimeUnit.SECONDS),"cancellable load started");loader.cancel();block.countDown();
        check(finished.await(3,TimeUnit.SECONDS)&&count.get()==1,"pause suppresses late table");loader.close();
        Files.writeString(work.resolve("java89.json"),"{\"checks\":"+checks+",\"profiles\":"+tones.size()+",\"status\":\"PASS\"}\n");
        System.out.println("PASS Stage89 "+checks+" checks");
    }
}
