import com.particlesdevs.photoncamera.hasselblad.*;
import java.io.*;import java.nio.*;import java.nio.file.*;import java.security.*;import java.util.*;
public final class Stage56Smoke {
    static int checks,cases;static double maxError,maxResidual;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    interface Action{void run()throws Exception;}
    static void reject(Action a)throws Exception {boolean fail=false;try{a.run();}catch(IOException|IllegalArgumentException|IllegalStateException e){fail=true;}check(fail,"Expected rejection");}
    static double[] read(DataInputStream in,int n)throws Exception{double[] v=new double[n];for(int i=0;i<n;i++)v[i]=in.readDouble();return v;}
    static void checksum(byte[] b)throws Exception{var d=MessageDigest.getInstance("SHA-256");d.update(b,0,b.length-32);System.arraycopy(d.digest(),0,b,b.length-32,32);}
    static HasselbladIlluminant56.Result estimate(HasselbladDngTileReader.ReadResult m) {
        var i=m.illuminant;if(i.error!=null)throw new IllegalArgumentException(i.error);
        return HasselbladIlluminant56.estimate(i.colorMatrix1,i.colorMatrix2,i.light1,i.light2,m.calibration1,m.calibration2,m.analogBalance,m.asShotNeutral);
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);
        try(var in=new DataInputStream(new FileInputStream(root.resolve("numeric.bin").toFile()))) {
            int count=in.readInt();for(int row=0;row<count;row++) {
                int l1=in.readInt(),l2=in.readInt();double[] c1=read(in,9),c2=read(in,9),cc=read(in,9),ab=read(in,3),n=read(in,3);
                double expected=in.readDouble(),tint=in.readDouble();int selected=in.readInt();
                double[] before=n.clone(),beforeC1=c1.clone();
                var result=HasselbladIlluminant56.estimate(c1,c2,l1,l2,cc,cc,ab,n);
                double error=Math.abs(expected-result.kelvin);maxError=Math.max(maxError,error);maxResidual=Math.max(maxResidual,result.residual);
                check(error<1e-4,"Independent bisection CCT");check(Math.abs(result.tint-tint)<1e-5,"Tint geometry");
                check(result.nativeKelvin==selected,"Native selection grid");check(result.lutKelvin==Math.max(2000,Math.min(10000,selected)),"LUT bounds");
                check(Arrays.equals(n,before)&&Arrays.equals(c1,beforeC1),"Metadata mutated");cases++;
            }
            check(in.read()==-1,"Trailing fixture bytes");
        }
        for(double k:new double[]{1999,2000,2024,2025,2026,7975,8000,8049,8050,9999,10000,10499,10500,20000,22499,22500,50000,60000}) {
            int integer=(int)Math.floor(k+.5),v=Math.max(2000,Math.min(50000,integer));int step=v<=8000?50:v<=10000?100:v<=20000?1000:5000;
            int low=v<=8000?2000:v<=10000?8000:v<=20000?10000:20000;
            check(HasselbladIlluminant56.quantize(k)==low+((v-low+step/2)/step)*step,"Quantization boundary");
        }
        double[] id={1,0,0,0,1,0,0,0,1},n={.7,1,.8};
        reject(()->HasselbladIlluminant56.estimate(null,id,21,17,null,null,null,n));
        reject(()->HasselbladIlluminant56.estimate(new double[9],id,21,17,null,null,null,n));
        reject(()->HasselbladIlluminant56.estimate(id,id,255,17,null,null,null,n));
        reject(()->HasselbladIlluminant56.estimate(id,id,21,21,null,null,null,n));
        reject(()->HasselbladIlluminant56.estimate(id,id,21,17,null,null,new double[]{1,0,1},n));
        reject(()->HasselbladIlluminant56.estimate(id,id,21,17,null,null,null,new double[]{0,1,1}));
        reject(()->HasselbladIlluminant56.estimate(id,id,21,17,null,null,null,new double[]{Double.NaN,1,1}));
        double[] other=id.clone();other[1]=.1;reject(()->HasselbladIlluminant56.estimate(id,id,21,17,id,other,null,n));
        var p55=HasselbladProfile43.read(Files.newInputStream(root.resolve("synthetic55.hbc")));
        byte[] encoded=Files.readAllBytes(root.resolve("synthetic56.hbc"));var p56=HasselbladProfile43.read(new ByteArrayInputStream(encoded));
        check(p56.hasAutomaticIlluminant&&p56.hasNativeFinishing&&!p55.hasAutomaticIlluminant,"Profile capabilities");
        short[] codes={0,1,32767,-1,1200,25000};check(Arrays.equals(p55.finishRgb16(codes),p56.finishRgb16(codes)),"Manual finishing unchanged");
        check(Arrays.equals(p55.parameters(id),p56.parameters(id))&&Arrays.equals(p55.grid,p56.grid),"Colour payload unchanged");
        for(int t:new int[]{1000,2000,3000,3550,5500,8000,9000,10000,15000}) {
            int k=Math.max(2000,Math.min(10000,t)),j=k<5500?0:1;double w=(k-(j==0?3000:5500))/(j==0?2500.:3500.);
            double[] grid=p56.gridAtTemperature(t);for(int i=0;i<grid.length;i++)check(Math.abs(grid[i]-(i/8.+j+w))<1e-14,"LUT interpolation/extrapolation");
        }
        int extension=encoded.length-32-(8+3*(4+8*8));
        for(int offset:new int[]{extension,extension+4,extension+8,extension+8+68}) {
            byte[] bad=encoded.clone();ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN).putInt(offset,0);checksum(bad);
            reject(()->HasselbladProfile43.read(new ByteArrayInputStream(bad)));
        }
        byte[] bad=encoded.clone();ByteBuffer.wrap(bad).order(ByteOrder.LITTLE_ENDIAN).putDouble(extension+12,Double.NaN);checksum(bad);reject(()->HasselbladProfile43.read(new ByteArrayInputStream(bad)));
        byte[] wrongModel=encoded.clone();ByteBuffer.wrap(wrongModel).order(ByteOrder.LITTLE_ENDIAN).putInt(20,1);checksum(wrongModel);
        reject(()->HasselbladProfile43.read(new ByteArrayInputStream(wrongModel)));
        short[] pixels=null;double valid=0;
        for(String name:new String[]{"valid","swapped","single","mismatch","missing","bad_count","bad_illuminant","third","short_neutral"}) {
            var preview=HasselbladDngTileReader.readPreview(root.resolve(name+".dng").toFile(),4096);var meta=preview.metadata;
            if(pixels==null)pixels=preview.cameraRgb16.clone();check(Arrays.equals(pixels,preview.cameraRgb16),"Selector metadata altered raw preparation");
            var tile=HasselbladDngTileReader.read(root.resolve(name+".dng").toFile());
            if(Set.of("missing","bad_count","bad_illuminant","third").contains(name)) {
                reject(()->estimate(meta));reject(()->estimate(tile));
            }else{
                var r=estimate(meta);check(Math.abs(r.kelvin-estimate(tile).kelvin)<1e-10,"Tile/preview selection mismatch");
                if(name.equals("valid"))valid=r.kelvin;
                if(name.equals("swapped")||name.equals("short_neutral"))check(Math.abs(r.kelvin-valid)<1e-8,"Metadata invariance");
                if(name.equals("mismatch"))check(meta.calibration1==null,"Signature mismatch ignored calibration");
            }
        }
        System.out.println("{\"status\":\"PASS\",\"checks\":"+checks+",\"numeric_cases\":"+cases+",\"maximum_kelvin_error\":"+maxError+",\"maximum_ratio_residual\":"+maxResidual+",\"synthetic_only\":true}");
    }
}
