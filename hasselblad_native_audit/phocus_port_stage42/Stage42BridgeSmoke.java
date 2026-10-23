import com.particlesdevs.photoncamera.hasselblad.HasselbladRenderer42;
import com.particlesdevs.photoncamera.hasselblad.HasselbladRenderBundle42;
import java.io.*;
import java.nio.*;
import java.security.MessageDigest;
import java.util.Arrays;

public final class Stage42BridgeSmoke {
    static int checks;
    static void check(boolean v){checks++;if(!v)throw new AssertionError("check "+checks);}
    public static void main(String[] args) throws Exception {
        double[] p=new double[38];p[1]=1;p[9]=999;p[13]=999;p[17]=999;
        p[18]=2;p[21]=1;p[22]=p[23]=p[24]=p[25]=1;
        p[28]=p[32]=p[36]=1;p[37]=1;
        double[] grid=new double[8];float[] curve=new float[65536];
        for(int i=0;i<65536;i++)curve[i]=i+.25f;
        curve[65535]=65535;
        short[] in={(short)100,200,300,0,0,0};
        short[] out=HasselbladRenderer42.render(in,p,grid,curve,2,2,1);
        check(Arrays.equals(out,new short[]{200,200,200,0,0,0}));check(in[0]==100);
        for(int bad=0;bad<4;bad++) {
            boolean failed=false;
            try {
                double[] q=p.clone();
                if(bad==0)q[22]=2;if(bad==1)q[25]=Double.NaN;
                HasselbladRenderer42.render(bad==2?null:in,q,grid,
                    bad==3?new float[1]:curve,2,2,1);
            }catch(IllegalArgumentException expected){failed=true;}
            check(failed);
        }
        // Synthetic format, checksum, JNI render, output hash and display conversion.
        ByteBuffer b=ByteBuffer.allocate(8+40+38*8+8*8+65536*4+64+2*9+32).order(ByteOrder.LITTLE_ENDIAN);
        b.put(new byte[]{'H','B','4','2','R','A','W','1'});
        for(int v:new int[]{2,1,2,2,1,1,4000,0,1,0})b.putInt(v);
        for(double v:p)b.putDouble(v);for(double v:grid)b.putDouble(v);
        for(float v:curve)b.putFloat(v);b.put(new byte[32]);
        ByteBuffer encoded=ByteBuffer.allocate(out.length*2).order(ByteOrder.LITTLE_ENDIAN);
        for(short v:out)encoded.putShort(v);
        b.put(MessageDigest.getInstance("SHA-256").digest(encoded.array()));
        for(short v:in)b.putShort(v);b.put(new byte[6]);
        MessageDigest sha=MessageDigest.getInstance("SHA-256");sha.update(b.array(),0,b.position());b.put(sha.digest());
        HasselbladRenderBundle42 bundle=HasselbladRenderBundle42.read(new ByteArrayInputStream(b.array()));
        check(bundle.width==2&&bundle.height==1);check(bundle.matches(out));check(bundle.display(out).length==2);
        check(!bundle.matches(new short[6]));
        byte[] damaged=b.array().clone();damaged[60]^=1;
        try{HasselbladRenderBundle42.read(new ByteArrayInputStream(damaged));throw new AssertionError();}
        catch(IOException expected){checks++;}
        // Check dimensions before allocation, with a valid recalculated checksum.
        damaged=b.array().clone();ByteBuffer.wrap(damaged).order(ByteOrder.LITTLE_ENDIAN).putInt(8,Integer.MAX_VALUE);
        sha.reset();sha.update(damaged,0,damaged.length-32);
        System.arraycopy(sha.digest(),0,damaged,damaged.length-32,32);
        try{HasselbladRenderBundle42.read(new ByteArrayInputStream(damaged));throw new AssertionError();}
        catch(IOException expected){checks++;}
        System.out.println("{\"status\":\"PASS\",\"checks\":"+checks+",\"synthetic_only\":true}");
    }
}
