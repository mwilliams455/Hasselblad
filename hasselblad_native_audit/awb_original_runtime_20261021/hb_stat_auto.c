/* SPDX-License-Identifier: MIT */
#include "hb_stat_prepare.h"
#include "hb_user_manual.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static unsigned supported(const unsigned char*c,const unsigned char*k){
    if(u32(c+0x28)>1024||u32(c+0x2c)>8||(c[0x19c]&&c[0x1a0]>2)||k[0xc88]<1||k[0xc88]>15)return 0;
    for(unsigned i=0;i<k[0xc88];++i)if(u32(c+0x308+4*i)>80||(i&&u32(c+0x308+4*i)<u32(c+0x304+4*i)))return 0;
    if(c[0x278]){if(c[0x27a]<1||c[0x27a]>2)return 0;for(unsigned i=0;i<c[0x27a];++i)if(c[0x27e +52*i]<1||c[0x27e +52*i]>8)return 0;}
    if(c[0x2f4]){if(k[0x16e940]<1||k[0x16e940]>8)return 0;for(unsigned i=0;i<k[0x16e940];++i)if(k[0x16e944+52*i]<1||k[0x16e944+52*i]>8)return 0;}
    if(k[0x139e2c]&&k[0x139e2e]&&u16(c+0x990e4)>1024)return 0;return 1;
}
static uint32_t corrected(uint32_t value,uint32_t gain){uint32_t p=value*gain;return p>>28?65535:p>>12;}
static void apply(unsigned char*c,unsigned offset){
    uint32_t red=u32(c+offset),blue=u32(c+offset+4);
    for(unsigned i=0;i<u32(c+0x28);++i){unsigned char*d=c+0xf450+40*i;w32(d,corrected(u32(d),red));w32(d+8,corrected(u32(d+8),blue));}
    for(unsigned i=0;i<u32(c+0x2c);++i)if(c[0x37450+i]){unsigned char*d=c+0x37458+40*i;w32(d,corrected(u32(d),red));w32(d+8,corrected(u32(d+8),blue));}
}
uint32_t hb_stat_auto_complete(unsigned char*c,const unsigned char*k){
    if(!c||!k||!supported(c,k))return HB_PREP_UNSUPPORTED;
    hb_stat_awb_info(c);uint32_t status=hb_stat_calib_proc(c);if(status)return status;
    if(c[0x278]){status=hb_e_nd_update_unit(c);if(status)return status;apply(c,0x2ec);}else{w32(c+0x2ec,4096);w32(c+0x2f0,4096);}
    if(c[0x2f4]){status=hb_e_nd_update_temperature(c,k);if(status)return status;apply(c,0x300);}else{w32(c+0x300,4096);w32(c+0x304,4096);}
    hb_stat_ae_info(c,k);return hb_stat_auto_classify(c,k);
}
