import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Local private inputs and arrays only; public receipt has aggregate checks. */
public final class Stage56PrivateCheck {
    static void save(Path p,short[] a)throws Exception {
        var b=ByteBuffer.allocate(a.length*2).order(ByteOrder.LITTLE_ENDIAN);
        for(short v:a)b.putShort(v);Files.write(p,b.array());
    }
    static void save(Path p,double[] a)throws Exception {
        var b=ByteBuffer.allocate(a.length*8).order(ByteOrder.LITTLE_ENDIAN);
        for(double v:a)b.putDouble(v);Files.write(p,b.array());
    }
    public static void main(String[] args)throws Exception {
        Path out=Path.of(args[2]),nativeGrids=Path.of(args[3]),previous=Path.of(args[4]);Files.createDirectories(out);
        var preview=HasselbladDngTileReader.readPreview(new File(args[0]),1048576);var m=preview.metadata;
        HasselbladProfile43 look;try(var in=new FileInputStream(args[1])){look=HasselbladProfile43.read(in);}
        if(m.illuminant.error!=null)throw new AssertionError(m.illuminant.error);
        var selection=HasselbladIlluminant56.estimate(m.illuminant.colorMatrix1,m.illuminant.colorMatrix2,
            m.illuminant.light1,m.illuminant.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        double error=0;int count=0;
        for(int t:new int[]{2000,2400,2850,3050,3550,4000,5550,6500,8000,9100,10000}) {
            var b=ByteBuffer.wrap(Files.readAllBytes(nativeGrids.resolve("grid_"+t+".bin"))).order(ByteOrder.LITTLE_ENDIAN);
            double[] grid=look.gridAtTemperature(t);if(b.remaining()!=grid.length*8)throw new AssertionError("grid size");
            for(double v:grid){error=Math.max(error,Math.abs(v-b.getDouble()));count++;}
        }
        if(error>1e-12)throw new AssertionError("grid precision "+error);
        double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        var plan=HasselbladPreparedHighlight54.prepare(camera,m.asShotNeutral);
        short[] input=plan.reconstruct(preview.cameraRgb16);double[] params=look.parameters(plan.afterMatrix);
        short[] manual=HasselbladRenderer42.render(input,params,look.grid,look.curve,look.gridWidth,look.gridHeight,1);
        short[] manualFinished=look.finishRgb16(manual);
        save(out.resolve("manual_rgb16.bin"),manual);save(out.resolve("manual_finished_rgb16.bin"),manualFinished);
        if(!Arrays.equals(Files.readAllBytes(out.resolve("manual_rgb16.bin")),Files.readAllBytes(previous.resolve("room/highlight_rgb16.bin")))||
            !Arrays.equals(Files.readAllBytes(out.resolve("manual_finished_rgb16.bin")),Files.readAllBytes(previous.resolve("output_rgb16.bin"))))
            throw new AssertionError("manual preview changed");
        double[] grid=look.gridAtTemperature(selection.lutKelvin);long start=System.nanoTime();
        short[] auto=HasselbladRenderer42.render(input,params,grid,look.curve,look.gridWidth,look.gridHeight,1);
        short[] gradation=HasselbladRenderer42.defaultGradation(auto),finished=look.finishRgb16(auto);
        save(out.resolve("input_rgb16.bin"),input);save(out.resolve("params.bin"),params);save(out.resolve("grid.bin"),grid);
        save(out.resolve("auto_rgb16.bin"),auto);save(out.resolve("auto_gradation_rgb16.bin"),gradation);save(out.resolve("auto_finished_rgb16.bin"),finished);
        String receipt="{\"schema\":\"hasselblad-stage56-private-host-v1\",\"status\":\"RENDERED_FOR_INDEPENDENT_CHECK\",\"pixels\":"+auto.length/3+
            ",\"metadata_kelvin\":"+selection.kelvin+",\"metadata_tint_diagnostic\":"+selection.tint+
            ",\"native_quantized_kelvin\":"+selection.nativeKelvin+",\"lut_kelvin\":"+selection.lutKelvin+
            ",\"iterations\":"+selection.iterations+",\"neutral_ratio_residual\":"+selection.residual+
            ",\"grid_values_checked\":"+count+",\"grid_max_absolute_difference\":"+error+
            ",\"manual_colour_and_finishing_unchanged_exact\":true,\"auto_render_milliseconds\":"+(System.nanoTime()-start)/1000000+
            ",\"device_tested\":false,\"scene_fitted_parameters\":0,\"full_phocus_equivalence\":false}";
        Files.writeString(out.resolve("HOST_RENDER56.json"),receipt+"\n");System.out.println(receipt);
    }
}
