import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;import java.nio.*;import java.nio.file.*;import java.util.*;import java.security.*;
public final class Stage43Smoke {
    static int checks;
    static void check(boolean b,String what){checks++;if(!b)throw new AssertionError(what);}
    static double[] calibration(HasselbladDngTileReader.PreviewResult p) {
        var m=p.metadata;return HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
    }
    static void checksum(byte[] b)throws Exception {
        MessageDigest sha=MessageDigest.getInstance("SHA-256");sha.update(b,0,b.length-32);
        System.arraycopy(sha.digest(),0,b,b.length-32,32);
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);
        for(String name:new String[]{"plain","gains","big_multistrip","rotate3","rotate6"})for(int limit:new int[]{4096,512}) {
            var p=HasselbladDngTileReader.readPreview(root.resolve(name+".dng").toFile(),limit);
            byte[] expected=Files.readAllBytes(root.resolve(name+"-"+limit+".rgb16"));
            ByteBuffer actual=ByteBuffer.allocate(p.cameraRgb16.length*2).order(ByteOrder.LITTLE_ENDIAN);
            for(short v:p.cameraRgb16)actual.putShort(v);
            check(Arrays.equals(expected,actual.array()),name+" RGB16 limit "+limit);
            check(p.width*p.height<=limit,"preview limit");check(calibration(p).length==9,"calibration");
            int orientation=name.equals("rotate3")?3:name.equals("rotate6")?6:name.equals("big_multistrip")?8:1;
            check(p.orientation==orientation,"orientation");
        }
        for(String bad:new String[]{"compressed","bad_cfa","crop","dual","opcode","black_repeat","neutral","linearization","layout","strip"}) {
            boolean failed=false;
            try{calibration(HasselbladDngTileReader.readPreview(root.resolve("bad_"+bad+".dng").toFile(),4096));}
            catch(IOException|IllegalArgumentException e){failed=true;}
            check(failed,"reject "+bad);
        }
        double[] fm={.9642,0,0,0,1,0,0,0,.8249},neutral={.5,1,.25};
        double[] camera=HasselbladRenderer42.cameraToD50(fm,fm,null,null,null,neutral);
        check(Math.abs(camera[0]-1.9284)<1e-12&&Math.abs(camera[8]-3.2996)<1e-12,"DNG WB once");
        for(int bad=0;bad<3;bad++) {
            boolean failed=false;
            try {HasselbladRenderer42.cameraToD50(bad==0?null:bad==1?new double[8]:fm,null,null,null,null,
                    bad==2?new double[]{Double.NaN,1,1}:neutral);}catch(IllegalArgumentException e){failed=true;}
            check(failed,"JNI calibration reject "+bad);
        }
        byte[] encoded=Files.readAllBytes(root.resolve("synthetic.hbc"));
        var profile=HasselbladProfile43.read(new ByteArrayInputStream(encoded));
        short[] input={100,200,300,0,0,0};
        short[] out=HasselbladRenderer42.render(input,profile.parameters(new double[]{1,0,0,0,1,0,0,0,1}),
            profile.grid,profile.curve,profile.gridWidth,profile.gridHeight,1);
        check(Arrays.equals(out,new short[]{200,200,200,0,0,0}),"profile to JNI");
        check(profile.display(out).length==2,"profile display");
        for(int bad=0;bad<8;bad++) {
            byte[] damaged=encoded.clone();ByteBuffer b=ByteBuffer.wrap(damaged).order(ByteOrder.LITTLE_ENDIAN);
            if(bad==0)b.putInt(8,Integer.MAX_VALUE);
            if(bad==1)b.putDouble(32,Double.NaN);
            if(bad==2)b.putDouble(32+22*8,2);
            if(bad==3)b.putDouble(32+37*8,0);
            if(bad==4)b.putDouble(32+38*8,Double.NaN);
            if(bad==5)b.putFloat(32+38*8+64,-1);
            if(bad==6)b.put(0,(byte)'X');
            checksum(damaged);if(bad==7)damaged[48]^=1;
            boolean failed=false;
            try{HasselbladProfile43.read(new ByteArrayInputStream(damaged));}catch(IOException e){failed=true;}
            check(failed,"profile reject "+bad);
        }
        boolean cancelled=false;Thread.currentThread().interrupt();
        try{HasselbladDngTileReader.readPreview(root.resolve("plain.dng").toFile(),4096);}catch(IOException e){cancelled=true;}
        finally{Thread.interrupted();}
        check(cancelled,"cancellation");
        System.out.println("{\"status\":\"PASS\",\"checks\":"+checks+",\"synthetic_only\":true,\"raw_reference\":\"Stage30 full-frame float32 bilinear\"}");
    }
}
