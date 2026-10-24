package com.particlesdevs.photoncamera.hasselblad;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.util.Arrays;

/** Private data-only look. Camera calibration is read afresh from each DNG. */
public final class HasselbladProfile43 {
    public static final int MAX_BYTES=1400000;
    public final int gridWidth,gridHeight,temperature,model,film,space;
    private final double[] values=new double[38];
    public final double[] grid;
    public final float[] curve=new float[65536];
    private final byte[] encoded;
    public final boolean hasNativeFinishing,hasAutomaticIlluminant;
    private final int[] anchorTemperatures=new int[3];
    private final double[][] anchorGrids=new double[3][];
    private final double[] outputMatrix=new double[9];
    private double outputExponent;
    private HasselbladProfile43(byte[] data)throws Exception {
        if(data.length<400)throw new IOException("Incomplete colour profile");
        MessageDigest sha=MessageDigest.getInstance("SHA-256");sha.update(data,0,data.length-32);
        if(!MessageDigest.isEqual(sha.digest(),Arrays.copyOfRange(data,data.length-32,data.length)))
            throw new IOException("Colour profile checksum failed");
        ByteBuffer b=ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic=new byte[8];b.get(magic);
        hasAutomaticIlluminant=Arrays.equals(magic,new byte[]{'H','B','5','6','L','U','T','1'});
        hasNativeFinishing=hasAutomaticIlluminant||Arrays.equals(magic,new byte[]{'H','B','5','5','L','U','T','1'});
        if(!hasNativeFinishing&&!Arrays.equals(magic,new byte[]{'H','B','4','3','L','U','T','1'}))
            throw new IOException("Choose a supported .hbc colour profile");
        gridWidth=b.getInt();gridHeight=b.getInt();temperature=b.getInt();
        model=b.getInt();film=b.getInt();space=b.getInt();
        if(gridWidth<2||gridWidth>256||gridHeight<2||gridHeight>256||
            temperature<2000||temperature>10000||model<0||model>1||
            (film!=0&&film!=1&&film!=7)||space!=0)
            throw new IOException("Unsupported colour profile configuration");
        if(hasAutomaticIlluminant&&model!=0)throw new IOException("Automatic illuminant requires the normal model");
        long count=(long)gridWidth*gridHeight*2;
        if(data.length!=32+38*8+count*8+65536*4+32+(hasNativeFinishing?96:0)+(hasAutomaticIlluminant?8+3*(4+count*8):0))throw new IOException("Colour profile length mismatch");
        for(int i=0;i<values.length;i++) {
            values[i]=b.getDouble();
            if(!Double.isFinite(values[i])||Math.abs(values[i])>1e6)throw new IOException("Invalid colour parameter");
        }
        if(values[22]!=1||values[23]!=1||values[24]!=1||values[25]!=1||values[37]<=0||values[37]>8)
            throw new IOException("Unsupported white balance, exposure or display transfer");
        grid=new double[(int)count];
        for(int i=0;i<grid.length;i++) {
            grid[i]=b.getDouble();
            if(!Double.isFinite(grid[i])||Math.abs(grid[i])>1e6)throw new IOException("Invalid colour grid");
        }
        for(int i=0;i<curve.length;i++) {
            curve[i]=b.getFloat();
            if(!Float.isFinite(curve[i])||curve[i]<0||curve[i]>65535)throw new IOException("Invalid colour curve");
        }
        if(hasNativeFinishing) {
            if(b.getInt()!=1||b.getInt()!=0||b.getInt()!=2||b.getInt()!=1)
                throw new IOException("Unsupported finishing route");
            for(int i=0;i<9;i++) {
                outputMatrix[i]=b.getDouble();
                if(!Double.isFinite(outputMatrix[i])||Math.abs(outputMatrix[i])>1e6)
                    throw new IOException("Invalid output matrix");
            }
            outputExponent=b.getDouble();
            if(!Double.isFinite(outputExponent)||outputExponent<=0||outputExponent>8)
                throw new IOException("Invalid output transfer");
        }
        if(hasAutomaticIlluminant) {
            if(b.getInt()!=1||b.getInt()!=3)throw new IOException("Unsupported illuminant profile version");
            for(int j=0;j<3;j++) {
                anchorTemperatures[j]=b.getInt();
                if(anchorTemperatures[j]<2000||anchorTemperatures[j]>10000||
                    (j>0&&anchorTemperatures[j]<=anchorTemperatures[j-1]))throw new IOException("Invalid LUT anchors");
                anchorGrids[j]=new double[(int)count];
                for(int i=0;i<count;i++) {
                    double v=b.getDouble();
                    if(!Double.isFinite(v)||Math.abs(v)>1e6)throw new IOException("Invalid illuminant LUT");
                    anchorGrids[j][i]=v;
                }
            }
        }
        encoded=data;
    }
    public static HasselbladProfile43 read(InputStream in)throws Exception {
        if(in==null)throw new IOException("Cannot open colour profile");
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] block=new byte[16384];int n;
        while((n=in.read(block))!=-1){if(out.size()+n>MAX_BYTES)throw new IOException("Colour profile too large");out.write(block,0,n);}
        return new HasselbladProfile43(out.toByteArray());
    }
    public byte[] encoded(){return encoded.clone();}
    public static double[] multiply(double[] a,double[] b) {
        if(a.length!=9||b.length!=9)throw new IllegalArgumentException("Expected 3 by 3 matrices");
        double[] c=new double[9];
        for(int r=0;r<3;r++)for(int col=0;col<3;col++)
            for(int k=0;k<3;k++)c[r*3+col]+=a[r*3+k]*b[k*3+col];
        return c;
    }
    public double[] parameters(double[] cameraToD50) {
        double[] p=values.clone(),first=multiply(Arrays.copyOf(values,9),cameraToD50);
        System.arraycopy(first,0,p,0,9);return p;
    }
    private static int[] encode(short[] input,double[] matrix,double exponent,double denominator) {
        if(input.length%3!=0||matrix.length!=9)throw new IllegalArgumentException("Invalid display input");
        double[] decoded=new double[65536];
        for(int i=0;i<decoded.length;i++)decoded[i]=Math.pow(i/denominator,exponent);
        int[] pixels=new int[input.length/3];
        for(int i=0;i<pixels.length;i++) {
            double r=decoded[input[3*i]&65535],g=decoded[input[3*i+1]&65535],blue=decoded[input[3*i+2]&65535];
            int packed=0xff000000;
            for(int c=0;c<3;c++) {
                double v=matrix[c*3]*r+matrix[c*3+1]*g+matrix[c*3+2]*blue;
                v=Math.max(0,Math.min(1,v));v=v<=.0031308?12.92*v:1.055*Math.pow(v,1/2.4)-.055;
                packed|=((int)Math.floor(v*255+.5))<<(16-8*c);
            }
            pixels[i]=packed;
        }
        return pixels;
    }
    public int[] display(short[] rendered) {return encode(rendered,Arrays.copyOfRange(values,28,37),values[37],65536);}
    /** Native normal-model LUT interpolation in Kelvin, including endpoint extrapolation.
     * DNG matrix interpolation uses inverse Kelvin independently. */
    public double[] gridAtTemperature(int kelvin) {
        if(!hasAutomaticIlluminant)throw new IllegalStateException("Import an automatic-illuminant profile");
        int t=Math.max(2000,Math.min(10000,kelvin)),j=t<anchorTemperatures[1]?0:1;
        double weight=(double)(t-anchorTemperatures[j])/(anchorTemperatures[j+1]-anchorTemperatures[j]);
        double[] result=new double[grid.length];
        for(int i=0;i<result.length;i++)result[i]=Math.fma(weight,anchorGrids[j+1][i]-anchorGrids[j][i],anchorGrids[j][i]);
        return result;
    }
    public short[] finishRgb16(short[] rendered) {
        if(!hasNativeFinishing)throw new IllegalStateException("Import a finishing-enabled colour profile");
        return HasselbladRenderer42.outputSrgb16(HasselbladRenderer42.defaultGradation(rendered),outputMatrix,outputExponent);
    }
    public static int[] srgb16ToArgb(short[] rgb) {
        if(rgb==null||rgb.length%3!=0)throw new IllegalArgumentException("Invalid sRGB16 input");
        int[] pixels=new int[rgb.length/3];
        for(int i=0;i<pixels.length;i++) {
            int v=0xff000000;
            for(int c=0;c<3;c++)v|=(((rgb[3*i+c]&65535)+128)/257)<<(16-8*c);
            pixels[i]=v;
        }
        return pixels;
    }
    public static int[] baseline(short[] camera,double[] cameraToD50,double[] xyzToSrgb) {
        return encode(camera,multiply(xyzToSrgb,cameraToD50),1,65535);
    }
}
