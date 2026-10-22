/* SPDX-License-Identifier: MIT
 * Owned mathematical reference — standard CIE/ICC display colourimetry,
 * independent Phocus401 selector semantics (public documentation), no
 * vendor code, no original source data, no photographic renderer.
 */
#include "hb_colour_stage19.h"
#include <math.h>
#include <stdint.h>
#include <string.h>
static int finite_v(const double *v, size_t n) {
    if (!v) return 0;
    for(size_t i=0;i<n;++i) if(!isfinite(v[i])) return 0;
    return 1;
}
static int overlaps(const void *a,size_t n,const void *b,size_t m){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=y ? y-x<n : x-y<m;
}
static int invert3(const double a[9],double b[9]) {
    double adj[9]={a[4]*a[8]-a[5]*a[7], a[2]*a[7]-a[1]*a[8], a[1]*a[5]-a[2]*a[4],
                   a[5]*a[6]-a[3]*a[8], a[0]*a[8]-a[2]*a[6], a[2]*a[3]-a[0]*a[5],
                   a[3]*a[7]-a[4]*a[6], a[1]*a[6]-a[0]*a[7], a[0]*a[4]-a[1]*a[3]};
    double det=a[0]*adj[0]+a[1]*adj[3]+a[2]*adj[6];
    if(!isfinite(det)||fabs(det)<1.e-12) return 0;
    for(size_t i=0;i<9;i++) {b[i]=adj[i]/det;if(!isfinite(b[i]))return 0;}
    return 1;
}
static void mv(const double m[9],const double v[3],double o[3]){
    for(unsigned i=0;i<3;i++)
        o[i]=m[3*i]*v[0]+m[3*i+1]*v[1]+m[3*i+2]*v[2];
}
static void mm(const double a[9],const double b[9],double c[9]){
    for(unsigned i=0;i<3;i++)for(unsigned j=0;j<3;j++) {
        double s=0;
        for(unsigned k=0;k<3;k++)s+=a[3*i+k]*b[3*k+j];
        c[3*i+j]=s;
    }
}
int hb19_build_output_matrix(int gamut, double out[9], hb19_output_receipt *receipt) {
    if(!out||!receipt)return HB19_BAD_INPUT;
    if(gamut!=HB19_SRGB&&gamut!=HB19_DISPLAY_P3)return HB19_UNSUPPORTED;
    if(overlaps(out,9*sizeof(double),receipt,sizeof(*receipt)))return HB19_OVERLAP;
    const double D50[3]={.9642,1.,.8249};
    /* D65 chromaticity (x=0.3127, y=0.3290), normalized Y=1. */
    const double D65[3]={.3127/.329,1.,(1.-.3127-.329)/.329};
    const double B[9]={.8951,.2664,-.1614,-.7502,1.7135,.0367,.0389,-.0685,1.0296};
    double invB[9];if(!invert3(B,invB))return HB19_NUMERIC_ERROR;
    double cone50[3],cone65[3];mv(B,D50,cone50);mv(B,D65,cone65);
    double scaled[9];
    for(unsigned i=0;i<3;i++) {
        if(!(cone50[i]>0)||!(cone65[i]>0))return HB19_NUMERIC_ERROR;
        for(unsigned j=0;j<3;j++)scaled[3*i+j]=B[3*i+j]*cone65[i]/cone50[i];
    }
    double cat[9];mm(invB,scaled,cat);
    /* Columns encode normalized XYZ of R/G/B primaries from xy.
     * sRGB: (0.64,0.33), (0.30,0.60), (0.15,0.06)
     * Display P3: (0.68,0.32), (0.265,0.69), (0.15,0.06)
     */
    double chroma[6];
    if(gamut==HB19_SRGB){
        const double p[6]={.64,.33,.30,.60,.15,.06};memcpy(chroma,p,sizeof(p));
    }else {
        const double p[6]={.68,.32,.265,.69,.15,.06};memcpy(chroma,p,sizeof(p));
    }
    double prim[9];
    for(unsigned channel=0;channel<3;channel++){
        double x=chroma[2*channel],y=chroma[2*channel+1];
        prim[channel]=x/y;prim[3+channel]=1.;prim[6+channel]=(1.-x-y)/y;
    }
    double invprim[9];if(!invert3(prim,invprim))return HB19_NUMERIC_ERROR;
    double s[3];mv(invprim,D65,s);
    for(unsigned i=0;i<3;i++)if(!(s[i]>0.)||!isfinite(s[i]))return HB19_NUMERIC_ERROR;
    double xyz2rgb[9];
    for(unsigned i=0;i<3;i++)for(unsigned j=0;j<3;j++)xyz2rgb[3*i+j]=prim[3*i+j]*s[j];
    double invrgb[9];if(!invert3(xyz2rgb,invrgb))return HB19_NUMERIC_ERROR;
    double result[9];mm(invrgb,cat,result);
    if(!finite_v(result,9))return HB19_NUMERIC_ERROR;
    double white[3];mv(result,D50,white);
    for(unsigned i=0;i<3;i++)if(fabs(white[i]-1.)>1.e-10)return HB19_NUMERIC_ERROR;
    hb19_output_receipt rc={HB19_SCHEMA,1,1,(uint32_t)gamut,1,0,0,0,0};
    memcpy(out,result,sizeof(result));*receipt=rc;
    return HB19_OK;
}
int hb19_apply_output_matrix(const double m[9],const double *src,size_t n,double *dst){
    if(!m||!src||!dst||n==0||n>HB19_MAX_PIXELS||
       !finite_v(m,9)||!finite_v(src,n*3))return HB19_BAD_INPUT;
    size_t bytes=n*3*sizeof(double);
    if(overlaps(m,9*sizeof(double),dst,bytes)||overlaps(src,bytes,dst,bytes))return HB19_OVERLAP;
    double vec[3];
    /* Preflight every result to make the operation transactional. */
    for(size_t i=0;i<n;i++){
        mv(m,src+i*3,vec);
        if(!finite_v(vec,3))return HB19_NUMERIC_ERROR;
    }
    for(size_t i=0;i<n;i++)mv(m,src+i*3,dst+i*3);
    return HB19_OK;
}
static void segment(const int32_t *anchors,size_t length,int32_t k,
                    uint32_t *lower,double *fraction){
    size_t hi=1;
    while(hi<length-1 && k>=anchors[hi])hi++;
    if(k>=anchors[length-1])hi=length-1;
    *lower=(uint32_t)(hi-1);
    *fraction=((double)k-anchors[hi-1])/((double)anchors[hi]-anchors[hi-1]);
}
int hb19_select_phocus_wb(double kelvin,hb19_phocus_selector *output){
    if(!output||!isfinite(kelvin)||kelvin<-1000000.||kelvin>1000000.)return HB19_BAD_INPUT;
    const int32_t a_lut[3]={3100,5550,9100};
    const int32_t a_mat[4]={2400,3100,5550,9100};
    int32_t k=(int32_t)kelvin;
    int32_t kl=k<2000?2000:k>10000?10000:k;
    int32_t km=k<2000?2000:k>8000?8000:k;
    hb19_phocus_selector sel={0};sel.schema=HB19_SCHEMA;
    sel.truncated_kelvin=k;sel.lut_effective_kelvin=kl;sel.matrix_effective_kelvin=km;
    segment(a_lut,3,kl,&sel.lut_lower_index,&sel.lut_alpha);
    segment(a_mat,4,km,&sel.matrix_lower_index,&sel.matrix_alpha);
    sel.original_phocus_payload_present=0;sel.hncs_render_authorized=0;
    *output=sel;return HB19_OK;
}
int hb19_synthetic_phocus_blend(const double *low,const double *high,
                                size_t n,double alpha,float *out){
    if(!low||!high||!out||n==0||n>HB19_MAX_SELECTOR_SAMPLES||!isfinite(alpha)||
       !finite_v(low,n)||!finite_v(high,n))return HB19_BAD_INPUT;
    size_t ob=n*sizeof(float),ib=n*sizeof(double);
    if(overlaps(low,ib,out,ob)||overlaps(high,ib,out,ob))return HB19_OVERLAP;
    for(size_t i=0;i<n;i++){
        double x=low[i]+alpha*(high[i]-low[i]);
        if(!isfinite(x)||fabs(x)>3.402823466e38)return HB19_NUMERIC_ERROR;
    }
    for(size_t i=0;i<n;i++)out[i]=(float)(low[i]+alpha*(high[i]-low[i]));
    return HB19_OK;
}
