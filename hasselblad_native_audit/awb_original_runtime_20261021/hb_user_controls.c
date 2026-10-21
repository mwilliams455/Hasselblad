/* SPDX-License-Identifier: MIT */
#include "hb_user_controls.h"
#include "hb_user_prepare.h"
#include "hb_user_manual.h"
#include "hb_post_results.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float rf(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static uint32_t fu(float v){return !(v>0)?0:(double)v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
uint32_t hb_user_ct_tint_to_gain(const unsigned char*c,const unsigned char*k,const hb_temperature_model*m,uint32_t ct,float tint,uint32_t scale,uint32_t*r,uint32_t*g,uint32_t*b){
    if(!c||!k||!m||!m->isotemperature_31x4||!r||!g||!b)return HB_PREP_UNSUPPORTED;
    const float*t=m->isotemperature_31x4;float temp=(float)ct,amount=tint/-3000.0f,mired=1000000.0f/temp;
    unsigned i=0;for(;i<29;++i)if(mired<t[4*(i+1)])break;
    const float*a=t+4*i,*z=a+4;float f=(z[0]-mired)/(z[0]-a[0]);double h=1.0-(double)f;
    float p=a[3]*a[3],q=z[3]*z[3],na=(float)sqrt((double)p+1.0),nz=(float)sqrt((double)q+1.0);
    p=f*(1.0f/na);q=f*(a[3]/na);float dx=(float)(h*(double)(1.0f/nz)+(double)p),dy=(float)(h*(double)(z[3]/nz)+(double)q);
    p=dx*dx;q=dy*dy;float norm=sqrtf(p+q),matrix[9]={0};
    uint32_t st=hb_temperature_matrix(k,c[0x990dc]==1&&k[0x133518],rf(c+0x990d8),temp,matrix);if(st)return st;
    p=a[1]*f;q=a[2]*f;float u0=(float)(h*(double)z[1]+(double)p),v0=(float)(h*(double)z[2]+(double)q);
    p=amount*(dx/norm);q=amount*(dy/norm);float u=p+u0,v=q+v0;
    double den=(double)v*-4.0;den=(double)u+den;den=den+2.0;
    float x=(float)(((double)u*1.5)/den),y=(float)((double)v/den),zz=1.0f-x;zz=zz-y;
    float rgb[3];for(unsigned j=0;j<3;++j){p=matrix[3*j]*x;q=matrix[3*j+1]*y;float s=p+q;p=zz*matrix[3*j+2];rgb[j]=s+p;}
    float peak=rgb[0]>rgb[1]?rgb[0]:rgb[1];peak=peak>rgb[2]?peak:rgb[2];
    for(unsigned j=0;j<3;++j){if((double)rgb[j]<0.00001)rgb[j]=10;else{rgb[j]=peak/rgb[j];if(rgb[j]>10)rgb[j]=10;}}
    uint32_t rr=fu(rgb[0]*(float)scale),gg=fu(rgb[1]*(float)scale),bb=fu(rgb[2]*(float)scale);*r=rr;*g=gg;*b=bb;return 0;
}
uint32_t hb_user_result_manual(unsigned char*c,const uint32_t raw[3],const uint32_t golden[3],uint32_t ct,float tint,uint32_t label,uint8_t flag){
    if(!c||!raw||!golden||label>8)return HB_PREP_UNSUPPORTED;
    /* Input triples must be separate from context. Untouched fields survive
     * the full156-byte record copy, matching the initialized original ABI. */
    for(unsigned i=0;i<3;++i){w32(c+0xb0ebc+4*i,raw[i]);w32(c+0xb0ec8+4*i,raw[i]);w32(c+0xb0f2c+4*i,golden[i]);w32(c+0xb0f38+4*i,golden[i]);}
    w32(c+0xb0f10,ct);w32(c+0xb0f14,ct);wf(c+0xb0f18,tint);wf(c+0xb0f1c,tint);w32(c+0xb0f24,u16(c+0xa84cc+2*label));c[0xb0eb8]=flag;
    memcpy(c+0xb0f54,c+0xb0eb8,156);return 0;
}
uint32_t hb_user_result_golden_snapshot(unsigned char*c){if(!c)return HB_PREP_UNSUPPORTED;memcpy(c+0xb0ee8,c+0xb0ebc,24);memcpy(c+0xb0f84,c+0xb0f58,24);return 0;}
uint32_t hb_user_result_recalibrate(unsigned char*c,unsigned correction){
    static const unsigned cal[]={0x1c0,0x300,0x2ec,0x270};static const unsigned pairs[]={0xb0ec8,0xb0ebc,0xb0f58,0xb0f64};
    if(!c||correction>3)return HB_PREP_UNSUPPORTED;uint32_t r=u32(c+cal[correction]),b=u32(c+cal[correction]+4);if(!r||!b)return 89;
    for(unsigned i=0;i<4;++i){unsigned char*p=c+pairs[i];w32(p,(u32(p)<<12)/r);w32(p+8,(u32(p+8)<<12)/b);}return 0;
}
static int calibration_supported(const unsigned char*c,const unsigned char*k){
    if(c[0x1a0]>2)return 0;
    if(c[0x2f4]==1){unsigned n=k[0x16e940];if(n<1||n>8)return 0;for(unsigned i=0;i<n;++i)if(k[0x16e944+52*i]<1||k[0x16e944+52*i]>8)return 0;}
    if(c[0x278]==1){unsigned n=c[0x27a];if(n<1||n>2)return 0;for(unsigned i=0;i<n;++i)if(c[0x27e +52*i]<1||c[0x27e +52*i]>8)return 0;}
    if(c[0x24c]==1){unsigned n=k[0x16e649];if(n<1||n>2)return 0;for(unsigned i=0;i<n;++i){const unsigned char*p=k+0x16e64c+260*i;if(p[1]<1||p[1]>8)return 0;for(unsigned j=0;j<p[1];++j)if(p[8+32*j]<1||p[8+32*j]>2)return 0;}}
    return 1;
}
static uint32_t finish(unsigned char*c,const unsigned char*k,uint32_t ct){
    w32(c+0x1bc,ct);uint32_t st=hb_update_calib_gain(c);if(st)return st;hb_user_result_golden_snapshot(c);
    if(c[0x2f4]==1){st=hb_e_nd_update_temperature(c,k);if(st)return st;st=hb_user_result_recalibrate(c,1);if(st)return st;}
    if(c[0x278]==1){st=hb_e_nd_update_unit(c);if(st)return st;st=hb_user_result_recalibrate(c,2);if(st)return st;}
    if(c[0x24c]==1){st=hb_e_nd_update_golden(c,k);if(st)return st;st=hb_user_result_recalibrate(c,3);if(st)return st;}
    st=hb_user_result_recalibrate(c,0);if(!st)c[0xc534]=1;return st;
}
static uint32_t ct_request(unsigned char*c,const unsigned char*k,const hb_temperature_model*m,unsigned with_tint){
    if(!c||!k)return HB_PREP_UNSUPPORTED;unsigned request=with_tint?0xb14cc:0xb14c4;if(c[request]!=1)return 0;
    uint32_t mode=u32(k+(with_tint?0x1c:0x18)),ct=u32(c+request+4);
    if(!with_tint)ct=ct<2000?2000:ct>10000?10000:ct;
    if(mode<=1&&(!m||!m->isotemperature_31x4||!calibration_supported(c,k)||(!mode&&(ct-2000)/100>80)))return HB_PREP_UNSUPPORTED;
    c[request]=0;if(mode>1)return 157;uint32_t raw[3],golden[3],scale=u32(k+0x80),st;float tint=0,computed=0;
    if(mode==0){unsigned i=(ct-2000)/100;raw[0]=u32(c+0xd68+16*i);raw[1]=4096;raw[2]=u32(c+0xd6c+16*i);
        st=hb_temperature_calibrated(c,k,m,raw[0],raw[1],raw[2],&computed,&tint);if(st)return st;
        st=hb_post_golden_conversion(raw[0],raw[1],raw[2],golden,golden+1,golden+2,scale,4096);if(st)return st;
    }else{tint=with_tint?rf(c+request+8):rf(c+0x1278+8*((ct-2000)/100));
        st=hb_user_ct_tint_to_gain(c,k,m,ct,tint,4096,raw,raw+1,raw+2);if(st)return st;
        st=hb_user_ct_tint_to_gain(c,k,m,ct,tint,scale,golden,golden+1,golden+2);if(st)return st;
    }
    st=hb_user_result_manual(c,raw,golden,ct,tint,8,0);if(st)return st;return finish(c,k,ct);
}
uint32_t hb_user_update_ct(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){return ct_request(c,k,m,0);}
uint32_t hb_user_update_ct_tint(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){return ct_request(c,k,m,1);}
uint32_t hb_user_update_gain(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    if(!c||!k)return HB_PREP_UNSUPPORTED;if(c[0xb14d8]!=1)return 0;
    uint32_t raw[3]={u32(c+0xb14dc),u32(c+0xb14e0),u32(c+0xb14e4)},golden[3];
    if(raw[0]&&raw[1]&&raw[2]&&(!m||!m->isotemperature_31x4))return HB_PREP_UNSUPPORTED;
    c[0xb14d8]=0;if(!raw[0]||!raw[1]||!raw[2])return 81;float ct,tint;uint32_t st=hb_temperature_calibrated(c,k,m,raw[0],raw[1],raw[2],&ct,&tint);if(st)return st;
    st=hb_post_golden_conversion(raw[0],raw[1],raw[2],golden,golden+1,golden+2,u32(k+0x80),4096);if(st)return st;
    st=hb_user_result_manual(c,raw,golden,fu(ct),tint,8,0);if(!st)c[0xc534]=1;return st;
}
uint32_t hb_user_controls(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    if(!c||!k)return HB_PREP_UNSUPPORTED;hb_user_mode_switch(c);uint32_t st=hb_user_update_ct(c,k,m);if(st)return st;
    st=hb_user_update_ct_tint(c,k,m);if(st)return st;return hb_user_update_gain(c,k,m);
}
