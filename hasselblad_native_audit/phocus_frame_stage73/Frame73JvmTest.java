import com.particlesdevs.photoncamera.hasselblad.HasselbladPreNoise73;
import java.util.Arrays;
/** Host JVM/JNI data-contract smoke, no Android SDK or vendor data. */
public final class Frame73JvmTest {
    public static void main(String[] args) {
        final int w=12,h=15,stride=w+69;
        short[] input=new short[stride*(h+64)];
        Arrays.fill(input,(short)10000);
        short[] frozen=input.clone();
        short[] out=new short[w*h*4+16];Arrays.fill(out,(short)0x4444);
        int rc=HasselbladPreNoise73.nativeRender(input,w,h,stride,0,out);
        if(rc!=0)throw new AssertionError("JNI render rc="+rc);
        if(!Arrays.equals(input,frozen))throw new AssertionError("JNI mutated Bayer input");
        for(int i=0;i<w*h*4;i+=4){
            if((out[i]&0xffff)!=10000||(out[i+1]&0xffff)!=10000||
               (out[i+2]&0xffff)!=10000)throw new AssertionError("neutral pixel "+i);
        }
        for(int i=w*h*4;i<out.length;i++)if((out[i]&0xffff)!=0x4444)
            throw new AssertionError("JNI output overrun "+i);
        Arrays.fill(out,(short)0x4444);
        rc=HasselbladPreNoise73.nativeRender(input,w,h,stride,1,out);
        if(rc!=-2)throw new AssertionError("invalid CFA must fail closed: "+rc);
        for(short code:out)if((code&0xffff)!=0x4444)
            throw new AssertionError("invalid CFA mutated output");
        rc=HasselbladPreNoise73.nativeRender(input,40,40,stride,0,out);
        if(rc!=-2)throw new AssertionError("unsupported size accepted");
        short[] shared=new short[stride*(h+64)];
        rc=HasselbladPreNoise73.nativeRender(shared,w,h,stride,0,shared);
        if(rc!=-1)throw new AssertionError("Input/output alias accepted");
        System.out.println("STAGE73_JVM_JNI_INTERMEDIATE_RGB_MASK_PASS");
    }
}
