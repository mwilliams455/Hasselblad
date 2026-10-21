/* SPDX-License-Identifier: MIT
 * Owned outer entry, fixed-result publication, cadence and E-ND change flags. */
#include "hb_run_entry.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static uint32_t fu(float v){return !(v>0)?0:(double)v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static void fixed_result(unsigned char*c,const unsigned char*k){
    uint32_t scale=u32(k+0x80);
    for(unsigned i=0;i<3;++i){uint32_t v=u32(k+0x28+4*i),golden=(v*scale)/4096;
        w32(c+0xb0c4c+4*i,v);w32(c+0xb0c58+4*i,v);
        w32(c+0xb0cbc+4*i,golden);w32(c+0xb0cc8+4*i,golden);}
    uint32_t ct=u32(k+0x34);float tint=(float)u32(k+0x38);
    w32(c+0xb0ca0,ct);w32(c+0xb0ca4,ct);wf(c+0xb0ca8,tint);wf(c+0xb0cac,tint);w32(c+0xb0cb4,u16(c+0xa84dc));
    memcpy(c+0xb0ce4,c+0xb0c48,156);memcpy(c+0xb0b10,c+0xb0c48,156);
    memcpy(c+0xb0d80,c+0xb0c48,156);memcpy(c+0xb0e1c,c+0xb0ce4,156);
    memcpy(c+0xb0eb8,c+0xb0c48,156);memcpy(c+0xb0f54,c+0xb0ce4,156);
}
uint32_t hb_run_entry(unsigned char*c,const unsigned char*k,hb_run_entry_result*out){
    if(!c||!k||!out)return HB_PREP_UNSUPPORTED;
    hb_run_entry_result result={HB_RUN_RETURN,HB_RUN_UNINITIALIZED,3};
    ++c[0xb2150];
    if(u32(c+0x170)!=1)goto done;
    result.reason=HB_RUN_BUSY;result.status=4;if(u32(c+0x174))goto done;
    result.status=0;
    if(k[0x24]!=1){fixed_result(c,k);result.reason=HB_RUN_FIXED_RESULT;goto done;}
    uint32_t warm=u32(c+0x180);if(warm<=u32(k+0x70))w32(c+0x180,warm+1);
    uint32_t skip=u32(c+0x17c);if(skip){w32(c+0x17c,skip-1);result.reason=HB_RUN_CADENCE_SKIP;goto done;}
    w32(c+0x17c,u32(c+0x184));
    if(u32(k+0x78)==1&&c[0xe0bb0]!=1){
        uint32_t now=u32(c+0x9c1a0),previous=u32(c+0x188);
        if(previous>=now){previous=now;w32(c+0x188,now);}
        uint32_t elapsed=now-previous;float denominator=elapsed?(float)elapsed:1.0f;
        uint32_t rate=fu(f32(c+0x9c1a4)/denominator);
        if((float)rate>(float)u32(k+0x7c)){result.reason=HB_RUN_RATE_SKIP;goto done;}
        w32(c+0x188,now);
    }
    unsigned enabled=c[0x990dc];c[0x24c]=c[0x278]=c[0x2f4]=0;
    if(enabled){c[0x24c]=k[0x16e648]!=0;c[0x278]=c[0x279]!=0;c[0x2f4]=k[0x16e940]!=0&&c[0xe0bb0]==0;}
    float current=f32(c+0x990d8),difference=fabsf(f32(c+0xd4bc)-current);c[0xd4c2]=0;
    if((double)difference>0.01||c[0xd4c1]!=enabled){wf(c+0xd4bc,current);c[0xd4c1]=(unsigned char)enabled;c[0xd4c2]=1;}
    result.action=HB_RUN_PREPARE;result.reason=HB_RUN_READY;
done:*out=result;return 0;
}
