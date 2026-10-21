/* SPDX-License-Identifier: MIT */
#include "hb_stat_difference.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static int16_t i16(const void*p){int16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static uint32_t delta(uint32_t a,uint32_t b){uint32_t d=a-b;return d&UINT32_C(0x80000000)?0-d:d;}
uint32_t hb_stat_difference(unsigned char*c,const unsigned char*k,const unsigned char*r){
    if(!c||!k)return HB_PREP_UNSUPPORTED;
    uint32_t n=u32(c+0x28),rois=u32(c+0x2c);
    if(n>1024||rois>12)return HB_PREP_UNSUPPORTED;
    unsigned forced=r&&r[0x1c]==1&&r[0x20]==0;
    unsigned enabled=k[0x1531a8]&&k[0x1531ac],active_roi=0;
    int32_t timer=(int32_t)i16(c+0xef3e)-1;
    uint32_t frame=u32(c+0x9c1a0),period=k[0x1531ad];
    /* ARM UDIV by zero yields zero, so its remainder is the frame itself. */
    unsigned periodic=(period?frame%period:frame)==1;
    if(!forced&&enabled){
        for(uint32_t i=0;i<rois;++i)if(c[0x98f48+32*i]){active_roi=1;break;}
        if(!active_roi&&timer<0&&!c[0xdb60]&&!u32(c+0xeeac)&&!periodic&&!n)return HB_PREP_UNSUPPORTED;
    }
    if(u16(c+0xb6962))w32(c+0xb6964,u32(c+0xb6964)+1);
    if(forced){c[0xd328]=1;return 0;}
    if(!enabled){c[0xd328]=1;return r?0:UINT32_MAX;}
    if(active_roi){c[0xef3c]=1;w16(c+0xef3e,30);}
    else if(timer>=0){c[0xef3c]=1;w16(c+0xef3e,(uint16_t)timer);}
    else if(c[0xdb60]||u32(c+0xeeac)){c[0xef3c]=1;w16(c+0xef3e,30);}
    else c[0xef3c]=0; /* Expired timer is retained, not decremented below0. */
    if(c[0xef3c]==1||periodic){c[0xd328]=1;return 0;}
    uint32_t sum=0;
    for(uint32_t i=0;i<n;++i){
        sum+=delta(u32(c+0x84f48+20*i),u32(c+0xf450+40*i));
        sum+=delta(u32(c+0x84f50+20*i),u32(c+0xf458+40*i));
    }
    if(sum/n<=u32(k+0x1531b0))c[0xd328]=0;
    else{
        unsigned char old=c[0xd328];
        c[0xd328]=(f32(c+0x9c1a4)>=30&&c[0xd329]==1)?0:1;
        c[0xd329]=old;
    }
    return 0;
}
