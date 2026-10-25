import com.particlesdevs.photoncamera.hasselblad.HasselbladFinalRaw74;
import java.util.Arrays;
public final class Stage74JvmTest {
  static void check(boolean okay){if(!okay)throw new AssertionError();}
  static void caseTest(int w,int h){
    int srcW=w+64,srcH=h+64;
    short[] raw=new short[srcW*srcH];Arrays.fill(raw,(short)10000);
    short[] rgb=new short[w*h*3];Arrays.fill(rgb,(short)2222);
    int status=HasselbladFinalRaw74.renderLinearRgb16Native(raw,srcW,w,h,0,rgb);
    check(status==0);
    for(short v:rgb)check(v==(short)10000);
    for(short v:raw)check(v==(short)10000);
    Arrays.fill(rgb,(short)3333);
    status=HasselbladFinalRaw74.renderLinearRgb16Native(raw,srcW,w,h,1,rgb);
    check(status!=0);for(short v:rgb)check(v==(short)3333);
  }
  public static void main(String[] args){
    caseTest(12,15);caseTest(23,31);caseTest(9,11);
    short[] raw=new short[12*15*3];Arrays.fill(raw,(short)23);
    check(HasselbladFinalRaw74.renderLinearRgb16Native(raw,12,12,15,0,raw)!=0);
    check(HasselbladFinalRaw74.renderLinearRgb16Native(null,12,12,15,0,raw)!=0);
    check(HasselbladFinalRaw74.renderLinearRgb16Native(raw,12,75,91,0,raw)!=0);
    for(short v:raw)check(v==(short)23);
    System.out.println("STAGE74_HOST_JVM_JNI_RGB16_PASS");
  }
}
