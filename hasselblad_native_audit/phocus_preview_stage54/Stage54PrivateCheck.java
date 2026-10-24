import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Private local comparison only. Do not upload these input/output arrays. */
public final class Stage54PrivateCheck {
    static void save(Path path,short[] values)throws Exception {
        ByteBuffer b=ByteBuffer.allocate(values.length*2).order(ByteOrder.LITTLE_ENDIAN);
        for(short v:values)b.putShort(v);Files.write(path,b.array());
    }
    static void save(Path path,double[] values)throws Exception {
        ByteBuffer b=ByteBuffer.allocate(values.length*8).order(ByteOrder.LITTLE_ENDIAN);
        for(double v:values)b.putDouble(v);Files.write(path,b.array());
    }
    public static void main(String[] args)throws Exception {
        Path out=Path.of(args[2]);Files.createDirectories(out);
        long start=System.nanoTime();
        var p=HasselbladDngTileReader.readPreview(new File(args[0]),1048576);var m=p.metadata;
        HasselbladProfile43 look;
        try(var in=new FileInputStream(args[1])){look=HasselbladProfile43.read(in);}
        double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        short[] before=p.cameraRgb16.clone();double[] matrixBefore=camera.clone();
        var plan=HasselbladPreparedHighlight54.prepare(camera,m.asShotNeutral);
        long prepared=System.nanoTime();
        short[] highlight=plan.reconstruct(p.cameraRgb16);
        long recovered=System.nanoTime();
        double[] params=look.parameters(plan.afterMatrix);
        short[] original=HasselbladRenderer42.render(p.cameraRgb16,look.parameters(camera),look.grid,look.curve,look.gridWidth,look.gridHeight,1);
        short[] adjusted=HasselbladRenderer42.render(highlight,params,look.grid,look.curve,look.gridWidth,look.gridHeight,1);
        if(!Arrays.equals(before,p.cameraRgb16)||!Arrays.equals(camera,matrixBefore))throw new AssertionError("input mutated");
        save(out.resolve("camera_rgb16.bin"),p.cameraRgb16);save(out.resolve("camera_to_d50.bin"),camera);
        save(out.resolve("gains.bin"),plan.gainRatios);save(out.resolve("after_matrix.bin"),plan.afterMatrix);
        save(out.resolve("highlight_input_rgb16.bin"),highlight);save(out.resolve("highlight_params.bin"),params);
        save(out.resolve("original_rgb16.bin"),original);save(out.resolve("highlight_rgb16.bin"),adjusted);
        int[] originalDisplay=look.display(original),highlightDisplay=look.display(adjusted);
        ByteBuffer displays=ByteBuffer.allocate(originalDisplay.length*8).order(ByteOrder.LITTLE_ENDIAN);
        for(int v:originalDisplay)displays.putInt(v);for(int v:highlightDisplay)displays.putInt(v);
        Files.write(out.resolve("display_argb.bin"),displays.array());
        long ceiling=0,changed=0;for(int i=0;i<original.length;i++) {
            if((p.cameraRgb16[i]&65535)==65535)ceiling++;
            if(original[i]!=adjusted[i])changed++;
        }
        String receipt="{\"schema\":\"hasselblad-stage54-private-host-v1\",\"status\":\"RENDERED_FOR_INDEPENDENT_CHECK\",\"pixels\":"+p.width*p.height+
            ",\"width\":"+p.width+",\"height\":"+p.height+",\"orientation\":"+p.orientation+
            ",\"gainmap_count\":"+m.gainMapCount+",\"prepared_ceiling_channels\":"+ceiling+
            ",\"changed_colour_channels\":"+changed+",\"analytic_equal_gain_limit\":"+plan.analyticEqualGainLimit+
            ",\"highlight_milliseconds\":"+(recovered-prepared)/1000000+
            ",\"elapsed_milliseconds\":"+(System.nanoTime()-start)/1000000+
            ",\"input_unchanged\":true,\"device_tested\":false,\"full_phocus_equivalence\":false}";
        Files.writeString(out.resolve("HOST_RENDER54.json"),receipt+"\n");System.out.println(receipt);
    }
}
