import java.io.File;
import com.particlesdevs.photoncamera.hasselblad.HasselbladDngTileReader;

public final class Stage32DngTileSmoke {
    static int passed=0;
    static void test(boolean yes, String label) {
        if (!yes)throw new AssertionError(label);
        passed++;
    }
    static void close(double actual, double wanted, String label){
        test(Double.isFinite(actual)&&Math.abs(actual-wanted)<1e-6,label+" actual="+actual+" wanted="+wanted);
    }
    static void rejected(File f,String reason)throws Exception{
        try{HasselbladDngTileReader.read(f);throw new AssertionError("accepted "+reason);}
        catch(HasselbladDngTileReader.Unsupported ex){test(reason.equals(ex.code),reason+" got "+ex.code);}
    }
    public static void main(String[] args)throws Exception {
        File folder=new File(args[0]);
        var plain=HasselbladDngTileReader.read(new File(folder,"plain.dng"));
        test(plain.width==64&&plain.height==64,"dimensions");
        test(plain.originalBits==16&&plain.stripCount==1,"strips");
        test("absent_not_shading_calibrated".equals(plain.gainState),"gain absence not claimed corrected");
        test(plain.gainMapCount==0 && plain.gainAppliedSamples==0,"plain no gains");
        test(plain.cameraLinearTile.length==3072,"native tile bounded 1024 pixels");
        test(plain.hasPcsInput(),"DNG fm and neutral paired");
        close(plain.cameraLinearTile[0],(300.-64)/(1023-64),"red CFA own-site fidelity");
        close(plain.cameraLinearTile[1],((400.-65)/(1023-65)+(450.-66)/(1023-66))/2,"interpolated G at red site");
        close(plain.cameraLinearTile[4],(400.-65)/(1023-65),"green1 original CFA sample preserved");
        close(plain.cameraLinearTile[32*3+1],(450.-66)/(1023-66),"green2 original CFA sample preserved");
        close(plain.cameraLinearTile[2],(500.-67)/(1023-67),"blue on red site neighbors");
        var gain=HasselbladDngTileReader.read(new File(folder,"gains.dng"));
        test(gain.gainMapCount==4&&gain.gainAppliedSamples>0,"4 gainmaps applied to separate CFA sites");
        close(gain.cameraLinearTile[0],(300.-64)/(1023-64)*2,"gain red");
        close(gain.cameraLinearTile[1],((400.-65)/(1023-65)*1.1+(450.-66)/(1023-66)*1.2)/2,"gain green interpolation");
        close(gain.cameraLinearTile[4],(400.-65)/(1023-65)*1.1,"gain green1 original");
        close(gain.cameraLinearTile[32*3+1],(450.-66)/(1023-66)*1.2,"gain green2 original");
        close(gain.cameraLinearTile[2],(500.-67)/(1023-67)*1.5,"gain blue");
        var big=HasselbladDngTileReader.read(new File(folder,"big.dng"));
        test(big.width==64&&big.gainMapCount==4,"big-endian classic TIFF");
        close(big.cameraLinearTile[0],gain.cameraLinearTile[0],"endian parity red");
        close(big.cameraLinearTile[1],gain.cameraLinearTile[1],"endian parity green");
        rejected(new File(folder,"bad_cfa.dng"),"unsupported_CFA_not_RGGB");
        rejected(new File(folder,"bad_strip.dng"),"tiff_offset_outside_file");
        rejected(new File(folder,"unsupported_opcode.dng"),"unsupported_opcode2_id");
        var dual=HasselbladDngTileReader.read(new File(folder,"dual_mismatch.dng"));
        test(dual.forwardMatrix1[0]!=dual.forwardMatrix2[0],"preserve mismatched dual illuminant for native refusal");
        test(dual.cameraLinearTile.length==3072,"dual metadata does not corrupt raw read");
        System.out.println("{\"schema\":\"hasselblad-stage32-dng-tile-host-v1\",\"status\":\"PASS\",\"checks\":"+passed+",\"native_stage24_called\":false,\"original_images_used\":false,\"hncs_pixel_equivalence_proven\":false}");
    }
}
