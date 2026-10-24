import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Local private arrays only; receipt contains aggregate counts. */
public final class Stage55PrivateCheck {
    static short[] read(Path p)throws Exception {
        var b=ByteBuffer.wrap(Files.readAllBytes(p)).order(ByteOrder.LITTLE_ENDIAN);
        short[] out=new short[b.remaining()/2];b.asShortBuffer().get(out);return out;
    }
    public static void main(String[] args)throws Exception {
        Path dir=Path.of(args[1]),oracle=Path.of(args[2]);
        HasselbladProfile43 profile;
        try(var in=new FileInputStream(args[0])){profile=HasselbladProfile43.read(in);}
        short[] input=read(dir.resolve("highlight_rgb16.bin")),before=input.clone();
        long start=System.nanoTime();
        short[] grad=HasselbladRenderer42.defaultGradation(input),output=profile.finishRgb16(input);
        if(!Arrays.equals(input,before)||!Arrays.equals(grad,read(oracle.resolve("gradation_rgb16.bin")))||
            !Arrays.equals(output,read(oracle.resolve("output_rgb16.bin"))))throw new AssertionError("full-frame native bridge mismatch");
        int[] packed=HasselbladProfile43.srgb16ToArgb(output);
        var bytes=ByteBuffer.allocate(packed.length*4).order(ByteOrder.LITTLE_ENDIAN);for(int v:packed)bytes.putInt(v);
        Files.write(dir.resolve("finished_argb.bin"),bytes.array());
        System.out.println("{\"status\":\"PASS_EXACT_JNI_RGB16\",\"pixels\":"+input.length/3+
            ",\"gradation_channels_exact\":"+grad.length+",\"output_channels_exact\":"+output.length+
            ",\"elapsed_milliseconds\":"+(System.nanoTime()-start)/1000000+",\"input_unchanged\":true,\"device_tested\":false}");
    }
}
