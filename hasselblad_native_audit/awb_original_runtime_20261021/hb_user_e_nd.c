/* SPDX-License-Identifier: MIT
 * Owned E-ND temperature interpolation and per-unit calibration request. */
#include "hb_user_e_nd.h"
#include "hb_user_prepare.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static int16_t i16(const void*p){int16_t v;memcpy(&v,p,2);return v;}
static float rf(const void*p){float v;memcpy(&v,p,4);return v;}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t interp(int32_t x0,int32_t x1,uint32_t y0,uint32_t y1,float x){
    int32_t lo=x0<x1?x0:x1,hi=x0<x1?x1:x0;uint32_t a=x0<x1?y0:y1,b=x0<x1?y1:y0;
    float wa,wb;if((float)lo>=x){wa=1;wb=0;}else if((float)hi<=x){wa=0;wb=1;}else{wb=x-(float)lo;wa=(float)hi-x;}
    float sum=wa+wb;if(sum==0)return (a+b)>>1;
    float p=wa*(float)a,q=wb*(float)b,v=(q+p)/sum;
    /* All y endpoints originate in uint16 tables. NaN converts to zero. */
    return v>0?(uint32_t)v:0;
}
static unsigned temp_supported(const unsigned char*k){
    unsigned n=k[0x16e940];if(n>8)return 0;
    for(unsigned i=0;i<n;++i){unsigned points=k[0x16e944+52*i];if(points<1||points>8)return 0;}
    return 1;
}
uint32_t hb_e_nd_temp_row_gain(const unsigned char*p,float amount,uint32_t*r,uint32_t*b){
    if(!p||!r||!b||p[2]<1||p[2]>8)return HB_PREP_UNSUPPORTED;
    unsigned n=p[2],lo=0,hi=n-1,endpoint=0;
    if((float)u16(p+4)>=amount){hi=0;endpoint=1;}
    else if((float)u16(p+4+6*hi)<=amount){lo=hi;endpoint=1;}
    else{for(unsigned i=1;i<n;++i)if((float)u16(p+4+6*i)>amount){lo=i-1;hi=i;break;}}
    const unsigned char*a=p+4+6*lo,*z=p+4+6*hi;
    uint32_t red,blue;if(endpoint){red=u16(a+2);blue=u16(a+4);}
    else{red=interp(u16(a),u16(z),u16(a+2),u16(z+2),amount);blue=interp(u16(a),u16(z),u16(a+4),u16(z+4),amount);}
    *r=red;*b=blue;return 0;
}
uint32_t hb_e_nd_temp_gain(const unsigned char*k,float amount,float temperature,uint32_t*r,uint32_t*b){
    if(!k||!r||!b||!temp_supported(k))return HB_PREP_UNSUPPORTED;
    unsigned n=k[0x16e940];if(!n){*r=4096;*b=4096;return 0;}
    unsigned lo=0,hi=n-1;const unsigned char*p=k+0x16e942;
    if((float)i16(p)>=temperature)hi=0;
    else if((float)i16(p+52*hi)<=temperature)lo=hi;
    else if(n<2)hi=0;
    else{lo=0;for(unsigned i=1;i<n;++i){hi=i;if((float)i16(p+52*i)>=temperature)break;lo=i;}}
    uint32_t ar,ab,zr,zb;hb_e_nd_temp_row_gain(p+52*lo,amount,&ar,&ab);hb_e_nd_temp_row_gain(p+52*hi,amount,&zr,&zb);
    uint32_t red=interp(i16(p+52*lo),i16(p+52*hi),ar,zr,temperature),blue=interp(i16(p+52*lo),i16(p+52*hi),ab,zb,temperature);
    *r=red;*b=blue;return 0;
}
static const unsigned char *profile(const unsigned char*c,const unsigned char*k){
    uint16_t key=u16(c+0xb1f88);
    for(unsigned i=0;i<k[0x16e854];++i){const unsigned char*p=k+0x16e858+116*i;if(u16(p)==key)return p;}
    return 0;
}
static unsigned request_supported(const unsigned char*c,const unsigned char*k){
    if(c[0xb1f86]!=1)return 1;
    if(k[0x16e854]>2)return 0;
    const unsigned char*p=profile(c,k);if(!p)return 1;
    unsigned n=u16(c+0xb1f8a);if(n!=u16(p+8))return 1;
    if(n>2||!temp_supported(k))return 0;
    for(unsigned i=0;i<n;++i){const unsigned char*a=c+0xb1f8c+52*i,*z=p+10+52*i;
        if(u16(a)!=u16(z)||u16(a+2)!=u16(z+2))break;
        if(u16(a+2)>8)return 0;}
    return 1;
}
static uint32_t scaled(uint32_t gain,uint16_t sample){return (gain*(uint32_t)sample)>>12;}
static uint32_t ratio(uint32_t base,uint32_t sample,uint32_t refbase,uint32_t refsample){return ((refsample*base/sample)<<12)/refbase;}
uint32_t hb_user_e_nd_unit_request(unsigned char*c,const unsigned char*k){
    if(!c||!k||!request_supported(c,k))return HB_PREP_UNSUPPORTED;
    if(c[0xb1f86]!=1)return 0;
    c[0xb1f86]=0;const unsigned char*p=profile(c,k);unsigned valid=0;if(!p)goto finish;
    unsigned groups=u16(c+0xb1f8a);w16(c+0x27a,(uint16_t)groups);if(groups!=u16(p+8))goto finish;
    float temperature=(float)(u16(c+0xb1ff4)/10);if(temperature<20)temperature=20;else if(temperature>30)temperature=30;
    float reference=rf(p+4);uint32_t cr,cb,rr,rb;
    hb_e_nd_temp_gain(k,1,temperature,&cr,&cb);hb_e_nd_temp_gain(k,1,reference,&rr,&rb);
    for(unsigned i=0;i<groups;++i){const unsigned char*a=c+0xb1f8c+52*i,*z=p+10+52*i;unsigned char*out=c+0x27c+52*i;
        uint16_t key=u16(a),n=u16(a+2);if(key!=u16(z))goto finish;w16(out,key);
        if(n!=u16(z+2))goto finish;w16(out+2,n);
        for(unsigned j=0;j<n;++j){const unsigned char*x=a+4+6*j,*y=z+4+6*j;unsigned char*q=out+4+6*j;
            uint16_t amount=u16(x);if(amount!=u16(y))goto finish;w16(q,amount);
            if(!j){if(amount!=1)goto finish;w16(q+2,4096);w16(q+4,4096);continue;}
            uint32_t pr,pb,sr,sb;hb_e_nd_temp_gain(k,(float)amount,temperature,&pr,&pb);hb_e_nd_temp_gain(k,(float)amount,reference,&sr,&sb);
            uint32_t br=scaled(cr,u16(a+6)),nr=scaled(pr,u16(x+2)),brr=scaled(rr,u16(z+6)),nrr=scaled(sr,u16(y+2));
            if(!br||!nr||!brr||!nrr)goto finish;
            uint32_t red=ratio(br,nr,brr,nrr);w16(q+2,(uint16_t)red);
            uint32_t bb=scaled(cb,u16(a+8)),nb=scaled(pb,u16(x+4)),bbr=scaled(rb,u16(z+8)),nbr=scaled(sb,u16(y+4));
            if(!bb||!nb||!bbr||!nbr)goto finish;
            uint32_t blue=ratio(bb,nb,bbr,nbr);w16(q+4,(uint16_t)blue);
            if(!(uint16_t)red||!(uint16_t)blue)goto finish;
        }
    }
    valid=1;
finish:
    c[0x279]=(unsigned char)valid;c[0x278]=(unsigned char)(c[0x990dc]!=0&&valid);return 0;
}
uint32_t hb_user_prepare_calibration(unsigned char*c,const unsigned char*k){
    if(!c||!k||!request_supported(c,k))return HB_PREP_UNSUPPORTED;
    uint32_t status=hb_user_prepare_prefix(c,k);if(status)return status;
    return hb_user_e_nd_unit_request(c,k);
}
