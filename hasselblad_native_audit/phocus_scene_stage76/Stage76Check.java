import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class Stage76Check {
    private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    public static void main(String[] args)throws Exception {
        Path fixtures=Path.of(args[0]);int sites=0;
        for(int c=0;c<4;c++) {
            File file=fixtures.resolve("case"+c+".dng").toFile();byte[] original=Files.readAllBytes(file.toPath());
            var full=HasselbladDngTileReader.readPrepared76(file);int stride=full.metadata.width;
            for(int region=0;region<5;region++) {
                var tile=HasselbladDngTileReader.readBounded75(file,region);
                for(int y=0;y<128;y++)for(int x=0;x<128;x++) {
                    check(full.bayer[(tile.y-32+y)*stride+tile.x-32+x]==tile.bayer[y*128+x],"Prepared frame differs from Stage75");sites++;
                }
            }
            check(Arrays.equals(original,Files.readAllBytes(file.toPath())),"Input DNG changed");
        }
        HasselbladFrame76.selfCheck();int channels=0;
        for(int[] size:new int[][]{{128,128},{129,133},{160,178},{226,210},{254,194},{257,259}}) {
            int w=size[0],h=size[1],cw=HasselbladFrame76.width(w),ch=HasselbladFrame76.width(h);short[] raw=new short[w*h];
            for(int y=0;y<h;y++)for(int x=0;x<w;x++)raw[y*w+x]=(short)((x*491+y*151+(x*y)%2891)&65535);
            short[] original=raw.clone();
            for(int y=0;y<ch;y+=64) {
                short[] band=HasselbladFrame76.band(raw,w,h,y);int rows=Math.min(64,ch-y),ay=Math.min(y,ch-64);
                for(int x=0;x<cw;x+=64) {
                    int ax=Math.min(x,cw-64),cols=Math.min(64,cw-x);short[] tile=new short[128*128];
                    for(int yy=0;yy<128;yy++)System.arraycopy(raw,(ay+yy)*w+ax,tile,yy*128,128);
                    short[] expected=HasselbladDevice75Buffers.render(tile,64,64);
                    for(int yy=0;yy<rows;yy++)for(int xx=0;xx<cols;xx++)for(int k=0;k<3;k++) {
                        check(band[(yy*cw+x+xx)*3+k]==expected[((yy+y-ay)*64+x-ax+xx)*3+k],"Band coordinate/partial tile mismatch");channels++;
                    }
                }
            }
            check(Arrays.equals(raw,original),"Frame input mutated");
        }
        short[] in=new short[128*128],out=new short[64*64*3];Arrays.fill(out,(short)12345);
        for(int status:new int[]{HasselbladFrame76.renderBandNative(in,128,63,2,out),
            HasselbladFrame76.renderBandNative(in,127,0,64,out),HasselbladFrame76.renderBandNative(new short[1],128,0,64,out),
            HasselbladFrame76.renderBandNative(in,128,0,64,new short[1]),HasselbladFrame76.renderBandNative(in,128,0,64,in)})check(status!=0,"Bad band accepted");
        for(short v:out)check(v==12345,"Rejected band changed output");
        Thread.currentThread().interrupt();boolean cancelled=false;
        try{HasselbladFrame76.band(in,128,128,0);}catch(IOException e){cancelled=true;}finally{Thread.interrupted();}
        check(cancelled,"Band cancellation ignored");
        for(String bad:new String[]{"bad_cfa","compressed","crop","short_file","small","opcode","dual","white"}){
            boolean rejected=false;try{HasselbladDngTileReader.readPrepared76(fixtures.resolve(bad+".dng").toFile());}catch(IOException e){rejected=true;}
            check(rejected,"Unsupported frame DNG accepted: "+bad);
        }
        var frame=HasselbladDngTileReader.readPrepared76(fixtures.resolve("case0.dng").toFile());var metadata=frame.metadata;
        int rw=metadata.width,rh=metadata.height,ow=HasselbladFrame76.width(rw),oh=HasselbladFrame76.width(rh);
        short[] scene=new short[ow*oh*3];
        for(int y=0;y<oh;y+=64){short[] b=HasselbladFrame76.band(frame.bayer,rw,rh,y);System.arraycopy(b,0,scene,y*ow*3,b.length);}
        HasselbladProfile43 profile;try(InputStream profileInput=Files.newInputStream(fixtures.resolve("synthetic75.hbc"))){profile=HasselbladProfile43.read(profileInput);}
        double[] camera=HasselbladRenderer42.cameraToD50(metadata.forwardMatrix1,metadata.forwardMatrix2,metadata.calibration1,metadata.calibration2,metadata.analogBalance,metadata.asShotNeutral);
        for(double[] grid:new double[][]{profile.grid,profile.gridAtTemperature(3550)}) {
            short[] whole=profile.finishRgb16(HasselbladRenderer42.render(scene,profile.parameters(camera),grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
            for(int y=0;y<oh;y+=64){int count=Math.min(64,oh-y)*ow*3;short[] part=Arrays.copyOfRange(scene,y*ow*3,y*ow*3+count);
                short[] actual=profile.finishRgb16(HasselbladRenderer42.render(part,profile.parameters(camera),grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
                check(Arrays.equals(actual,Arrays.copyOfRange(whole,y*ow*3,y*ow*3+count)),"Colour batching seam");}
        }
        System.out.println("STAGE76_COLOUR_STRIPS_PASS: "+(2*scene.length)+" manual/automatic finished RGB16 codes equal unpartitioned colour execution");
        System.out.println("STAGE76_JVM_PASS: "+sites+" prepared Bayer sites; "+channels+" assembled RGB16 channels; odd/partial geometries, rejection and cancellation checks");
    }
}
