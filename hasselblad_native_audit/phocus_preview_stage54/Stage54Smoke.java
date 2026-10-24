import com.particlesdevs.photoncamera.hasselblad.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

public final class Stage54Smoke {
    static int checks;static long channels;static int maxDifference;
    static void check(boolean b,String what){checks++;if(!b)throw new AssertionError(what);}
    static double[] doubles(ByteBuffer b,int n){double[] v=new double[n];for(int i=0;i<n;i++)v[i]=b.getDouble();return v;}
    static short[] shorts(ByteBuffer b,int n){short[] v=new short[n];for(int i=0;i<n;i++)v[i]=b.getShort();return v;}
    static double[] mul(double[] m,double[] v){double[] r=new double[3];for(int i=0;i<3;i++)for(int j=0;j<3;j++)r[i]+=m[i*3+j]*v[j];return r;}
    static void reject(Runnable action) {
        boolean caught=false;try{action.run();}catch(IllegalArgumentException e){caught=true;}
        check(caught,"invalid input rejected");
    }
    public static void main(String[] args)throws Exception {
        ByteBuffer b=ByteBuffer.wrap(Files.readAllBytes(Path.of(args[0],"bridge54.bin"))).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic=new byte[8];b.get(magic);check(Arrays.equals(magic,"HB54TEST".getBytes(java.nio.charset.StandardCharsets.US_ASCII)),"magic");
        int cases=b.getInt(),count=b.getInt();double maxFactorError=0;
        for(int k=0;k<cases;k++) {
            double[] neutral=doubles(b,3),matrix=doubles(b,9),gains=doubles(b,3),after=doubles(b,9);
            short[] input=shorts(b,count*3),expected=shorts(b,count*3),frozen=input.clone();
            double[] nm=neutral.clone(),mm=matrix.clone();
            var p=HasselbladPreparedHighlight54.prepare(matrix,neutral);
            check(Arrays.equals(gains,p.gainRatios),"gain ratios");
            for(int i=0;i<9;i++)check(Math.abs(after[i]-p.afterMatrix[i])<1e-14,"matrix columns");
            short[] output=p.reconstruct(input);
            for(int i=0;i<output.length;i++) {
                int difference=Math.abs((output[i]&65535)-(expected[i]&65535));
                maxDifference=Math.max(maxDifference,difference);channels++;
                check(difference<=1,"JNI vs independent oracle");
            }
            check(Arrays.equals(input,frozen)&&Arrays.equals(neutral,nm)&&Arrays.equals(matrix,mm),"inputs unchanged");
            // Isolate WB ownership without intermediate integer quantization.
            for(int i=0;i<input.length;i+=3) {
                double[] raw={(input[i]&65535)/65535.,(input[i+1]&65535)/65535.,(input[i+2]&65535)/65535.};
                double[] weighted={raw[0]*gains[0],raw[1]*gains[1],raw[2]*gains[2]};
                double[] reference=mul(matrix,raw),factored=mul(p.afterMatrix,weighted);
                for(int c=0;c<3;c++)maxFactorError=Math.max(maxFactorError,Math.abs(reference[c]-factored[c]));
            }
            if(k==6)check(Arrays.equals(input,output)&&p.analyticEqualGainLimit,"unity identity");
        }
        check(!b.hasRemaining()&&maxFactorError<2e-15,"WB factorization");
        double[] gains={1,.7,.3},unity={1,1,1};short[] pixel={0,100,(short)65535};
        reject(()->HasselbladRenderer42.reconstructHighlights(null,gains,false));
        reject(()->HasselbladRenderer42.reconstructHighlights(new short[0],gains,false));
        reject(()->HasselbladRenderer42.reconstructHighlights(new short[2],gains,false));
        reject(()->HasselbladRenderer42.reconstructHighlights(new short[1048577*3],gains,false));
        reject(()->HasselbladRenderer42.reconstructHighlights(pixel,null,false));
        reject(()->HasselbladRenderer42.reconstructHighlights(pixel,new double[2],false));
        reject(()->HasselbladRenderer42.reconstructHighlights(pixel,new double[]{0,1,2},false));
        reject(()->HasselbladRenderer42.reconstructHighlights(pixel,new double[]{Double.NaN,1,2},false));
        reject(()->HasselbladRenderer42.reconstructHighlights(pixel,unity,false));
        check(Arrays.equals(pixel,HasselbladRenderer42.reconstructHighlights(pixel,unity,true)),"explicit limit");
        double[] identity={1,0,0,0,1,0,0,0,1};
        reject(()->HasselbladPreparedHighlight54.prepare(null,unity));
        reject(()->HasselbladPreparedHighlight54.prepare(identity,new double[]{1,0,1}));
        reject(()->HasselbladPreparedHighlight54.prepare(identity,new double[]{Double.POSITIVE_INFINITY,1,1}));
        reject(()->HasselbladPreparedHighlight54.prepare(identity,new double[]{Double.MIN_VALUE,Double.MAX_VALUE,1}));
        double[] bad=identity.clone();bad[0]=Double.NaN;
        reject(()->HasselbladPreparedHighlight54.prepare(bad,unity));
        System.out.println("{\"schema\":\"hasselblad-stage54-host-jni-v1\",\"status\":\"PASS\",\"synthetic_cases\":"+cases+
            ",\"compared_channels\":"+channels+",\"maximum_rgb16_difference\":"+maxDifference+
            ",\"wb_factorization_max_error\":"+maxFactorError+",\"checks\":"+checks+
            ",\"synthetic_only\":true,\"device_tested\":false,\"full_phocus_equivalence\":false}");
    }
}
