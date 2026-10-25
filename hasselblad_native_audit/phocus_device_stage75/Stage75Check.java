import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class Stage75Check {
    public static void main(String[] args)throws Exception {
        Path assets=Path.of(args[0]),fixtures=Path.of(args[1]);int channels=0,regions=0;
        String[] names={"neutral64","colour64","random23"};int[] ws={64,64,23},hs={64,64,31};
        for(int i=0;i<names.length;i++) {
            int w=ws[i],h=hs[i];short[] in,expected;
            try(InputStream a=Files.newInputStream(assets.resolve(names[i]+".input.u16le"));InputStream b=Files.newInputStream(assets.resolve(names[i]+".rgb.u16le"))) {
                in=HasselbladDevice75Buffers.decode(a,(w+64)*(h+64));expected=HasselbladDevice75Buffers.decode(b,w*h*3);
            }
            short[] out=HasselbladDevice75Buffers.render(in,w,h);
            if(!Arrays.equals(out,expected))throw new AssertionError("JNI RGB mismatch "+names[i]);
            if(!Arrays.equals(out,HasselbladDevice75Buffers.render(in,w,h)))throw new AssertionError("repeat");channels+=out.length;
        }
        HasselbladDevice75Buffers.rejectionChecks();
        for(int caseId=0;caseId<4;caseId++)for(int region=0;region<5;region++) {
            Path p=fixtures.resolve("case"+caseId+".dng");byte[] before=Files.readAllBytes(p);
            var tile=HasselbladDngTileReader.readBounded75(p.toFile(),region);
            if(!Arrays.equals(before,Files.readAllBytes(p)))throw new AssertionError("DNG changed");
            if((tile.x&1)!=0||(tile.y&1)!=0)throw new AssertionError("CFA phase");
            if(!Arrays.equals(HasselbladDevice75Buffers.encode(tile.bayer),Files.readAllBytes(fixtures.resolve("case"+caseId+"-"+region+".input.u16le"))))throw new AssertionError("Prepared Bayer mismatch case "+caseId+" region "+region);
            HasselbladDevice75Buffers.render(tile.bayer,64,64);regions++;
        }
        for(String name:new String[]{"bad_cfa","compressed","crop","short_file","small","opcode","dual","white"}) {
            boolean rejected=false;try{HasselbladDngTileReader.readBounded75(fixtures.resolve(name+".dng").toFile(),0);}catch(IOException e){rejected=true;}
            if(!rejected)throw new AssertionError("Malformed DNG accepted: "+name);
        }
        Thread.currentThread().interrupt();boolean cancelled=false;
        try{HasselbladDngTileReader.readBounded75(fixtures.resolve("case0.dng").toFile(),0);}catch(IOException e){cancelled=true;}finally{Thread.interrupted();}
        if(!cancelled)throw new AssertionError("Cancellation ignored");
        for(byte[] malformed:new byte[][]{new byte[1],new byte[3],new byte[6]}){
            boolean rejected=false;try{HasselbladDevice75Buffers.decode(new ByteArrayInputStream(malformed),2);}catch(IOException e){rejected=true;}
            if(!rejected)throw new AssertionError("Malformed fixture accepted");}
        System.out.println("STAGE75_PASS: "+channels+" JNI codes; "+regions+" independent prepared Bayer tiles; 8 malformed DNGs; cancellation; unsigned LE export; repeat and rejection checks");
    }
}
