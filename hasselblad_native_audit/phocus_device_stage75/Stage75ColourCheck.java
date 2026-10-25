import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
/** Wiring check with synthetic profile only; no physical colour-match assertion. */
public final class Stage75ColourCheck {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);HasselbladProfile43 profile;
        try(InputStream in=Files.newInputStream(root.resolve("synthetic75.hbc"))){profile=HasselbladProfile43.read(in);}
        int count=0;
        for(int r=0;r<5;r++) {
            var tile=HasselbladDngTileReader.readBounded75(root.resolve("case0.dng").toFile(),r);var m=tile.metadata;
            short[] rgb=HasselbladDevice75Buffers.render(tile.bayer,64,64),before=rgb.clone();
            double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            int[] neutral=HasselbladProfile43.baseline(rgb,camera,HasselbladRenderer42.xyzToSrgb());
            short[] manual=profile.finishRgb16(HasselbladRenderer42.render(rgb,profile.parameters(camera),profile.grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
            var im=m.illuminant;var selection=HasselbladIlluminant56.estimate(im.colorMatrix1,im.colorMatrix2,im.light1,im.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] grid=profile.gridAtTemperature(selection.lutKelvin);
            short[] automatic=profile.finishRgb16(HasselbladRenderer42.render(rgb,profile.parameters(camera),grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
            short[] repeat=profile.finishRgb16(HasselbladRenderer42.render(rgb,profile.parameters(camera),grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
            if(neutral.length!=4096||manual.length!=12288||automatic.length!=12288||HasselbladProfile43.srgb16ToArgb(automatic).length!=4096)throw new AssertionError("Colour shape");
            if(!Arrays.equals(rgb,before)||!Arrays.equals(repeat,automatic))throw new AssertionError("Mutation/repeat");
            if(Arrays.equals(profile.grid,grid))throw new AssertionError("Selected grid was not applied");
            count++;
        }
        System.out.println("STAGE75_SYNTHETIC_COLOUR_PASS: "+count+" demosaic -> neutral/manual LUT/automatic LUT -> finishing -> display cases; not physical colour validation");
    }
}
