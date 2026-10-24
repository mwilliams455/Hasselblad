import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;import java.nio.*;import java.nio.file.*;import java.util.*;
/** Selected private DNG execution check. No image-dependent fitted parameters. */
public final class Stage58DngCheck {
 public static void main(String[] args)throws Exception {
  var p=HasselbladDngTileReader.readPreviewWithPreparation58(new File(args[0]),1048576);var m=p.metadata;var a=p.preparation58;
  HasselbladProfile43 look;try(var in=new FileInputStream(args[1])){look=HasselbladProfile43.read(in);}
  var im=m.illuminant;var selection=HasselbladIlluminant56.estimate(im.colorMatrix1,im.colorMatrix2,im.light1,im.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
  double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
  double[] params=look.parameters(camera),grid=look.gridAtTemperature(selection.lutKelvin);
  short[] old=look.finishRgb16(HasselbladRenderer42.render(p.cameraRgb16,params,grid,look.curve,look.gridWidth,look.gridHeight,1));
  if(!Arrays.equals(Stage58Check.shorts(old),Files.readAllBytes(Path.of(args[3]))))throw new AssertionError("Stage57 comparison changed");
  short[] colour=HasselbladRenderer42.render(a.rgb16,params,grid,look.curve,look.gridWidth,look.gridHeight,1),finished=look.finishRgb16(colour);
  Path out=Path.of(args[2]);Files.createDirectories(out);
  Stage57Check.save(out.resolve("raw.bin"),a.rgb16);Stage57Check.save(out.resolve("legacy_raw.bin"),p.cameraRgb16);
  Stage57Check.save(out.resolve("params.bin"),params);Stage57Check.save(out.resolve("colour.bin"),colour);Stage57Check.save(out.resolve("finished.bin"),finished);
  Files.write(out.resolve("unclamped.bin"),Stage58Check.floats(a.unclampedRgb));Files.write(out.resolve("counters.bin"),Stage58Check.longs(a.counters()));
  int[] first=HasselbladProfile43.srgb16ToArgb(old),second=HasselbladProfile43.srgb16ToArgb(finished);
  int max=0;long changed=0,overTwo=0,sum=0;
  for(int i=0;i<first.length;i++){int pm=0;for(int shift:new int[]{16,8,0}){int d=Math.abs(((first[i]>>>shift)&255)-((second[i]>>>shift)&255));pm=Math.max(pm,d);sum+=d;}max=Math.max(max,pm);if(pm>0)changed++;if(pm>2)overTwo++;}
  String report="{\"schema\":\"hasselblad-stage58-saved-dng-host-v1\",\"status\":\"PASS_HOST_INTEGRATION\",\"pixels\":"+first.length+",\"selected_lut_temperature\":"+selection.lutKelvin+
   ",\"stage57_automatic_colour_only_unchanged_exact\":true,\"comparison_max_rgb8_difference\":"+max+",\"comparison_mean_abs_rgb8_difference\":"+(double)sum/(first.length*3L)+
   ",\"comparison_changed_pixels\":"+changed+",\"comparison_pixels_over_two_codes\":"+overTwo+",\"unequal_black_levels\":"+a.unequalBlackLevels+",\"scene_fitted_parameters\":0,\"headroom_recovered\":false,\"difference_is_accuracy_score\":false,\"device_tested\":false}";
  Files.writeString(out.resolve("SAVED_DNG58.json"),report+"\n");System.out.println(report);
 }
}
