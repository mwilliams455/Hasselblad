import com.particlesdevs.photoncamera.hasselblad.HasselbladStage6Contract;
import java.util.HashSet;
import java.util.Set;

public final class Stage6ContractHarness {
    private static int checks=0;
    private static void check(boolean yes) { checks++; if (!yes) throw new AssertionError("check "+checks); }
    public static void main(String[] args) {
        float[] neutral={0.4482421875f,1f,0.462890625f};
        check(HasselbladStage6Contract.supported(4096,3072,0,1,false,false,true,neutral));
        check(HasselbladStage6Contract.supported(64,64,0,1,false,false,true,neutral));
        check(!HasselbladStage6Contract.supported(8192,6144,0,1,false,false,true,neutral));
        check(!HasselbladStage6Contract.supported(4095,3072,0,1,false,false,true,neutral));
        check(!HasselbladStage6Contract.supported(4096,3071,0,1,false,false,true,neutral));
        check(!HasselbladStage6Contract.supported(4096,3072,1,1,false,false,true,neutral));
        check(!HasselbladStage6Contract.supported(4096,3072,0,2,false,false,true,neutral));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,true,false,true,neutral));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,true,true,neutral));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,false,false,neutral));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,false,true,null));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,false,true,new float[]{1f,1f}));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,false,true,new float[]{1f,Float.NaN,1f}));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,false,true,new float[]{1f,-1f,1f}));
        check(!HasselbladStage6Contract.supported(4096,3072,0,1,false,false,true,new float[]{1f,9f,1f}));
        check(HasselbladStage6Contract.PATCH_COUNT==16);
        check(HasselbladStage6Contract.SAMPLES==1024);
        for (int[] dims : new int[][]{{4096,3072},{64,64},{4000,3000},{128,128}}) {
            Set<String> seen=new HashSet<>();
            int counted=0;
            for(int i=0;i<HasselbladStage6Contract.PATCH_COUNT;i++) {
                int[] p=HasselbladStage6Contract.patchRect(dims[0],dims[1],i);
                check(p.length==4 && p[2]==8 && p[3]==8);
                check((p[0]&1)==0 && (p[1]&1)==0);
                check(p[0]>=0 && p[1]>=0 && p[0]+p[2]<=dims[0] && p[1]+p[3]<=dims[1]);
                check(seen.add(p[0]+":"+p[1]));
                counted+=p[2]*p[3];
            }
            check(counted==1024);
        }
        for(int invalid : new int[]{-1,16,17}) {
            try {HasselbladStage6Contract.patchRect(4096,3072,invalid);throw new AssertionError("index");}
            catch(IllegalArgumentException expected) {check(true);}
        }
        try {HasselbladStage6Contract.patchRect(63,64,0);throw new AssertionError("size");}
        catch(IllegalArgumentException expected) {check(true);}
        System.out.println("PASS Stage6 finite bounded ROI & fail-closed eligibility checks="+checks);
    }
}
