import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

/** Private inputs/outputs only; reproduce the installed Stage43 DNG viewer. */
public final class Stage46PrivateDump {
    static void shorts(Path path,short[] values)throws Exception {
        var b=ByteBuffer.allocate(values.length*2).order(ByteOrder.LITTLE_ENDIAN);
        for(short v:values)b.putShort(v);Files.write(path,b.array());
    }
    static void doubles(Path path,double[] values)throws Exception {
        var b=ByteBuffer.allocate(values.length*8).order(ByteOrder.LITTLE_ENDIAN);
        for(double v:values)b.putDouble(v);Files.write(path,b.array());
    }
    static void png(Path path,int[] pixels,int w,int h,int orientation)throws Exception {
        if(orientation!=6)throw new IllegalArgumentException("This scene audit expects orientation 6");
        var im=new BufferedImage(h,w,BufferedImage.TYPE_INT_RGB);
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)im.setRGB(h-1-y,x,pixels[y*w+x]);
        ImageIO.write(im,"png",path.toFile());
    }
    public static void main(String[] a)throws Exception {
        if(a.length!=5)throw new IllegalArgumentException("Expected DNG, output directory and three private profiles");
        Path out=Path.of(a[1]);Files.createDirectories(out);
        var p=HasselbladDngTileReader.readPreview(new File(a[0]),1048576);var m=p.metadata;
        if(m.width!=4096 || m.height!=3072 || p.width!=1024 || p.height!=768 || p.orientation!=6)
            throw new IllegalArgumentException("This scene audit expects a 4096x3072 DNG with orientation 6");
        double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
        shorts(out.resolve("camera_rgb16.bin"),p.cameraRgb16);
        doubles(out.resolve("camera_to_d50.bin"),camera);
        doubles(out.resolve("xyz_to_srgb.bin"),HasselbladRenderer42.xyzToSrgb());
        png(out.resolve("baseline.png"),HasselbladProfile43.baseline(p.cameraRgb16,camera,HasselbladRenderer42.xyzToSrgb()),p.width,p.height,p.orientation);
        for(int i=2;i<a.length;i++) {
            HasselbladProfile43 profile;try(var in=new FileInputStream(a[i])){profile=HasselbladProfile43.read(in);}
            String name="curve"+profile.film+"_"+profile.temperature;
            var params=profile.parameters(camera);
            short[] rendered=HasselbladRenderer42.render(p.cameraRgb16,params,profile.grid,profile.curve,profile.gridWidth,profile.gridHeight,1);
            shorts(out.resolve(name+"_rgb16.bin"),rendered);doubles(out.resolve(name+"_params.bin"),params);
            png(out.resolve(name+".png"),profile.display(rendered),p.width,p.height,p.orientation);
        }
        String result="{\"schema\":\"hasselblad-stage46-java-dng-dump-v1\",\"raw_width\":"+m.width+",\"raw_height\":"+m.height+
            ",\"width\":"+p.width+",\"height\":"+p.height+",\"step\":"+p.step+",\"orientation\":"+p.orientation+
            ",\"input_negative_channels\":"+p.negativeChannels+",\"input_over_unity_channels\":"+p.overUnityChannels+
            ",\"gainmap_count\":"+m.gainMapCount+",\"device_tested\":false}";
        Files.writeString(out.resolve("STAGE46_JAVA_DUMP.json"),result+"\n");System.out.println(result);
    }
}
