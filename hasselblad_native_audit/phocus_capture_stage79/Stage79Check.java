import com.particlesdevs.photoncamera.hasselblad.*;
import com.particlesdevs.photoncamera.processing.encoder.ImageFormatConfig;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

public final class Stage79Check {
    static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
    interface Attempt{void run()throws Exception;}
    static void reject(Attempt attempt)throws Exception{boolean rejected=false;try{attempt.run();}catch(IOException e){rejected=true;}check(rejected,"Invalid operation accepted");}
    public static void main(String[] args)throws Exception {
        Path work=Path.of(args[0]), fixtures=work.resolve("fixtures");
        HasselbladProfile43 profile;
        try(InputStream in=Files.newInputStream(fixtures.resolve("synthetic75.hbc"))){profile=HasselbladProfile43.read(in);}
        long pixels=0, rgbCodes=0;
        for(int index=0;index<10;index++) {
            File file=fixtures.resolve("prep78-"+index+".dng").toFile();
            // Independent previous preparation + Stage76 schedule, Stage78 colour expression.
            var p=HasselbladDngTileReader.readPrepared76(file);var m=p.metadata;
            var selection=HasselbladIlluminant56.estimate(m.illuminant.colorMatrix1,m.illuminant.colorMatrix2,
                    m.illuminant.light1,m.illuminant.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] camera=HasselbladRenderer42.cameraToD50(m.forwardMatrix1,m.forwardMatrix2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
            double[] params=profile.parameters(camera),grid=profile.gridAtTemperature(selection.lutKelvin);
            int w=HasselbladFrame76.width(m.width),h=HasselbladFrame76.width(m.height);int[] expected=new int[w*h];
            for(int y=0;y<h;y+=64) {
                short[] rgb=HasselbladFrame76.band(p.bayer,m.width,m.height,y);
                int[] values=HasselbladProfile43.srgb16ToArgb(profile.finishRgb16(HasselbladRenderer42.render(rgb,params,grid,profile.curve,profile.gridWidth,profile.gridHeight,1)));
                System.arraycopy(values,0,expected,y*w,values.length);
            }
            for(int workers:new int[]{1,4}) {
                int[] actual=new int[w*h];int[] next={0};
                var r=HasselbladSceneRenderer79.render(file,profile,workers,new HasselbladSceneRenderer79.Sink(){
                    public void begin(int sw,int sh){check(sw==w&&sh==h,"Dimensions changed");}
                    public void band(int y,int rows,int sw,int[] data){check(y==next[0]&&data.length==rows*sw,"Band ordering/gap");next[0]+=rows;System.arraycopy(data,0,actual,y*w,data.length);}
                });
                check(next[0]==h&&Arrays.equals(expected,actual),"Automatic colour output changed");pixels+=actual.length;
                check(r.orientation==p.orientation && r.kelvin==selection.lutKelvin && r.checkedSites==49152,"Metadata/guard changed");
                for(var s:r.samples) {
                    short[] reference=new short[64*64*3];
                    check(HasselbladFinalRaw74.renderLinearRgb16Native(s.bayer,128,64,64,0,reference)==0,"Reference render failed");
                    check(Arrays.equals(reference,s.rgb),"Exported sample mismatch");rgbCodes+=reference.length;
                }
            }
        }
        // Padded source whose final row omits padding: preserve position, limit and source bytes.
        int w=128,h=129,row=270,required=(h-1)*row+w*2;
        ByteBuffer source=ByteBuffer.allocateDirect(required),packed=ByteBuffer.allocateDirect(w*h*2);
        for(int i=0;i<required;i++)source.put(i,(byte)(i*71));source.position(11);source.limit(required-3);
        HasselbladRawLayout79.validate(w,h,row,2,row/2,h,required,required,0,0,0,false,true);
        HasselbladRawLayout79.copy(source,packed,w,h,row);
        for(int y=0;y<h;y++)for(int x=0;x<w*2;x++)check(packed.get(y*w*2+x)==(byte)((y*row+x)*71),"Padding entered RAW");
        check(source.position()==11&&source.limit()==required-3,"Source cursor changed");
        ByteBuffer all=source.duplicate();all.clear();for(int i=0;i<required;i++)check(all.get(i)==(byte)(i*71),"Source mutated");
        reject(()->HasselbladRawLayout79.validate(w,h,row,2,row/2,h,required-1,required,0,0,0,false,true));
        reject(()->HasselbladRawLayout79.validate(w,h,row,2,row/2,h,required,required,2,0,0,false,true));
        reject(()->HasselbladRawLayout79.validate(w,h,row,2,row/2,h,required,required,0,0,0,true,true));
        reject(()->HasselbladRawLayout79.validate(w,h,row,2,row/2,h,required,required,0,0,0,false,false));
        reject(()->HasselbladRawLayout79.validate(w,h,row,1,row/2,h,required,required,0,0,0,false,true));
        reject(()->HasselbladRawLayout79.validate(8192,8192,16384,2,8192,8192,Long.MAX_VALUE,Long.MAX_VALUE,0,0,0,false,true));
        check(HasselbladRawLayout79.orientation(0)==1&&HasselbladRawLayout79.orientation(90)==6&&HasselbladRawLayout79.orientation(180)==3&&HasselbladRawLayout79.orientation(270)==8,"Orientation");
        reject(()->HasselbladRawLayout79.orientation(45));
        Path publish=Files.createTempDirectory(work,"publish79-");Path input=publish.resolve("source"),out=publish.resolve("out.jpg");
        Files.write(input,new byte[]{1,2,3});HasselbladCaptureFiles79.publish(input,out);
        check(Arrays.equals(Files.readAllBytes(out),new byte[]{1,2,3}),"Publication bytes changed");
        Files.write(input,new byte[]{4,5,6});reject(()->HasselbladCaptureFiles79.publish(input,out));
        check(Arrays.equals(Files.readAllBytes(out),new byte[]{1,2,3}),"Existing photo overwritten");
        Thread.currentThread().interrupt();try {
            reject(()->HasselbladRawLayout79.copy(source,packed,w,h,row));
            reject(()->HasselbladCaptureFiles79.publish(input,publish.resolve("cancelled.jpg")));
            reject(()->HasselbladSceneRenderer79.render(fixtures.resolve("prep78-0.dng").toFile(),profile,4,null));
        }finally{Thread.interrupted();}
        try(var paths=Files.list(publish)){check(paths.count()==2,"Partial publication left files");}
        check(!ImageFormatConfig.savesRaw(0)&&!ImageFormatConfig.isRawOnly(0),"JPEG-only");
        check(ImageFormatConfig.savesRaw(1)&&!ImageFormatConfig.isRawOnly(1),"RAW+JPEG");
        check(ImageFormatConfig.savesRaw(2)&&ImageFormatConfig.isRawOnly(2),"RAW-only");
        String result="{\"schema\":\"hasselblad-stage79-host-v1\",\"status\":\"PASS\",\"automatic_argb_pixels_exact\":"+pixels+
                ",\"sample_rgb16_codes_exact\":"+rgbCodes+",\"row_padding_immutability_cancellation_publication\":true,\"device_capture_tested\":false}";
        Files.writeString(work.resolve("STAGE79_HOST_VALIDATION.json"),result+"\n");System.out.println(result);
    }
}
