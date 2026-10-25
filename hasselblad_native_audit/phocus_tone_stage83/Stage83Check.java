import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Synthetic input validation and stream/metric checks; no private payload in source. */
public final class Stage83Check {
    private static int checks;
    interface Task {void run()throws Exception;}
    static void ok(boolean result){if(!result)throw new AssertionError();checks++;}
    static void reject(Task task)throws Exception {try{task.run();}catch(IOException|IllegalArgumentException e){checks++;return;}throw new AssertionError("Accepted malformed input");}
    static byte[] signed(byte[] data)throws Exception {
        MessageDigest sha=MessageDigest.getInstance("SHA-256");sha.update(data,0,data.length-32);
        System.arraycopy(sha.digest(),0,data,data.length-32,32);return data;
    }
    static float[] ramp(int divisor){float[] c=new float[65536];for(int i=0;i<c.length;i++)c[i]=i/divisor;return c;}
    static byte[] pack()throws Exception {
        ByteBuffer b=ByteBuffer.allocate(HasselbladTone83.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        b.put("HB83CRV1".getBytes("US-ASCII")).putInt(3);int j=1;
        for(int film:new int[]{0,1,7}){b.putInt(film);for(float v:ramp(j++))b.putFloat(v);}
        return signed(b.array());
    }
    static HasselbladTone83 read(byte[] data)throws Exception{return HasselbladTone83.read(new ByteArrayInputStream(data));}
    static byte[] changeInt(byte[] original,int offset,int value)throws Exception {
        byte[] data=original.clone();ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).putInt(offset,value);return signed(data);
    }
    static HasselbladProfile43 profile(boolean automatic,int film,float[] curve)throws Exception {
        int length=32+38*8+8*8+65536*4+32+(automatic?96+8+3*(4+8*8):0);
        ByteBuffer b=ByteBuffer.allocate(length).order(ByteOrder.LITTLE_ENDIAN);
        b.put((automatic?"HB56LUT1":"HB43LUT1").getBytes("US-ASCII"));
        for(int i:new int[]{2,2,4000,0,film,0})b.putInt(i);
        for(int i=0;i<38;i++)b.putDouble(i>=22&&i<=25||i==37?1:0);
        for(int i=0;i<8;i++)b.putDouble(0);for(float v:curve)b.putFloat(v);
        if(automatic) {
            for(int i:new int[]{1,0,2,1})b.putInt(i);
            for(int i=0;i<9;i++)b.putDouble(i%4==0?1:0);b.putDouble(1);
            b.putInt(1).putInt(3);for(int t:new int[]{2850,5000,6500}){b.putInt(t);for(int i=0;i<8;i++)b.putDouble(0);}
        }
        return HasselbladProfile43.read(new ByteArrayInputStream(signed(b.array())));
    }
    public static void main(String[] args)throws Exception {
        byte[] data=pack();HasselbladTone83 tones=read(data);
        ok(Arrays.equals(data,tones.encoded()));ok(Arrays.equals(ramp(1),tones.curve(0)));
        ok(Arrays.equals(ramp(2),tones.curve(1)));ok(Arrays.equals(ramp(3),tones.curve(7)));
        float[] copy=tones.curve(0);copy[65535]=0;ok(tones.curve(0)[65535]==65535);
        byte[] copyBytes=tones.encoded();copyBytes[0]=0;ok(Arrays.equals(tones.encoded(),data));
        reject(()->tones.curve(4));reject(()->HasselbladTone83.read(null));
        reject(()->read(Arrays.copyOf(data,data.length-1)));reject(()->read(Arrays.copyOf(data,data.length+1)));
        byte[] bad=data.clone();bad[25]^=1;reject(()->read(bad));
        reject(()->read(changeInt(data,0,0)));reject(()->read(changeInt(data,8,4)));
        reject(()->read(changeInt(data,12,7)));reject(()->read(changeInt(data,12+4+65536*4,0)));
        for(float v:new float[]{Float.NaN,Float.POSITIVE_INFINITY,-1,65536})
            reject(()->read(changeInt(data,16,Float.floatToIntBits(v))));
        reject(()->read(changeInt(data,16+400,Float.floatToIntBits(0))));
        for(int film:new int[]{0,1,7}) {
            HasselbladProfile43 p=profile(true,film,tones.curve(film));byte[] original=p.encoded();
            tones.validateProfile(p);ok(Arrays.equals(original,p.encoded()));
        }
        reject(()->tones.validateProfile(profile(false,0,ramp(1))));
        reject(()->tones.validateProfile(profile(true,1,ramp(1))));
        byte[] words={0,0,-1,-1,0,-128,1,0,0,1};
        try(DataInputStream in=new DataInputStream(new ByteArrayInputStream(words))) {
            ok(Arrays.equals(HasselbladTone83.readBand(in,3),new short[]{0,-1,Short.MIN_VALUE}));
            ok(Arrays.equals(HasselbladTone83.readBand(in,2),new short[]{1,256}));ok(in.read()==-1);
            reject(()->HasselbladTone83.readBand(in,1));reject(()->HasselbladTone83.readBand(in,0));
            reject(()->HasselbladTone83.readBand(in,Integer.MAX_VALUE));
        }
        HasselbladTone83.Stats stats=new HasselbladTone83.Stats();
        ok(stats.meanAbsoluteDifference()==0);
        stats.add(new int[]{0xff000000,0xffffffff},new int[]{0xff000000,0xffffffff});
        stats.add(new int[]{0xffff0000,0xff000102},new int[]{0xff000000,0xff000000});
        ok(stats.pixels==4&&stats.changedPixels==2);ok(stats.absoluteDifference==258&&stats.maxDifference==255);
        ok(stats.meanAbsoluteDifference()==21.5);ok(stats.whiteChannelPixels==2&&stats.allWhitePixels==1&&stats.allBlackPixels==1);
        reject(()->stats.add(new int[1],new int[0]));
        boolean privatePack=false;
        if(args.length>1) {
            try(InputStream in=Files.newInputStream(Path.of(args[1]))) {
                HasselbladTone83 real=HasselbladTone83.read(in);
                for(int film:new int[]{0,1,7}){real.validateProfile(profile(true,film,real.curve(film)));ok(real.curve(film).length==65536);}
                privatePack=true;
            }
        }
        String result="{\"schema\":\"hasselblad-stage83-host-v1\",\"status\":\"PASS\",\"checks\":"+checks+
            ",\"private_pack_read\":"+privatePack+",\"device_tested\":false,\"demosaic_retested\":false}";
        Files.writeString(Path.of(args[0]),result+"\n");System.out.println(result);
    }
}
