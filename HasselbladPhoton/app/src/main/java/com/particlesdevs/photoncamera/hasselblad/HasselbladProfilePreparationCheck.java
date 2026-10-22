package com.particlesdevs.photoncamera.hasselblad;

import java.security.MessageDigest;
import java.util.Locale;

/**
 * Stage8 experimental, explicitly user-run, non-photographic self-check.
 * Tests profile-preparation math, not colour rendering or a Hasselblad look.
 * No RAW, camera, GPU, proprietary IQ table, WB or image access.
 */
public final class HasselbladProfilePreparationCheck {
    private HasselbladProfilePreparationCheck() { }
    private static native int[] nativePrepare(int[] packedSyntheticEightProfiles,
                                              int cctKelvin, int gamut);
    private static final int[] CCTS={1000,2400,2725,3001,3050,4300,5550,7001,9099,9100,14000,14000};
    private static final int[] GAMUTS={0,0,0,1,1,0,1,0,1,1,0,1};
    private static final long[][] NATIVE_EXPECTED={
        {1902087001L,1689031804L,1475976607L,1262921410L,1049866213L,836811016L,623755819L},
        {1902087001L,1689031804L,1475976607L,1262921410L,1049866213L,836811016L,623755819L},
        {1744345434L,1531290237L,1318235040L,1105179843L,892124646L,679069449L,466014252L},
        {349574455L,136519258L,4218431357L,4005376160L,3792320963L,3579265766L,3366210569L},
        {324933480L,111878283L,4193790382L,3980735185L,3767679988L,3554624791L,3341569594L},
        {1428927837L,1215872640L,1002817443L,789762246L,576707049L,363651852L,150596655L},
        {9515883L,4091427982L,3878372785L,3665317588L,3452262391L,3239207194L,3026151997L},
        {1143066304L,930011107L,716955910L,503900713L,290845516L,77790319L,4159636882L},
        {3990245201L,3777190004L,3564134807L,3351079610L,3138024413L,2924974986L,2711919789L},
        {3989065582L,3776010385L,3562955188L,3349899991L,3136844794L,2923795132L,2710739935L},
        {955834210L,742779013L,529723816L,316668619L,103547886L,4185459985L,3972404788L},
        {3989065582L,3776010385L,3562955188L,3349899991L,3136844794L,2923795132L,2710739935L}
    };

    private static int pack(int low,int high) { return (low & 65535) | ((high & 65535) << 16); }
    private static int lane(int word, int shift) {
        int b=(word >>> shift) & 65535;
        return b >= 32768 ? b-65536 : b;
    }
    private static int blend(int a,int b,int q8) {
        return a + Math.floorDiv((b-a)*q8,256);
    }
    private static int[] cctCoeff(int value) {
        int[] axis={2400,3050,5550,9100};
        if (value<axis[0]) return new int[]{0,0};
        if (value>=axis[3]) return new int[]{2,256};
        for(int i=0;i<3;i++) {
            if(value<axis[i+1])return new int[]{i,(value-axis[i])*256/(axis[i+1]-axis[i])};
        }
        throw new IllegalArgumentException("Invalid CCT axis");
    }
    private static int[] synthetic(int words) {
        int[] src=new int[words*8];
        for(int p=0;p<8;p++) for(int j=0;j<words;j++) {
            int low=(p*7171+j*2339+137)%60001-30000;
            int high=30000-(p*4813+j*3251+977)%60001;
            src[p*words+j]=pack(low,high);
        }
        return src;
    }
    private static int[] independentReference(int[] src,int words,int cct,int gamut) {
        int[] cf=cctCoeff(cct); int c=cf[0],f=cf[1];
        int[] result=new int[words];
        for(int j=0;j<words;j++) {
            int[] components=new int[2];
            for(int half=0;half<2;half++) {
                int shift=16*half;
                int a=blend(lane(src[(c+0)*words+j],shift),
                            lane(src[(c+1)*words+j],shift),f);
                int b=blend(lane(src[(c+4)*words+j],shift),
                            lane(src[(c+5)*words+j],shift),f);
                components[half]=blend(a,b,256*gamut);
            }
            result[j]=pack(components[0],components[1]);
        }
        return result;
    }
    private static boolean same(int[] a,int[] b) {
        if(a==null||b==null||a.length!=b.length)return false;
        for(int i=0;i<a.length;i++)if(a[i]!=b[i])return false;
        return true;
    }
    private static String sha256LE(int[] data) throws Exception {
        MessageDigest dig=MessageDigest.getInstance("SHA-256");
        byte[] buf=new byte[4];
        for(int word:data) {
            buf[0]=(byte)word;
            buf[1]=(byte)(word>>>8);
            buf[2]=(byte)(word>>>16);
            buf[3]=(byte)(word>>>24);
            dig.update(buf);
        }
        StringBuilder result=new StringBuilder();
        for(byte v:dig.digest())result.append(String.format(Locale.US,"%02x",v&255));
        return result.toString();
    }

    /** Never called by processing/shutter; always explicit UI action. */
    public static String run() {
        int nativePasses=0, nativeCases=CCTS.length, fullSizePasses=0, fullSizeCases=8;
        String fullSizeDigest="";
        String error="";
        long started=System.nanoTime();
        try {
            System.loadLibrary("hasselblad_profile_jni");
            final int[] src=synthetic(7);
            for(int i=0;i<nativeCases;i++) {
                int[] actual=nativePrepare(src,CCTS[i],GAMUTS[i]);
                if(actual==null || actual.length!=7)continue;
                boolean match=true;
                for(int j=0;j<7;j++) {
                    if(Integer.toUnsignedLong(actual[j])!=NATIVE_EXPECTED[i][j]) {match=false;break;}
                }
                if(match && same(actual,independentReference(src,7,CCTS[i],GAMUTS[i])))nativePasses++;
            }
            final int words=6144;
            final int[] large=synthetic(words);
            final int[] smokeCcts={2400,4300,5550,7001};
            int[] last=null;
            for(int gamut=0;gamut<2;gamut++)for(int cct:smokeCcts) {
                int[] actual=nativePrepare(large,cct,gamut);
                if (same(actual,independentReference(large,words,cct,gamut))) {
                    fullSizePasses++;
                    last=actual;
                }
            }
            if(last!=null)fullSizeDigest=sha256LE(last);
            // Invalid gamut must fail safely without a fabricated success.
            if(nativePrepare(src,4300,2)!=null)error="invalid_gamut_was_accepted";
        } catch (Throwable t) {
            error=t.getClass().getSimpleName();
        }
        boolean pass=nativePasses==nativeCases && fullSizePasses==fullSizeCases && error.isEmpty();
        double ms=(System.nanoTime()-started)/1e6;
        return "{\"schema\":\"hasselblad-stage8-android-profile-diagnostic-v1\","
                +"\"status\":\""+(pass?"PASS":"NOT_PASSED")+"\","
                +"\"original_native_cases_passed\":"+nativePasses+","
                +"\"original_native_cases_total\":"+nativeCases+","
                +"\"fullsize_synthetic_cases_passed\":"+fullSizePasses+","
                +"\"fullsize_synthetic_cases_total\":"+fullSizeCases+","
                +"\"last_fullsize_synthetic_sha256_le\":\""+fullSizeDigest+"\","
                +"\"elapsed_ms\":"+String.format(Locale.US,"%.3f",ms)+","
                +"\"reason\":\""+error+"\","
                +"\"contains_camera_lut\":false,"
                +"\"photographic_colour_still_photon\":true,"
                +"\"hasselblad_wb_selected\":false,"
                +"\"pixel_lut_sampler_implemented\":false,"
                +"\"render_applied\":false}";
    }
}
