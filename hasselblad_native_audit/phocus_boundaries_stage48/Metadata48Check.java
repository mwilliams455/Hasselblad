import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

public final class Metadata48Check {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);int checks=0;
        ArrayList<String> failures=new ArrayList<>();
        for(String line:Files.readAllLines(root.resolve("manifest.tsv"))) {
            String[] f=line.split("\t");String name=f[0],expected=f[1];
            double[] matrix=new double[9];ByteBuffer b=ByteBuffer.wrap(Files.readAllBytes(root.resolve(name+".matrix"))).order(ByteOrder.LITTLE_ENDIAN);
            for(int i=0;i<9;i++)matrix[i]=b.getDouble();
            for(boolean preview:new boolean[]{false,true}) {
                checks++;String label=name+(preview?"_preview":"_tile");
                try {
                    File file=root.resolve(name+".dng").toFile();
                    var m=preview?HasselbladDngTileReader.readPreview(file,4096).metadata:HasselbladDngTileReader.read(file);
                    if(!expected.equals("OK"))throw new AssertionError("accepted unsupported metadata");
                    if((m.calibration1!=null)!=f[2].equals("1"))throw new AssertionError("wrong calibration selection");
                    double[] actual=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
                    for(int i=0;i<9;i++)if(Math.abs(actual[i]-matrix[i])>1e-12)throw new AssertionError("independent matrix mismatch");
                } catch(HasselbladDngTileReader.Unsupported e) {
                    if(!e.code.equals(expected))failures.add(label+":"+e.code);
                } catch(Exception|AssertionError e) {failures.add(label+":"+e.getClass().getSimpleName());}
            }
        }
        String quoted=String.join(",",failures.stream().map(s->"\""+s+"\"").toArray(String[]::new));
        System.out.println("{\"schema\":\"hasselblad-stage48-java-metadata-v1\",\"status\":\""+(failures.isEmpty()?"PASS":"EXPECTED_OLD_FAILURES")+"\",\"checks\":"+checks+",\"failures\":["+quoted+"],\"synthetic_only\":true}");
        if(!failures.isEmpty()&&(args.length<2||!args[1].equals("--allow-old-failures")))throw new AssertionError("Metadata checks failed");
    }
}
