package com.particlesdevs.photoncamera.hasselblad;

import java.util.Arrays;

/** Metadata-only white-point estimate. Never changes camera gains or pixel values.
 * Bounded three-channel, one/two-illuminant DNG route; camera calibration must
 * already be selected by matching DNG signatures. SDK-compatible CM scaling.
 */
public final class HasselbladIlluminant56 {
    private HasselbladIlluminant56() {}
    // Public Robertson data: Wyszecki & Stiles p.228, Adobe DNG SDK 1.4
    // dng_temperature.cpp blob 47318abb306a231e04140ff57caee2d8a3b77b6c.
    // Explicit public variant u325=.24702; no private calibration data here.
    private static final double[][] TABLE={
        {0,.18006,.26352,-.24341},
        {10,.18066,.26589,-.25479},
        {20,.18133,.26846,-.26876},
        {30,.18208,.27119,-.28539},
        {40,.18293,.27407,-.30470},
        {50,.18388,.27709,-.32675},
        {60,.18494,.28021,-.35156},
        {70,.18611,.28342,-.37915},
        {80,.18740,.28668,-.40955},
        {90,.18880,.28997,-.44278},
        {100,.19032,.29326,-.47888},
        {125,.19462,.30141,-.58204},
        {150,.19962,.30921,-.70471},
        {175,.20525,.31647,-.84901},
        {200,.21142,.32312,-1.0182},
        {225,.21807,.32909,-1.2168},
        {250,.22511,.33439,-1.4512},
        {275,.23247,.33904,-1.7298},
        {300,.24010,.34308,-2.0637},
        {325,.24702,.34655,-2.4681},
        {350,.25591,.34951,-2.9641},
        {375,.26400,.35200,-3.5814},
        {400,.27218,.35407,-4.3633},
        {425,.28039,.35577,-5.3762},
        {450,.28863,.35714,-6.7262},
        {475,.29685,.35823,-8.5955},
        {500,.30505,.35907,-11.324},
        {525,.31320,.35968,-15.628},
        {550,.32129,.36011,-23.325},
        {575,.32931,.36038,-40.770},
        {600,.33724,.36051,-116.45}};
    private static final double[] ID={1,0,0,0,1,0,0,0,1};
    public static final class Result {
        public final double kelvin,tint,residual;
        public final int nativeKelvin,lutKelvin,iterations;
        private Result(double k,double t,double r,int i) {
            kelvin=k;tint=t;residual=r;iterations=i;nativeKelvin=quantize(k);
            lutKelvin=Math.max(2000,Math.min(10000,nativeKelvin));
        }
    }
    private static void require(boolean ok,String why) {if(!ok)throw new IllegalArgumentException(why);}
    private static double[] valid(double[] input,int n,String label) {
        require(input!=null&&input.length==n,label+" missing or wrong length");
        double[] result=input.clone();
        for(double x:result)require(Double.isFinite(x)&&Math.abs(x)<=1e6,label+" invalid");
        return result;
    }
    private static double[] mv(double[] m,double[] v) {
        double[] r=new double[3];
        for(int i=0;i<3;i++)for(int j=0;j<3;j++)r[i]+=m[3*i+j]*v[j];
        return r;
    }
    private static double[] inverse(double[] a) {
        double[] b={a[4]*a[8]-a[5]*a[7],a[2]*a[7]-a[1]*a[8],a[1]*a[5]-a[2]*a[4],
            a[5]*a[6]-a[3]*a[8],a[0]*a[8]-a[2]*a[6],a[2]*a[3]-a[0]*a[5],
            a[3]*a[7]-a[4]*a[6],a[1]*a[6]-a[0]*a[7],a[0]*a[4]-a[1]*a[3]};
        double det=a[0]*b[0]+a[1]*b[3]+a[2]*b[6],scale=0;
        for(double x:a)scale=Math.max(scale,Math.abs(x));
        require(scale>0&&Double.isFinite(det)&&Math.abs(det)>1e-10*scale*scale*scale,"Singular colour calibration");
        for(int i=0;i<9;i++)b[i]/=det;return b;
    }
    private static double[] normalized(double[] input) {
        double[] m=valid(input,9,"Colour matrix"),w=mv(m,new double[]{.9642,1,.8249});
        double top=Math.max(w[0],Math.max(w[1],w[2]));require(top>0,"Invalid colour matrix normalization");
        double scale=top<.99||top>1.01?1/top:1;
        for(int i=0;i<9;i++)m[i]=Math.floor(m[i]*scale*10000+.5)/10000;
        inverse(m);return m;
    }
    public static double illuminantKelvin(int code) {
        switch(code) {
            case 3:case 17:return 2850;
            case 24:return 3200;
            case 23:return 5000;
            case 1:case 4:case 9:case 18:case 20:return 5500;
            case 10:case 19:case 21:return 6500;
            case 11:case 22:return 7500;
            case 12:return 6400;case 13:return 5050;
            case 2:case 14:return 4150;case 15:return 3575;case 16:return 2925;
            default:throw new IllegalArgumentException("Unsupported calibration illuminant");
        }
    }
    public static int quantize(double kelvin) {
        require(Double.isFinite(kelvin)&&kelvin>0,"Invalid temperature");
        int k=(int)Math.floor(kelvin+.5);k=Math.max(2000,Math.min(50000,k));
        int low=k<=8000?2000:k<=10000?8000:k<=20000?10000:20000;
        int step=k<=8000?50:k<=10000?100:k<=20000?1000:5000;
        return low+(int)((float)(k-low)/step+.5f)*step;
    }
    /** Standard xy -> correlated temperature and DNG tint, not native tint. */
    public static double[] temperature(double x,double y) {
        require(Double.isFinite(x)&&Double.isFinite(y)&&x>0&&y>0&&x+y<1,"Invalid white point");
        double denom=1.5-x+6*y,u=2*x/denom,v=3*y/denom,last=0;
        double[] previous={0,0};
        for(int i=1;i<31;i++) {
            double length=Math.hypot(1,TABLE[i][3]),du=1/length,dv=TABLE[i][3]/length;
            double distance=(v-TABLE[i][2])*du-(u-TABLE[i][1])*dv;
            if(distance<=0||i==30) {
                double d=Math.min(0,distance),weight=i==1?0:-d/(last-d);
                double kelvin=1e6/(TABLE[i-1][0]*weight+TABLE[i][0]*(1-weight));
                double lu=TABLE[i-1][1]*weight+TABLE[i][1]*(1-weight);
                double lv=TABLE[i-1][2]*weight+TABLE[i][2]*(1-weight);
                double nu=previous[0]*weight+du*(1-weight),nv=previous[1]*weight+dv*(1-weight);
                double tint=-3000*((u-lu)*nu+(v-lv)*nv)/Math.hypot(nu,nv);
                return new double[]{kelvin,tint};
            }
            last=distance;previous=new double[]{du,dv};
        }
        throw new IllegalArgumentException("White point outside temperature model");
    }
    public static Result estimate(double[] cm1,double[] cm2,int light1,int light2,
            double[] cc1,double[] cc2,double[] analog,double[] neutral) {
        double[] c1=normalized(cm1),c2=cm2==null?c1:normalized(cm2);
        double t1=cm2==null?5000:illuminantKelvin(light1),t2=cm2==null?5000:illuminantKelvin(light2);
        require(cm2==null||t1!=t2,"Duplicate calibration illuminants");
        double[] calibration=cc1==null?ID.clone():valid(cc1,9,"Camera calibration");
        require(cc2==null||Arrays.equals(calibration,valid(cc2,9,"Camera calibration")),"Unequal camera calibration unsupported");
        double[] ab=analog==null?new double[]{1,1,1}:valid(analog,3,"Analog balance");
        double[] n=valid(neutral,3,"As-shot neutral");double max=Math.max(n[0],Math.max(n[1],n[2]));
        for(int i=0;i<3;i++){require(n[i]>0&&ab[i]>0,"Nonpositive neutral or analog balance");n[i]/=max;}
        for(int r=0;r<3;r++)for(int c=0;c<3;c++)calibration[3*r+c]*=ab[r];
        inverse(calibration);
        double x=.3457,y=.3585;
        for(int pass=1;pass<=30;pass++) {
            double k=temperature(x,y)[0];
            double w=cm2==null?1:Math.max(0,Math.min(1,(1/k-1/t2)/(1/t1-1/t2)));
            double[] cm=new double[9];for(int i=0;i<9;i++)cm[i]=w*c1[i]+(1-w)*c2[i];
            double[] matrix=HasselbladProfile43.multiply(calibration,cm);
            double[] xyz=mv(inverse(matrix),n);double sum=xyz[0]+xyz[1]+xyz[2];
            require(xyz[0]>0&&xyz[1]>0&&xyz[2]>0&&Double.isFinite(sum),"Invalid inferred white point");
            double nx=xyz[0]/sum,ny=xyz[1]/sum;
            if(Math.abs(nx-x)+Math.abs(ny-y)<1e-10) {
                double[] kt=temperature(nx,ny);
                require(kt[0]>=1667&&kt[0]<=100000&&Math.abs(kt[1])<=150,"White point outside supported temperature/tint range");
                double nw=cm2==null?1:Math.max(0,Math.min(1,(1/kt[0]-1/t2)/(1/t1-1/t2)));
                for(int i=0;i<9;i++)cm[i]=nw*c1[i]+(1-nw)*c2[i];
                double[] rebuilt=mv(HasselbladProfile43.multiply(calibration,cm),new double[]{nx,ny,1-nx-ny});
                double residual=0;for(int i=0;i<3;i++)residual=Math.max(residual,Math.abs((rebuilt[i]/rebuilt[1])/(n[i]/n[1])-1));
                require(Double.isFinite(residual)&&residual<1e-7,"White-point reconstruction residual");
                return new Result(kt[0],kt[1],residual,pass);
            }
            x=nx;y=ny;
        }
        throw new IllegalArgumentException("White-point estimate did not converge");
    }
}
