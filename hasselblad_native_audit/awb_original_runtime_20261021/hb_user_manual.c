/* SPDX-License-Identifier: MIT */
#include "hb_user_manual.h"
#include "hb_user_e_nd.h"
#include "hb_user_prepare.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t fu(float v){return !(v>0)?0:(double)v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int32_t fs(float v){return isnan(v)?0:(double)v>=2147483647.0?INT32_MAX:(double)v<=-2147483648.0?INT32_MIN:(int32_t)v;}
static uint32_t interp(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x){
    uint32_t lo=x0<x1?x0:x1,hi=x0<x1?x1:x0,a=x0<x1?y0:y1,b=x0<x1?y1:y0;
    float wa,wb;if((float)lo>=x){wa=1;wb=0;}else if((float)hi<=x){wa=0;wb=1;}else{wb=x-(float)lo;wa=(float)hi-x;}
    float sum=wb+wa;if(sum==0)return (a+b)>>1;float p=wa*(float)a,q=wb*(float)b;return fu((q+p)/sum);
}
static int golden_row_ok(const unsigned char*p){
    if(p[1]<1||p[1]>8)return 0;
    for(unsigned i=0;i<p[1];++i)if(p[8+32*i]<1||p[8+32*i]>2)return 0;
    return 1;
}
uint32_t hb_e_nd_golden_ct_gain(const unsigned char*p,uint32_t ct,uint32_t*r,uint32_t*b){
    if(!p||!r||!b||p[4]<1||p[4]>2)return HB_PREP_UNSUPPORTED;
    unsigned n=p[4];const unsigned char*a=p+8,*z=a+12*(n-1),*chosen=0;
    if(u32(a)>=ct)chosen=a;else if(u32(z)<=ct)chosen=z;
    uint32_t red,blue;if(chosen){red=u32(chosen+4);blue=u32(chosen+8);}
    else{red=interp(u32(a),u32(z),u32(a+4),u32(z+4),(float)ct);blue=interp(u32(a),u32(z),u32(a+8),u32(z+8),(float)ct);}
    *r=red;*b=blue;return 0;
}
uint32_t hb_e_nd_golden_amount_gain(const unsigned char*p,uint32_t ct,float amount,uint32_t*r,uint32_t*b){
    if(!p||!r||!b||!golden_row_ok(p))return HB_PREP_UNSUPPORTED;
    unsigned n=p[1],lo=0,hi=n-1;
    if((float)u32(p+4)>=amount)hi=0;else if((float)u32(p+4+32*hi)<=amount)lo=hi;
    else if(n<2)hi=0;else{for(unsigned i=1;i<n;++i){hi=i;if((float)u32(p+4+32*i)>=amount)break;lo=i;}}
    const unsigned char*a=p+4+32*lo,*z=p+4+32*hi;uint32_t ar,ab,zr,zb;
    hb_e_nd_golden_ct_gain(a,ct,&ar,&ab);hb_e_nd_golden_ct_gain(z,ct,&zr,&zb);
    /* Original selects with uint32 amounts, then interpolates with BYTE keys. */
    uint32_t red=interp(a[0],z[0],ar,zr,amount),blue=interp(a[0],z[0],ab,zb,amount);
    *r=red;*b=blue;return 0;
}
static int temp_ok(const unsigned char*k){
    unsigned n=k[0x16e940];if(n<1||n>8)return 0;
    for(unsigned i=0;i<n;++i){unsigned m=k[0x16e944+52*i];if(m<1||m>8)return 0;}return 1;
}
static int unit_ok(const unsigned char*c){
    unsigned n=c[0x27a];if(n<1||n>2)return 0;
    for(unsigned i=0;i<n;++i){unsigned m=c[0x27e +52*i];if(m<1||m>8)return 0;}return 1;
}
static int golden_ok(const unsigned char*k){
    unsigned n=k[0x16e649];if(n<1||n>2)return 0;
    for(unsigned i=0;i<n;++i)if(!golden_row_ok(k+0x16e64c+260*i))return 0;return 1;
}
uint32_t hb_e_nd_update_temperature(unsigned char*c,const unsigned char*k){
    if(!c||!k||!temp_ok(k))return HB_PREP_UNSUPPORTED;
    float amount=rf(c+0x990d8),temperature=rf(c+0x990e0);uint32_t r,b;
    w32(c+0x2fc,u32(c+0x990d8));w32(c+0x2f8,u32(c+0x990e0));
    uint32_t st=hb_e_nd_temp_gain(k,amount,temperature,&r,&b);if(st)return st;
    w32(c+0x300,r);w32(c+0x304,b);return 0;
}
uint32_t hb_e_nd_update_unit(unsigned char*c){
    if(!c||!unit_ok(c))return HB_PREP_UNSUPPORTED;
    uint32_t ct=u32(c+0x1bc)&65535;float amount=rf(c+0x990d8);unsigned n=c[0x27a],lo=0,hi=n-1;
    w16(c+0x2e4,(uint16_t)ct);w32(c+0x2e8,u32(c+0x990d8));const unsigned char*p=c+0x27c;
    if(u16(p)>=ct)hi=0;else if(u16(p+52*hi)<=ct)lo=hi;
    else if(n<2)hi=0;else{for(unsigned i=1;i<n;++i){hi=i;if(u16(p+52*i)>=ct)break;lo=i;}}
    const unsigned char*a=p+52*lo,*z=p+52*hi;uint32_t ar,ab,zr,zb;
    hb_e_nd_temp_row_gain(a,amount,&ar,&ab);hb_e_nd_temp_row_gain(z,amount,&zr,&zb);
    /* CT selection uses uint16 keys; interpolation uses their low bytes. */
    w32(c+0x2ec,interp(a[0],z[0],ar,zr,(float)ct));w32(c+0x2f0,interp(a[0],z[0],ab,zb,(float)ct));return 0;
}
uint32_t hb_e_nd_update_golden(unsigned char*c,const unsigned char*k){
    if(!c||!k||!golden_ok(k))return HB_PREP_UNSUPPORTED;
    uint32_t ct=u32(c+0x1bc);float axis=rf(c+0x990d4),amount=rf(c+0x990d8);unsigned n=k[0x16e649],lo=0,hi=n-1;
    const unsigned char*p=k+0x16e64c;w32(c+0x26c,ct);
    if((float)p[0]>=axis)hi=0;else if((float)p[260*hi]<=axis)lo=hi;
    else if(n<2)hi=0;else{for(unsigned i=1;i<n;++i){hi=i;if((float)p[260*i]>=axis)break;lo=i;}}
    const unsigned char*a=p+260*lo,*z=p+260*hi;uint32_t ar,ab,zr,zb;
    hb_e_nd_golden_amount_gain(a,ct,amount,&ar,&ab);hb_e_nd_golden_amount_gain(z,ct,amount,&zr,&zb);
    w32(c+0x270,interp(a[0],z[0],ar,zr,axis));w32(c+0x274,interp(a[0],z[0],ab,zb,axis));return 0;
}
static uint32_t scaled(uint32_t a,uint32_t b){return (a*b)>>12;}
uint32_t hb_user_manual_samples(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    if(!c||!k)return HB_PREP_UNSUPPORTED;unsigned n=u16(c+0xb14f4);
    if(!n&&c[0xb14f2]!=1){c[0xb0ff0]=0;return 0;}
    if(n>64||u32(c+0x28)>1024||c[0x1a0]>2||!m||!m->isotemperature_31x4
       ||(c[0x2f4]==1&&!temp_ok(k))||(c[0x278]==1&&!unit_ok(c))||(c[0x24c]==1&&!golden_ok(k)))return HB_PREP_UNSUPPORTED;
    c[0xb14f2]=0;uint32_t r,b;uint32_t st=hb_user_calibration_gain(c,u32(c+0xb0ff4),&r,&b);if(st)return st;
    if(c[0x2f4]==1){st=hb_e_nd_update_temperature(c,k);if(st)return st;}
    if(c[0x278]==1){st=hb_e_nd_update_unit(c);if(st)return st;}
    if(c[0x24c]==1){st=hb_e_nd_update_golden(c,k);if(st)return st;}
    uint32_t sumr=0,sumb=0,count=0;
    for(unsigned i=0;i<n;++i){unsigned index=u16(c+0xb14f6+2*i);if(index>=u32(c+0x28))continue;
        const unsigned char*p=c+0x84f48+20*index;uint32_t rr=u32(p),bb=u32(p+8),valid=u32(p+16);if(!rr||!bb||!valid)continue;
        rr=scaled(rr,r);bb=scaled(bb,b);
        if(c[0x24c]==1){rr=scaled(rr,u32(c+0x270));bb=scaled(bb,u32(c+0x274));}
        if(c[0x278]==1){rr=scaled(rr,u32(c+0x2ec));bb=scaled(bb,u32(c+0x2f0));}
        if(c[0x2f4]==1){rr=scaled(rr,u32(c+0x300));bb=scaled(bb,u32(c+0x304));}
        sumr+=rr;sumb+=bb;++count;
    }
    if(!count){c[0xb0ff0]=0;return 0;}
    r=sumr/count;b=sumb/count;float ct=0,tint=0;
    (void)hb_temperature_calibrated(c,k,m,r,4096,b,&ct,&tint);
    if(ct<2000)ct=2000;else if(ct>10000)ct=10000;
    if(tint<-99)tint=-99;else if(tint>99)tint=99;
    w32(c+0xb0ffc,r);w32(c+0xb1000,b);w32(c+0xb0ff4,fu(ct));w32(c+0xb0ff8,(uint32_t)fs(tint));c[0xb0ff0]=1;return 0;
}
