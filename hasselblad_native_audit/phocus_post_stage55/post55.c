#include "post55.h"
#include <math.h>
#include <stdlib.h>

int hb55_default_curve(uint16_t *curve) {
    if(!curve)return -1;
    const double high=16383/(255*64.);
    const double gain=1/(double)(float)high,extent=high*gain;
    for(size_t i=0;i<65536;i++) {
        size_t index=(size_t)((((double)i*(1/65535.))*gain)*65535./extent);
        float value=(float)((extent/65535.)*(double)index);
        curve[i]=(uint16_t)fmin(65535,floor((double)value*65535+.5));
    }
    return 0;
}

static double hue_component(double low,double high,double h) {
    if(h<0)h+=1;
    if(h>1)h-=1;
    double slope=(high-low)*6;
    if(h<(double)(1.f/6.f))return fma(slope,h,low);
    if(h<.5)return high;
    if(h<(double)(2.f/3.f))return fma(slope,(double)(2.f/3.f)-h,low);
    return low;
}

/* Reconstruct the identity-contrast hue round trip with its mixed precision.
 * The mathematical identity can still move the truncated output by one code. */
static void preserve_hue(const float input[3],float output[3]) {
    float r=input[0]/65535.f,g=input[1]/65535.f,b=input[2]/65535.f;
    float lo=fminf(r,fminf(g,b)),hi=fmaxf(r,fmaxf(g,b)),d=hi-lo,h=0;
    if(hi!=lo) {
        if(hi==r){h=((g-b)*60.f)/d;if(g<b)h+=360.f;}
        else if(hi==g)h=((b-r)*60.f)/d+120.f;
        else h=((r-g)*60.f)/d+240.f;
    }
    float light=(lo+hi)*.5f,q;
    if(light<.5f) {
        float scale=1;
        if((double)light>1./65535)scale+=(d*.5f)/light;
        q=light*scale;
    } else {
        float saturation=0;
        if((double)light<1-1./65535)saturation=d/fmaf(light,-2.f,2.f);
        q=fmaf(-light,saturation,light+saturation);
    }
    float hue=h/360.f;
    double low=(double)(light+light)-(double)q;
    const double offsets[3]={(double)(1.f/3.f),0,(double)(-1.f/3.f)};
    for(int i=0;i<3;i++)output[i]=(float)hue_component(low,q,(double)hue+offsets[i])*65535.f;
}

int hb55_gradate(const uint16_t *curve,const uint16_t *input,size_t pixels,uint16_t *output) {
    if(!curve||!input||!output||pixels>SIZE_MAX/3)return -1;
    for(size_t k=0;k<pixels;k++) {
        float mapped[3],recovered[3];
        for(size_t c=0;c<3;c++)mapped[c]=curve[input[3*k+c]];
        preserve_hue(mapped,recovered);
        for(size_t c=0;c<3;c++) {
            float ratio=mapped[c]==0?recovered[c]:recovered[c]/mapped[c];
            float result=ratio*mapped[c];
            output[3*k+c]=(uint16_t)fminf(65535.f,fmaxf(0,result));
        }
    }
    return 0;
}

int hb55_output_rgb16(const uint16_t *input,size_t pixels,const double matrix[9],
                     double exponent,uint16_t *output) {
    if(!input||!matrix||!output||pixels>SIZE_MAX/3||!isfinite(exponent)||exponent<=0||exponent>8)return -1;
    for(int i=0;i<9;i++)if(!isfinite(matrix[i])||fabs(matrix[i])>1e6)return -1;
    float *decode=malloc(65536*sizeof(float));if(!decode)return -2;
    for(size_t i=0;i<65536;i++)decode[i]=(float)pow((double)((float)i/65535.f),exponent);
    for(size_t k=0;k<pixels;k++) {
        double rgb[3];for(size_t c=0;c<3;c++)rgb[c]=decode[input[3*k+c]];
        for(size_t c=0;c<3;c++) {
            float linear=(float)((rgb[0]*matrix[3*c]+rgb[1]*matrix[3*c+1])+rgb[2]*matrix[3*c+2]);
            float encoded=(float)(linear<=.0031308?(double)linear*12.92:
                                  1.055*pow((double)linear,1/2.4)-.055);
            float scaled=encoded*65535.f;
            output[3*k+c]=(uint16_t)fmin(65535,fmax(0,floor((double)scaled+.5)));
        }
    }
    free(decode);return 0;
}
