import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Synthetic-only JNI, profile compatibility and numeric boundary regression. */
public final class Stage55Smoke {
    static int checks;
    static void check(boolean value,String what){checks++;if(!value)throw new AssertionError(what);}
    interface Action {void run()throws Exception;}
    static void reject(Action a)throws Exception {
        boolean rejected=false;try{a.run();}catch(IOException|IllegalArgumentException|IllegalStateException e){rejected=true;}
        check(rejected,"invalid input accepted");
    }
    static void checksum(byte[] b)throws Exception {
        MessageDigest h=MessageDigest.getInstance("SHA-256");h.update(b,0,b.length-32);
        System.arraycopy(h.digest(),0,b,b.length-32,32);
    }
    static int defaultCurve(int i) {
        double high=16383/(255*64.0),gain=1/(double)(float)high,extent=high*gain;
        int index=(int)((i*(1/65535.0))*gain*65535/extent);
        return (int)Math.floor((double)(float)(extent/65535*index)*65535+.5);
    }
    static final double[] ID={1,0,0,0,1,0,0,0,1};
    public static void main(String[] args)throws Exception {
        short[] input=new short[(65536+4913)*3];int k=0;
        for(int i=0;i<65536;i++)for(int c=0;c<3;c++)input[k++]=(short)i;
        for(int r=0;r<17;r++)for(int g=0;g<17;g++)for(int b=0;b<17;b++) {
            input[k++]=(short)Math.round(r*65535/16.0);input[k++]=(short)Math.round(g*65535/16.0);input[k++]=(short)Math.round(b*65535/16.0);
        }
        short[] original=input.clone();short[] grad=HasselbladRenderer42.defaultGradation(input);
        check(Arrays.equals(input,original),"gradation mutated source");
        for(int i=0;i<input.length;i++)check(Math.abs((grad[i]&65535)-defaultCurve(input[i]&65535))<=1,"gradation numeric bound");
        short[] output=HasselbladRenderer42.outputSrgb16(input,ID,1);
        for(int i=0;i<input.length;i++) {
            float normalized=(input[i]&65535)/65535.f;
            float encoded=(float)(normalized<=.0031308?normalized*12.92:1.055*Math.pow(normalized,1/2.4)-.055);
            int expected=Math.min(65535,(int)Math.floor((double)(encoded*65535.f)+.5));
            check(Math.abs((output[i]&65535)-expected)<=1,"independent sRGB output");
        }
        check(Arrays.equals(input,original),"output mutated source");
        int[] packed=HasselbladProfile43.srgb16ToArgb(input);
        for(int i=0;i<packed.length;i++)for(int c=0;c<3;c++)
            check(((packed[i]>>(16-8*c))&255)==Math.round((input[3*i+c]&65535)*255/65535.0),"8-bit quantization");
        byte[] legacy=Files.readAllBytes(Path.of(args[0],"synthetic.hbc"));
        var old=HasselbladProfile43.read(new ByteArrayInputStream(legacy));check(!old.hasNativeFinishing,"legacy flag");
        reject(()->old.finishRgb16(input));
        byte[] extended=new byte[legacy.length+96];System.arraycopy(legacy,0,extended,0,legacy.length-32);
        extended[2]='5';extended[3]='5';int offset=legacy.length-32;
        ByteBuffer buffer=ByteBuffer.wrap(extended).order(ByteOrder.LITTLE_ENDIAN);buffer.position(offset);
        buffer.putInt(1).putInt(0).putInt(2).putInt(1);for(double v:ID)buffer.putDouble(v);buffer.putDouble(1);checksum(extended);
        var profile=HasselbladProfile43.read(new ByteArrayInputStream(extended));check(profile.hasNativeFinishing,"new flag");
        check(Arrays.equals(profile.grid,old.grid)&&Arrays.equals(profile.curve,old.curve)&&Arrays.equals(profile.parameters(ID),old.parameters(ID)),"colour payload unchanged");
        check(Arrays.equals(profile.display(input),old.display(input)),"legacy adapter unchanged");
        check(Arrays.equals(profile.finishRgb16(input),HasselbladRenderer42.outputSrgb16(grad,ID,1)),"profile finishing");
        for(int field=0;field<4;field++) {
            byte[] bad=extended.clone();ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN).putInt(offset+field*4,99);checksum(bad);
            reject(()->HasselbladProfile43.read(new ByteArrayInputStream(bad)));
        }
        for(double badValue:new double[]{Double.NaN,Double.POSITIVE_INFINITY,1e7}) {
            byte[] bad=extended.clone();ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN).putDouble(offset+16,badValue);checksum(bad);
            reject(()->HasselbladProfile43.read(new ByteArrayInputStream(bad)));
            double[] m=ID.clone();m[0]=badValue;reject(()->HasselbladRenderer42.outputSrgb16(input,m,1));
        }
        for(double exp:new double[]{0,-1,9,Double.NaN,Double.NEGATIVE_INFINITY}) {
            byte[] bad=extended.clone();ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN).putDouble(offset+88,exp);checksum(bad);
            reject(()->HasselbladProfile43.read(new ByteArrayInputStream(bad)));
            reject(()->HasselbladRenderer42.outputSrgb16(input,ID,exp));
        }
        for(short[] bad:new short[][]{null,new short[0],new short[2],new short[1048576*3+3]}) {
            reject(()->HasselbladRenderer42.defaultGradation(bad));reject(()->HasselbladRenderer42.outputSrgb16(bad,ID,1));
        }
        reject(()->HasselbladRenderer42.outputSrgb16(input,null,1));reject(()->HasselbladRenderer42.outputSrgb16(input,new double[8],1));
        byte[] corrupted=extended.clone();corrupted[corrupted.length-1]^=1;reject(()->HasselbladProfile43.read(new ByteArrayInputStream(corrupted)));
        byte[] truncated=Arrays.copyOf(extended,extended.length-1);checksum(truncated);reject(()->HasselbladProfile43.read(new ByteArrayInputStream(truncated)));
        System.out.println("{\"status\":\"PASS\",\"checks\":"+checks+",\"pixels\":"+input.length/3+",\"synthetic_only\":true}");
    }
}
