package com.particlesdevs.photoncamera.hasselblad;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.BooleanSupplier;

/** Actual store/settings/controller/cache and JNI; Android storage uses fault-injection adapters. */
public final class Stage90Check {
    static int checks,switches,profiles;
    static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
    interface Task{void run()throws Exception;}
    static void reject(Task f)throws Exception{try{f.run();throw new AssertionError("Expected rejection");}catch(IOException expected){checks++;}}
    static void await(BooleanSupplier ready,String why)throws Exception{
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(6);
        while(!ready.getAsBoolean()&&System.nanoTime()<deadline)Thread.sleep(2);
        check(ready.getAsBoolean(),why);
    }
    static byte[] seal(byte[] data)throws Exception{
        MessageDigest sha=MessageDigest.getInstance("SHA-256");sha.update(data,0,data.length-32);
        System.arraycopy(sha.digest(),0,data,data.length-32,32);return data;
    }
    static HasselbladProfile43 profile(byte[] b)throws Exception{return HasselbladProfile43.read(new ByteArrayInputStream(seal(b)));}
    static HasselbladProfile43 exponent(HasselbladProfile43 p,double e)throws Exception{
        byte[] b=p.encoded();int offset=32+38*8+p.gridWidth*p.gridHeight*16+65536*4+16+9*8;
        ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).putDouble(offset,e);return profile(b);
    }
    static HasselbladProfile43 film(HasselbladProfile43 p,HasselbladTone83 pack,int code)throws Exception{
        byte[] b=p.encoded();ByteBuffer bb=ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);bb.putInt(24,code);
        bb.position(32+38*8+p.gridWidth*p.gridHeight*16);for(float v:pack.curve(code))bb.putFloat(v);return profile(b);
    }
    static HasselbladTone83 reference(HasselbladTone83 pack)throws Exception{
        byte[] b=pack.encoded();ByteBuffer bb=ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);
        bb.position(12+2*(4+65536*4)+4);
        for(int i=0;i<65536;i++)bb.putFloat((float)(Math.pow(i/65535.,1.15)*65535));
        return HasselbladTone83.read(new ByteArrayInputStream(seal(b)));
    }
    static void select(Context c,int film)throws Exception{
        HasselbladProfile43 p=HasselbladLookStore84.read(c);
        HasselbladLookStore84.select(c,HasselbladLook84.sha256(p.encoded()),film);switches++;
    }
    static void exercise(Path work,HasselbladProfile43 p,HasselbladTone83 pack)throws Exception{
        profiles++;Context c=new Context(work.resolve("store-"+profiles).toFile());
        HasselbladProfile43 one=HasselbladLook84.select(p,pack,1),zero=HasselbladLook84.select(p,pack,0);
        HasselbladLookStore84.importProfile(c,one);HasselbladLookStore84.importPack(c,pack);
        HasselbladPreview89.Tone t1=HasselbladPreview90Cache.get(one,pack),t0=HasselbladPreview90Cache.get(zero,pack);
        check(!Arrays.equals(t1.texture(),t0.texture()),"distinct curves produce distinct preview tables");
        check(t1==HasselbladPreview90Cache.get(one,pack),"same full source reuses table");
        byte[] saved=one.encoded();
        AtomicReference<HasselbladPreview90Controller.Frame> current=new AtomicReference<>(HasselbladPreview90Controller.Frame.empty());
        AtomicInteger loads=new AtomicInteger(),completed=new AtomicInteger();
        HasselbladPreview90Controller controller=new HasselbladPreview90Controller(()->{
            loads.incrementAndGet();try{return HasselbladPreview89Settings.load(c);}finally{completed.incrementAndGet();}
        },current::set);
        controller.start();await(()->current.get().currentTone()==t1,"initial selected curve loaded");
        int initialLoads=loads.get();controller.start();check(loads.get()==initialLoads,"duplicate start does not resubscribe");
        for(int i=0;i<12;i++){
            HasselbladPreview90Controller.Frame stale=current.get();int target=i%2==0?0:1;
            select(c,target);
            check(stale.currentTone()==null,"committed selection invalidates held GL frame immediately");
            await(()->current.get().currentTone()==(target==0?t0:t1),"live tone switch without pause/resume");
        }
        check(Arrays.equals(saved,HasselbladLookStore84.read(c).encoded()),"round trip preserves complete saved profile");
        HasselbladPreview90Controller.Frame old=current.get();HasselbladPreview89Settings.setEnabled(c,false);
        check(old.currentTone()==null,"toggle invalidates old frame");await(()->current.get().currentTone()==null,"live off");
        HasselbladPreview89Settings.setEnabled(c,true);await(()->current.get().currentTone()==t1,"live on");

        // Same film code, different finishing parameters: film-only keys would be stale.
        HasselbladProfile43 changed=exponent(one,1.8);
        HasselbladPreview89.Tone changedTone=HasselbladPreview90Cache.get(changed,pack);
        check(changedTone!=t1&&!Arrays.equals(changedTone.texture(),t1.texture()),"complete profile contributes to cache key");
        old=current.get();HasselbladLookStore84.importProfile(c,changed);
        check(old.currentTone()==null,"same-film import invalidates");await(()->current.get().currentTone()==changedTone,"same-film replacement applied live");

        // A changed no-film reference can alter the preview while selected curve stays identical.
        HasselbladTone83 newPack=reference(pack);
        HasselbladPreview89.Tone changedReference=HasselbladPreview90Cache.get(changed,newPack);
        check(changedReference!=changedTone&&!Arrays.equals(changedReference.texture(),changedTone.texture()),"complete pack contributes to cache key");
        old=current.get();HasselbladLookStore84.importPack(c,newPack);
        check(old.currentTone()==null,"pack replacement invalidates");await(()->current.get().currentTone()==changedReference,"pack replacement applied live");

        // Replacing a profile before its matching pack must clear the old treatment.
        byte[] customBytes=newPack.encoded();ByteBuffer customBuffer=ByteBuffer.wrap(customBytes).order(ByteOrder.LITTLE_ENDIAN);
        customBuffer.position(12+(4+65536*4)+4);
        for(float value:newPack.curve(1))customBuffer.putFloat((float)(Math.pow(value/65535.,1.1)*65535));
        HasselbladTone83 customPack=HasselbladTone83.read(new ByteArrayInputStream(seal(customBytes)));
        HasselbladProfile43 customProfile=film(changed,customPack,1);
        int beforeFailure=completed.get();old=current.get();HasselbladLookStore84.importProfile(c,customProfile);
        check(old.currentTone()==null,"incompatible replacement immediately invalidates old treatment");
        await(()->completed.get()>beforeFailure&&current.get().currentTone()==null,"incompatible pack falls back to original preview");
        HasselbladPreview89.Tone customTone=HasselbladPreview90Cache.get(customProfile,customPack);
        HasselbladLookStore84.importPack(c,customPack);
        await(()->current.get().currentTone()==customTone,"matching pack restores live preview without restart");

        controller.stop();check(current.get().currentTone()==null,"pause clears frame");int pausedLoads=loads.get();
        select(c,0);check(loads.get()==pausedLoads,"paused preview does not rebuild");
        HasselbladPreview89.Tone pausedTone=HasselbladPreview89Settings.load(c);
        controller.start();await(()->current.get().currentTone()==pausedTone,"resume loads current tone");

        // Importing a no-film profile is supported; the renderer bypasses film 7.
        HasselbladProfile43 noFilm=film(changed,newPack,7);HasselbladLookStore84.importProfile(c,noFilm);
        await(()->current.get().currentTone()!=null&&current.get().currentTone().film==7,"no-film control follows import");
        byte[] identity=current.get().currentTone().texture();
        for(int i=0;i<1024;i++)check(((identity[4*i]&255)*256+(identity[4*i+1]&255))==Math.round(i*65535./1023),"no-film identity");
        controller.close();int closedLoads=loads.get();HasselbladLookStore84.importProfile(c,one);HasselbladLookStore84.importPack(c,pack);
        check(loads.get()==closedLoads&&current.get().currentTone()==null,"closed controller unsubscribed");

        // Failed writes keep the prior profile; a silent finish failure invalidates
        // conservatively and reloads the verified file rather than a requested curve.
        long revision=HasselbladPreview90Changes.revision();AtomicFile.failWrite=true;
        try{reject(()->select(c,0));}finally{AtomicFile.failWrite=false;}
        check(HasselbladPreview90Changes.revision()==revision,"failed write not announced as committed");
        check(HasselbladLookStore84.read(c).film==1,"failed write preserves active tone");
        AtomicFile.silentFinishFailure=true;try{reject(()->select(c,0));}finally{AtomicFile.silentFinishFailure=false;}
        check(HasselbladPreview90Changes.revision()>revision&&HasselbladLookStore84.read(c).film==1,"verification failure reloads actual state");

        // LRU is bounded to three tables, including same-film imports.
        HasselbladProfile43 first=exponent(one,2.0);HasselbladPreview89.Tone evicted=HasselbladPreview90Cache.get(first,pack);
        for(double e:new double[]{2.4,2.6,2.8})HasselbladPreview90Cache.get(exponent(one,e),pack);
        check(evicted!=HasselbladPreview90Cache.get(first,pack),"fourth key evicts least recently used table");

        // Force an old native load to finish after several committed selections.
        CountDownLatch begun=new CountDownLatch(1),release=new CountDownLatch(1);
        AtomicBoolean block=new AtomicBoolean(true);List<Integer> published=Collections.synchronizedList(new ArrayList<>());
        HasselbladPreview90Controller racing=new HasselbladPreview90Controller(()->{
            HasselbladPreview89.Tone t=HasselbladPreview89Settings.load(c);
            if(block.getAndSet(false)){begun.countDown();for(;;)try{release.await();break;}catch(InterruptedException ignored){}}
            return t;
        },f->{current.set(f);HasselbladPreview89.Tone t=f.currentTone();if(t!=null)published.add(t.film);});
        racing.start();check(begun.await(6,TimeUnit.SECONDS),"old load blocked");
        select(c,0);select(c,1);select(c,0);check(current.get().currentTone()==null,"old tone cleared during rapid changes");
        release.countDown();await(()->current.get().currentTone()!=null&&current.get().currentTone().film==0,"latest rapid selection wins");
        check(published.equals(Collections.singletonList(0)),"no superseded tone published");racing.close();
    }
    public static void main(String[] args)throws Exception{
        Path work=Path.of(args[0]);
        for(int i=1;i<args.length;i+=2){
            HasselbladProfile43 p;HasselbladTone83 pack;
            try(InputStream in=Files.newInputStream(Path.of(args[i]))){p=HasselbladProfile43.read(in);}
            try(InputStream in=Files.newInputStream(Path.of(args[i+1]))){pack=HasselbladTone83.read(in);}
            exercise(work,p,pack);
        }
        String result="{\"status\":\"PASS_REACTIVE_PREVIEW\",\"checks\":"+checks+",\"profile_sets\":"+profiles+",\"selection_writes\":"+switches+",\"without_activity_restart\":true,\"max_cached_tables\":3,\"cache_payload_bytes\":12288,\"android_device_tested\":false}";
        Files.writeString(work.resolve("STAGE90_HOST_VALIDATION.json"),result+"\n");System.out.println(result);
    }
}
