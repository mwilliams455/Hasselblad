import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.Arrays;
/** Run locally with owner-supplied inputs only. Never copy inputs into CI. */
public final class Stage43PrivateCheck {
    public static void main(String[] args)throws Exception {
        long start=System.nanoTime();
        var p=HasselbladDngTileReader.readPreview(new File(args[0]),1048576);
        var m=p.metadata;
        HasselbladProfile43 profile;
        HasselbladRenderBundle42 reference;
        try(var in=new FileInputStream(args[1])){profile=HasselbladProfile43.read(in);}
        try(var in=new FileInputStream(args[2])){reference=HasselbladRenderBundle42.read(in);}
        double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        short[] output=HasselbladRenderer42.render(p.cameraRgb16,profile.parameters(camera),profile.grid,profile.curve,profile.gridWidth,profile.gridHeight,1);
        if(!Arrays.equals(p.cameraRgb16,reference.input))throw new AssertionError("RAW input differs");
        if(!reference.matches(output))throw new AssertionError("Final RGB16 differs");
        if(!Arrays.equals(profile.display(output),reference.display(output)))throw new AssertionError("Display differs");
        if(!Arrays.equals(HasselbladProfile43.baseline(p.cameraRgb16,camera,HasselbladRenderer42.xyzToSrgb()),reference.baseline))throw new AssertionError("Baseline differs");
        String result="{\"schema\":\"hasselblad-stage43-private-host-check-v1\",\"status\":\"PASS_EXACT_RGB16\",\"pixels\":"+p.width*p.height+
            ",\"input_channels_exact\":"+p.cameraRgb16.length+",\"render_rgb16_exact\":true,\"display_rgb8_exact\":true,\"baseline_rgb8_exact\":true,"+
            "\"elapsed_milliseconds\":"+(System.nanoTime()-start)/1000000+",\"device_tested\":false,\"full_phocus_equivalence\":false}";
        Files.writeString(Path.of(args[3]),result+"\n");System.out.println(result);
    }
}
