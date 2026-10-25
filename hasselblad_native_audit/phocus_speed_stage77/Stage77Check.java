import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class Stage77Check {
    static void check(boolean ok,String what){if(!ok)throw new AssertionError(what);}
    public static void main(String[] args)throws Exception {
        long channels=0;Random random=new Random(7701);
        for(int[] shape:new int[][]{{128,129},{226,210},{320,128},{321,133},{322,194},{574,210},{577,259},{1088,194}}) {
            int w=shape[0],h=shape[1],ch=HasselbladFrame76.width(h);short[] raw=new short[w*h];
            for(int i=0;i<raw.length;i++)raw[i]=(short)random.nextInt(65536);
            short[] before=raw.clone();
            for(int y=0;y<ch;y+=64){short[] expected=HasselbladFrame76.band(raw,w,h,y);
                for(int workers:new int[]{1,4}){short[] actual=HasselbladFrame77.band(raw,w,h,y,workers);
                    check(Arrays.equals(expected,actual),"Compact wide/partial/parallel band mismatch");channels+=actual.length;}}
            check(Arrays.equals(raw,before),"Input mutated");
        }
        HasselbladFrame77.selfCheck(4);
        short[] input=new short[320*128],out=new short[256*64*3];Arrays.fill(out,(short)12345);
        for(int status:new int[]{HasselbladFrame77.renderBandNative(input,320,63,2,4,out),
            HasselbladFrame77.renderBandNative(input,320,0,64,0,out),HasselbladFrame77.renderBandNative(input,320,0,64,5,out),
            HasselbladFrame77.renderBandNative(new short[1],320,0,64,4,out),HasselbladFrame77.renderBandNative(input,320,0,64,4,input)})check(status!=0,"Invalid band accepted");
        for(short v:out)check(v==12345,"Rejected JNI call changed output");
        Thread.currentThread().interrupt();boolean cancelled=false;
        try{HasselbladFrame77.band(new short[128*128],128,128,0,4);}catch(IOException e){cancelled=true;}finally{Thread.interrupted();}
        check(cancelled,"Cancellation ignored");
        HasselbladProfile43 profile;
        try(InputStream f=Files.newInputStream(Path.of(args[0],"synthetic75.hbc"))){profile=HasselbladProfile43.read(f);}
        var metadata=HasselbladDngTileReader.readPrepared76(Path.of(args[0],"case0.dng").toFile()).metadata;
        double[] camera=HasselbladRenderer42.cameraToD50(metadata.forwardMatrix1,metadata.forwardMatrix2,metadata.calibration1,metadata.calibration2,metadata.analogBalance,metadata.asShotNeutral);
        int width=162,rows=64;short[] rgb=new short[width*rows*3];for(int i=0;i<rgb.length;i++)rgb[i]=(short)random.nextInt(65536);
        long previewCodes=0;
        for(int step:new int[]{1,2,3,4,5,7})for(int y:new int[]{0,64,128}) {
            short[] sampled=HasselbladPreview77.sample(rgb,width,y,rows,step);
            for(double[] grid:new double[][]{profile.grid,profile.gridAtTemperature(3550)}) {
                short[] whole=profile.finishRgb16(HasselbladRenderer42.render(rgb,profile.parameters(camera),grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
                short[] sparse=profile.finishRgb16(HasselbladRenderer42.render(sampled,profile.parameters(camera),grid,profile.curve,profile.gridWidth,profile.gridHeight,1));
                check(Arrays.equals(sparse,HasselbladPreview77.sample(whole,width,y,rows,step)),"Pointwise colour changed after sampling");previewCodes+=sparse.length;
            }
            int[] neutral=HasselbladProfile43.baseline(rgb,camera,HasselbladRenderer42.xyzToSrgb());
            int[] sparse=HasselbladProfile43.baseline(sampled,camera,HasselbladRenderer42.xyzToSrgb());
            int pw=(width+step-1)/step,ph=(y+rows+step-1)/step;int[] expected=new int[pw*ph],actual=new int[pw*ph];
            for(int sy=0;sy<rows;sy++)if((sy+y)%step==0)for(int x=0;x<width;x+=step)expected[((sy+y)/step)*pw+x/step]=neutral[sy*width+x];
            HasselbladPreview77.place(sparse,actual,width,y,rows,step);check(Arrays.equals(actual,expected),"Neutral preview coordinates changed");
        }
        check(HasselbladPreview77.sample(new short[9],3,1,1,4).length==0,"Empty preview band");
        HasselbladPreview77.place(new int[0],new int[1],3,1,1,4);
        System.out.println("STAGE77_JNI_EXACT "+channels+" channels; invalid buffers, input immutability, cancellation PASS");
        System.out.println("STAGE77_SPARSE_COLOUR_EXACT "+previewCodes+" RGB16 codes; neutral placement PASS");
    }
}
