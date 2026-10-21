/* SPDX-License-Identifier: MIT
 * Owned user calibration imports, manual table refresh and mode requests. */
#include "hb_user_prepare.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static uint32_t divu(uint32_t a,uint32_t b){return b?a/b:0;}
static uint32_t fu(float v){return !(v>0)?0:(double)v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static uint32_t interp(uint32_t x0,uint32_t x1,uint32_t y0,uint32_t y1,float x){
    uint32_t lo=x0<x1?x0:x1,hi=x0<x1?x1:x0,a=x0<x1?y0:y1,b=x0<x1?y1:y0;
    float wa,wb;if((float)lo>=x){wa=1;wb=0;}else if((float)hi<=x){wa=0;wb=1;}else{wb=x-(float)lo;wa=(float)hi-x;}
    float sum=wb+wa;if(sum==0)return (a+b)>>1;float p=wa*(float)a,q=wb*(float)b;return fu((q+p)/sum);
}
uint32_t hb_user_calibration_gain(unsigned char*c,uint32_t ct,uint32_t*r,uint32_t*b){
    if(!c||!r||!b||c[0x1a0]>2)return HB_PREP_UNSUPPORTED;
    unsigned n=c[0x1a0];uint32_t red=4096,blue=4096;
    if(n){const unsigned char*a=c+0x1a4,*z=a+12*(n-1),*chosen=0;
        if(u32(a)>=ct)chosen=a;else if(u32(z)<=ct){chosen=z;w32(c+0x1bc,10000);}
        if(chosen){red=u32(chosen+4);blue=u32(chosen+8);}
        else{red=interp(u32(a),u32(z),u32(a+4),u32(z+4),(float)ct);blue=interp(u32(a),u32(z),u32(a+8),u32(z+8),(float)ct);}
    }
    *r=red;*b=blue;return 0;
}
uint32_t hb_user_manual_lut_refresh(unsigned char*c,const unsigned char*k){
    if(!c||!k||k[0x139cbc]>15||c[0x1a0]>2)return HB_PREP_UNSUPPORTED;
    unsigned n=k[0x139cbc];c[0x14fc]=(unsigned char)n;
    for(unsigned i=0;i<n;++i){const unsigned char*p=k+0x139cc0+16*i;unsigned char*q=c+0x1500+16*i;uint32_t ct=u32(p),r,b;
        w32(q,ct);uint32_t status=hb_user_calibration_gain(c,ct,&r,&b);if(status)return status;
        w32(q+4,divu(u32(p+4)<<12,r));w32(q+8,divu(u32(p+8)<<12,b));w32(q+12,u32(p+12));}
    return 0;
}
static uint32_t ratios(const unsigned char*p,unsigned n,uint32_t rows[2][3]){
    for(unsigned i=0;i<n;++i){const unsigned char*q=p+20*i;uint32_t rr=u32(q+4),bb=u32(q+8),rd=u32(q+12),bd=u32(q+16);
        if(!rr||!bb||!rd||!bd)return 83;
        rows[i][0]=u32(q);rows[i][1]=(rr<<12)/rd;rows[i][2]=(bb<<12)/bd;}
    if(n==2&&rows[0][0]>rows[1][0])for(unsigned j=0;j<3;++j){uint32_t x=rows[0][j];rows[0][j]=rows[1][j];rows[1][j]=x;}
    return 0;
}
uint32_t hb_user_base_calibration(unsigned char*c,const unsigned char*k){
    if(!c||!k)return HB_PREP_UNSUPPORTED;if(c[0xb1430]!=1)return 0;
    unsigned n=c[0xb1434];if(n>2||k[0x139cbc]>15)return HB_PREP_UNSUPPORTED;
    c[0xb1430]=0;uint32_t rows[2][3]={{0}};uint32_t status=ratios(c+0xb1438,n,rows);if(status)return status;
    for(unsigned i=0;i<n;++i)memcpy(c+0x1a4+12*i,rows[i],12);
    w32(c+0x1a0,n);c[0x19c]=1;return hb_user_manual_lut_refresh(c,k);
}
static uint32_t end_groups(unsigned char*c){
    unsigned groups=u16(c+0xb14c0);if(!groups)return 0;
    for(unsigned i=0;i<groups;++i){unsigned char*p=c+0xb1460+48*i,*q=c+0x1f4+44*i;
        if(p[0]!=1)return 0;
        unsigned n=p[4];p[0]=0;uint32_t rows[2][3]={{0}};uint32_t status=ratios(p+8,n,rows);if(status)return status;
        for(unsigned j=0;j<n;++j)memcpy(q+8+12*j,rows[j],12);
        w32(q+4,n);q[0]=1;
    }
    c[0x19c]=0;return 0;
}
static uint32_t temperature_rows(unsigned char*c){
    if(c[0xb1d98]!=1)return 0;
    unsigned n=c[0xb1d9c];c[0xb1d98]=0;uint32_t rows[2][11]={{0}};
    for(unsigned i=0;i<n;++i){const unsigned char*p=c+0xb1da0+84*i;rows[i][0]=u32(p);
        for(unsigned j=0;j<10;++j){uint32_t a=u32(p+4+4*j),b=u32(p+44+4*j);if(!a||!b)return 84;rows[i][j+1]=(a<<12)/b;}}
    if(n==2&&rows[0][0]>rows[1][0])for(unsigned j=0;j<11;++j){uint32_t x=rows[0][j];rows[0][j]=rows[1][j];rows[1][j]=x;}
    for(unsigned i=0;i<n;++i)memcpy(c+0xc5ac+44*i,rows[i],44);
    c[0xc5a8]=(unsigned char)n;c[0xc5a4]=1;return 0;
}
uint32_t hb_user_prepare_prefix(unsigned char*c,const unsigned char*k){
    if(!c||!k)return HB_PREP_UNSUPPORTED;
    if(c[0xb1430]==1&&(c[0xb1434]>2||k[0x139cbc]>15))return HB_PREP_UNSUPPORTED;
    unsigned groups=u16(c+0xb14c0);if(groups>2)return HB_PREP_UNSUPPORTED;
    for(unsigned i=0;i<groups;++i){const unsigned char*p=c+0xb1460+48*i;if(p[0]!=1)break;if(p[4]>2)return HB_PREP_UNSUPPORTED;}
    if(c[0xb1d98]==1&&(c[0xb1d9c]<1||c[0xb1d9c]>2))return HB_PREP_UNSUPPORTED;
    uint32_t status=hb_user_base_calibration(c,k);if(status)return status;
    status=end_groups(c);if(status)return status;return temperature_rows(c);
}
void hb_user_mode_switch(unsigned char*c){
    if(!c||c[0xb14e8]!=1)return;
    c[0xb14e8]=0;uint32_t old=u32(c+0x194),next=u32(c+0xb14ec);
    if(old!=next){w32(c+0x198,old);w32(c+0x194,next);}
    c[0xb14c5]=c[0xb14c4]==1;c[0xb14cd]=c[0xb14cc]==1;c[0xb14d9]=c[0xb14d8]==1;
}
