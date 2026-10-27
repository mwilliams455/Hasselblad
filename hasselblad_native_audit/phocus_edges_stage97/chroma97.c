#include "chroma97.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct {double y,c1,c2,mag;int clipped;} Pixel;
static double ramp(double x){return fmax(0.0,fmin(1.0,x));}
static double median9(double *v) {
    for(int i=1;i<9;i++){double a=v[i];int j=i;while(j>0&&v[j-1]>a){v[j]=v[j-1];j--;}v[j]=a;}
    return v[4];
}

/* New bounded source-camera adaptation, not a recovered Phocus primitive.
 * A 3x3 chroma median identifies isolated deviations. The 5x5 colour guard
 * protects nearby real colour. The two smooth gates restrict changes to
 * low-chroma, high-contrast detail. No hue (including magenta) is singled out.
 * Before quantization each normalized chroma coordinate changes by <= .005;
 * (R/nR + 2G + B/nB)/4 is preserved exactly in the real-valued calculation. */
int hb97_chroma_roi(const uint16_t *rgb,size_t input_count,int width,int height,
    double nr,double nb,uint16_t *output,size_t output_capacity) {
    if(!rgb||!output||width<5||width>8196||height<5||height>8196)return -1;
    if(!isfinite(nr)||!isfinite(nb)||nr<.0625||nr>16||nb<.0625||nb>16)return -2;
    size_t sites=(size_t)width*height,n=sites*3,out=(size_t)(width-4)*(height-4)*3;
    if(input_count<n||output_capacity<out)return -1;
    uintptr_t a=(uintptr_t)rgb,b=(uintptr_t)output;
    if(a>UINTPTR_MAX-n*2||b>UINTPTR_MAX-out*2||!(a+n*2<=b||b+out*2<=a))return -1;
    Pixel *p=malloc(sites*sizeof(*p));if(!p)return -3;
    for(size_t i=0;i<sites;i++) {
        double r=rgb[3*i]/nr,g=rgb[3*i+1],b0=rgb[3*i+2]/nb,s=r+2*g+b0;
        double c1=(r-g)/(s+1),c2=(b0-g)/(s+1);
        p[i]=(Pixel){s*.25,c1,c2,fmax(fabs(c1),fabs(c2)),
            rgb[3*i]==0||rgb[3*i+1]==0||rgb[3*i+2]==0||
            rgb[3*i]==65535||rgb[3*i+1]==65535||rgb[3*i+2]==65535};
    }
    for(int y=2;y<height-2;y++)for(int x=2;x<width-2;x++) {
        size_t i=(size_t)y*width+x,k=((size_t)(y-2)*(width-4)+x-2)*3;
        memcpy(output+k,rgb+3*i,6);
        double near=0,lo=p[i].y,hi=lo,v1[9],v2[9];int clipped=0,j=0;
        for(int dy=-2;dy<=2;dy++)for(int dx=-2;dx<=2;dx++) {
            Pixel q=p[(size_t)(y+dy)*width+x+dx];
            near=fmax(near,q.mag);clipped|=q.clipped;
            if(abs(dx)<=1&&abs(dy)<=1){v1[j]=q.c1;v2[j++]=q.c2;lo=fmin(lo,q.y);hi=fmax(hi,q.y);}
        }
        if(clipped||near>=.16)continue;
        double contrast=(hi-lo)/fmax(hi,160.0);
        if(contrast<=.2)continue;
        double d1=median9(v1)-p[i].c1,d2=median9(v2)-p[i].c2;
        double amount=fmax(fabs(d1),fabs(d2));if(amount==0)continue;
        double weight=fmin(1.0,.005/amount)*ramp((.16-near)/.08)*ramp((contrast-.2)/.3);
        d1*=weight*(4*p[i].y+1);d2*=weight*(4*p[i].y+1);
        double corrected[3]={rgb[3*i]+nr*(3*d1-d2)*.25,
            rgb[3*i+1]-(d1+d2)*.25,rgb[3*i+2]+nb*(3*d2-d1)*.25};
        /* Reject the whole correction if it would create clipping. */
        if(corrected[0]<0||corrected[0]>65535||corrected[1]<0||corrected[1]>65535||corrected[2]<0||corrected[2]>65535)continue;
        for(int ch=0;ch<3;ch++)output[k+ch]=(uint16_t)floor(corrected[ch]+.5);
    }
    free(p);return 0;
}
