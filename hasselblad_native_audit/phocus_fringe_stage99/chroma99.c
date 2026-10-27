#include "chroma99.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
enum {RADIUS=15,SPAN=31,MOMENTS=9};
static double ramp(double x){return fmax(0.,fmin(1.,x));}
static void moment(const uint16_t *p,uint8_t flags,double ir,double ib,double *v){
    double r=p[0]*ir,g=p[1],b=p[2]*ib,y=(r+2*g+b)*.25;
    v[0]=r;v[1]=g;v[2]=b;v[3]=y*y;v[4]=r*y;v[5]=g*y;v[6]=b*y;
    v[7]=r*r+g*g+b*b;v[8]=(flags&2)||p[0]==65535||p[1]==65535||p[2]==65535;
}
/* New adaptation, not a recovered Phocus primitive. A coherent local RGB/luma
 * relation predicts chroma. Opposing channel slopes are genuine colour edges
 * and are excluded. Preserve normalized luma; bound each chroma move by .06.
 * Sliding column sums keep scratch memory proportional to width, not area. */
int hb99_chroma_roi(const uint16_t *rgb,size_t count,const uint8_t *flags,size_t flag_count,
    int width,int height,double nr,double nb,uint16_t *out,size_t capacity){
    if(!rgb||!flags||!out||width<SPAN||height<SPAN||width>8222||height>8222)return -1;
    if(!isfinite(nr)||!isfinite(nb)||nr<.0625||nr>16||nb<.0625||nb>16)return -2;
    size_t sites=(size_t)width*height,n=sites*3,need=(size_t)(width-30)*(height-30)*3;
    if(count<n||flag_count<sites||capacity<need)return -1;
    uintptr_t a=(uintptr_t)rgb,b=(uintptr_t)out,c=(uintptr_t)flags;
    if(a>UINTPTR_MAX-n*2||b>UINTPTR_MAX-need*2||c>UINTPTR_MAX-sites||
       !(a+n*2<=b||b+need*2<=a)||!(c+sites<=b||b+need*2<=c))return -1;
    double *columns=calloc((size_t)width*MOMENTS,sizeof(double));if(!columns)return -3;
    const double ir=1/nr,ib=1/nb,div=1./(SPAN*SPAN);
    for(int y=0;y<SPAN;y++)for(int x=0;x<width;x++){
        size_t i=(size_t)y*width+x;double m[MOMENTS];moment(rgb+3*i,flags[i],ir,ib,m);
        for(int j=0;j<MOMENTS;j++)columns[x*MOMENTS+j]+=m[j];
    }
    for(int y=RADIUS;y<height-RADIUS;y++){
        if(y>RADIUS)for(int x=0;x<width;x++){
            size_t lo=(size_t)(y-RADIUS-1)*width+x,hi=(size_t)(y+RADIUS)*width+x;
            double ml[MOMENTS],mh[MOMENTS];moment(rgb+3*lo,flags[lo],ir,ib,ml);moment(rgb+3*hi,flags[hi],ir,ib,mh);
            for(int j=0;j<MOMENTS;j++)columns[x*MOMENTS+j]+=mh[j]-ml[j];
        }
        double sums[MOMENTS]={0};
        for(int x=0;x<SPAN;x++)for(int j=0;j<MOMENTS;j++)sums[j]+=columns[x*MOMENTS+j];
        for(int x=RADIUS;x<width-RADIUS;x++){
            if(x>RADIUS)for(int j=0;j<MOMENTS;j++)sums[j]+=columns[(x+RADIUS)*MOMENTS+j]-columns[(x-RADIUS-1)*MOMENTS+j];
            size_t i=(size_t)y*width+x,k=((size_t)(y-RADIUS)*(width-30)+x-RADIUS)*3;
            const uint16_t *p=rgb+3*i;memcpy(out+k,p,6);
            if(sums[8]>0||(flags[i]&1)||!p[0]||!p[1]||!p[2])continue;
            double a0[3]={p[0]*ir,p[1],p[2]*ib},s=a0[0]+2*a0[1]+a0[2],Y=s*.25;
            double mean[3]={sums[0]*div,sums[1]*div,sums[2]*div};
            double my=(mean[0]+2*mean[1]+mean[2])*.25,var=fmax(sums[3]*div-my*my,1.);
            double fit[3],explained=0,total=sums[7]*div;int positive=1;
            for(int ch=0;ch<3;ch++){
                double cov=sums[4+ch]*div-mean[ch]*my;
                if(cov<=0)positive=0;
                fit[ch]=mean[ch]+cov/var*(Y-my);explained+=cov*cov/var;total-=mean[ch]*mean[ch];
            }
            if(!positive)continue;
            double coherence=ramp((explained/fmax(total,1.)-.9)/.08);if(coherence==0)continue;
            double lo=Y,hi=Y;
            for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++){
                const uint16_t *q=rgb+3*((size_t)(y+dy)*width+x+dx);
                double v=(q[0]*ir+2*q[1]+q[2]*ib)*.25;lo=fmin(lo,v);hi=fmax(hi,v);
            }
            double gate=ramp(((hi-lo)/fmax(hi,160.)-.2)/.3);if(gate==0)continue;
            double fs=fit[0]+2*fit[1]+fit[2];if(fs<=0)continue;
            double d1=(fit[0]-fit[1])/(fs+1)-(a0[0]-a0[1])/(s+1);
            double d2=(fit[2]-fit[1])/(fs+1)-(a0[2]-a0[1])/(s+1),amount=fmax(fabs(d1),fabs(d2));
            if(amount==0)continue;
            double weight=fmin(1.,.06/amount)*coherence*gate;
            d1*=weight*(s+1);d2*=weight*(s+1);
            double corrected[3]={(a0[0]+(3*d1-d2)*.25)*nr,a0[1]-(d1+d2)*.25,(a0[2]+(3*d2-d1)*.25)*nb};
            if(corrected[0]<0||corrected[0]>65535||corrected[1]<0||corrected[1]>65535||corrected[2]<0||corrected[2]>65535)continue;
            for(int ch=0;ch<3;ch++)out[k+ch]=(uint16_t)floor(corrected[ch]+.5);
        }
    }
    free(columns);return 0;
}
