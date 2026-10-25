import com.particlesdevs.photoncamera.hasselblad.*;
import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Reversible selection, preservation and persistence failures; no image/demosaic tests. */
public final class Stage84Check {
    static int checks;
    interface Task {void run()throws Exception;}
    static void ok(boolean v){if(!v)throw new AssertionError();checks++;}
    static void reject(Task f)throws Exception{try{f.run();}catch(Exception e){checks++;return;}throw new AssertionError("Expected rejection");}
    static void same(byte[] a,byte[] b){ok(Arrays.equals(a,b));}
    static void preserved(HasselbladProfile43 a,HasselbladProfile43 b)throws Exception {
        byte[] x=a.encoded(),y=b.encoded();int start=32+38*8+a.gridWidth*a.gridHeight*2*8,end=start+65536*4;
        same(Arrays.copyOfRange(x,0,24),Arrays.copyOfRange(y,0,24));
        same(Arrays.copyOfRange(x,28,start),Arrays.copyOfRange(y,28,start));
        same(Arrays.copyOfRange(x,end,x.length-32),Arrays.copyOfRange(y,end,y.length-32));
        for(int t:new int[]{2000,3050,4000,5150,6500,10000})ok(Arrays.equals(a.gridAtTemperature(t),b.gridAtTemperature(t)));
        double[] matrix={.7,.2,.1,.1,.8,.1,.1,.1,.8};ok(Arrays.equals(a.parameters(matrix),b.parameters(matrix)));
    }
    public static void main(String[] args)throws Exception {
        HasselbladTone83 pack=Stage83Check.read(Stage83Check.pack());
        HasselbladProfile43 zero=Stage83Check.profile(true,0,pack.curve(0));byte[] original=zero.encoded();
        HasselbladProfile43 one=HasselbladLook84.select(zero,pack,1);ok(one.film==1);ok(Arrays.equals(one.curve,pack.curve(1)));
        same(original,zero.encoded());preserved(zero,one);
        same(original,HasselbladLook84.select(one,pack,0).encoded());same(one.encoded(),HasselbladLook84.select(one,pack,1).encoded());
        HasselbladProfile43 noFilm=Stage83Check.profile(true,7,pack.curve(7));ok(HasselbladLook84.select(noFilm,pack,1).film==1);
        reject(()->HasselbladLook84.select(zero,pack,7));reject(()->HasselbladLook84.select(zero,pack,-1));
        reject(()->HasselbladLook84.select(zero,null,1));reject(()->HasselbladLook84.select(null,pack,1));
        reject(()->HasselbladLook84.select(Stage83Check.profile(false,0,pack.curve(0)),pack,1));
        reject(()->HasselbladLook84.select(Stage83Check.profile(true,0,pack.curve(1)),pack,1));
        String zeroHash=HasselbladLook84.sha256(original),oneHash=HasselbladLook84.sha256(one.encoded());
        HasselbladLook84.requireCurrent(zero,zeroHash);ok(!zeroHash.equals(oneHash));
        reject(()->HasselbladLook84.requireCurrent(zero,oneHash));reject(()->HasselbladLook84.requireCurrent(zero,null));
        ok(!HasselbladLook84.curveHash(zero).equals(HasselbladLook84.curveHash(one)));
        Context context=new Context(new File(args[0],"private-store"));
        reject(()->HasselbladLookStore84.read(context));
        HasselbladLookStore84.importProfile(context,zero);HasselbladLookStore84.importPack(context,pack);
        same(original,HasselbladLookStore84.read(context).encoded());
        HasselbladProfile43 selected=HasselbladLookStore84.select(context,zeroHash,1);same(one.encoded(),selected.encoded());
        same(one.encoded(),HasselbladLookStore84.read(context).encoded());
        reject(()->HasselbladLookStore84.select(context,zeroHash,0));same(one.encoded(),HasselbladLookStore84.read(context).encoded());
        AtomicFile.failWrite=true;reject(()->HasselbladLookStore84.select(context,oneHash,0));AtomicFile.failWrite=false;
        same(one.encoded(),HasselbladLookStore84.read(context).encoded());
        AtomicFile.failFinish=true;reject(()->HasselbladLookStore84.select(context,oneHash,0));AtomicFile.failFinish=false;
        same(one.encoded(),HasselbladLookStore84.read(context).encoded());
        AtomicFile.silentFinishFailure=true;reject(()->HasselbladLookStore84.select(context,oneHash,0));AtomicFile.silentFinishFailure=false;
        same(one.encoded(),HasselbladLookStore84.read(context).encoded());
        Thread.currentThread().interrupt();reject(()->HasselbladLookStore84.select(context,oneHash,0));Thread.interrupted();
        same(one.encoded(),HasselbladLookStore84.read(context).encoded());
        same(original,HasselbladLookStore84.select(context,oneHash,0).encoded());
        boolean privateProfiles=false;
        if(args.length==4) {
            HasselbladProfile43 p0,p1;HasselbladTone83 realPack;
            try(InputStream in=Files.newInputStream(Path.of(args[1]))){p0=HasselbladProfile43.read(in);}
            try(InputStream in=Files.newInputStream(Path.of(args[2]))){p1=HasselbladProfile43.read(in);}
            try(InputStream in=Files.newInputStream(Path.of(args[3]))){realPack=HasselbladTone83.read(in);}
            HasselbladProfile43 actual=HasselbladLook84.select(p0,realPack,1);
            same(p1.encoded(),actual.encoded());preserved(p0,actual);
            same(p0.encoded(),HasselbladLook84.select(actual,realPack,0).encoded());privateProfiles=true;
        }
        String json="{\"schema\":\"hasselblad-stage84-host-v1\",\"status\":\"PASS\",\"checks\":"+checks+
            ",\"private_profile_exact_match\":"+privateProfiles+",\"persistence_adapter\":\"JVM fault-injection substitute for Android AtomicFile\",\"device_tested\":false,\"demosaic_retested\":false}";
        Files.writeString(Path.of(args[0],"STAGE84_HOST_VALIDATION.json"),json+"\n");System.out.println(json);
    }
}
