import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;import java.nio.*;import java.nio.file.*;import java.util.*;

/** Private same-DNG integration only; no photograph is used to fit parameters. */
public final class Stage57DngCheck {
    public static void main(String[] args)throws Exception {
        var preview=HasselbladDngTileReader.readPreview(new File(args[0]),1048576);var m=preview.metadata;
        HasselbladProfile43 look;try(var in=new FileInputStream(args[1])){look=HasselbladProfile43.read(in);}
        var im=m.illuminant;if(im.error!=null)throw new AssertionError(im.error);
        var selection=HasselbladIlluminant56.estimate(im.colorMatrix1,im.colorMatrix2,im.light1,im.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        var plan=HasselbladPreparedHighlight54.prepare(camera,m.asShotNeutral);double[] grid=look.gridAtTemperature(selection.lutKelvin);
        short[] highlighted=HasselbladRenderer42.render(plan.reconstruct(preview.cameraRgb16),look.parameters(plan.afterMatrix),grid,look.curve,look.gridWidth,look.gridHeight,1);
        short[] original=look.finishRgb16(highlighted);
        Path out=Path.of(args[2]);Files.createDirectories(out);Stage57Check.save(out.resolve("existing_finished.bin"),original);
        if(!Arrays.equals(Files.readAllBytes(out.resolve("existing_finished.bin")),Files.readAllBytes(Path.of(args[3]))))throw new AssertionError("Stage56 view changed");
        double[] params=look.parameters(camera);short[] direct=HasselbladRenderer42.render(preview.cameraRgb16,params,grid,look.curve,look.gridWidth,look.gridHeight,1);
        short[] finished=look.finishRgb16(direct);
        Stage57Check.save(out.resolve("raw.bin"),preview.cameraRgb16);Stage57Check.save(out.resolve("params.bin"),params);
        Stage57Check.save(out.resolve("colour.bin"),direct);Stage57Check.save(out.resolve("finished.bin"),finished);
        int[] a=HasselbladProfile43.srgb16ToArgb(original),b=HasselbladProfile43.srgb16ToArgb(finished);
        long total=0,changed=0,overTwo=0;int maximum=0;
        for(int i=0;i<a.length;i++) {
            int pixelMax=0;for(int shift:new int[]{16,8,0}) {
                int d=Math.abs(((a[i]>>>shift)&255)-((b[i]>>>shift)&255));total+=d;maximum=Math.max(maximum,d);pixelMax=Math.max(pixelMax,d);
            }
            if(pixelMax>0)changed++;if(pixelMax>2)overTwo++;
        }
        String receipt="{\"schema\":\"hasselblad-stage57-saved-dng-host-v1\",\"status\":\"PASS_HOST_INTEGRATION\",\"pixels\":"+a.length+
            ",\"selected_lut_temperature\":"+selection.lutKelvin+",\"stage56_existing_automatic_view_unchanged_exact\":true"+
            ",\"comparison_max_rgb8_difference\":"+maximum+",\"comparison_mean_abs_rgb8_difference\":"+(double)total/(a.length*3L)+
            ",\"comparison_changed_pixels\":"+changed+",\"comparison_pixels_over_two_codes\":"+overTwo+
            ",\"difference_is_accuracy_score\":false,\"scene_fitted_parameters\":0,\"device_tested\":false}";
        Files.writeString(out.resolve("SAVED_DNG57.json"),receipt+"\n");System.out.println(receipt);
    }
}
