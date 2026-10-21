/* SPDX-License-Identifier: MIT
 * Owned result publication, recovery, shading and bounded passive REAWB. */
#include "hb_completion.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
uint32_t hb_result_copy(unsigned char*c,enum hb_result_copy direction){
    if(!c)return HB_PREP_UNSUPPORTED;
    switch(direction){
    case HB_CONFIRM_LIVE:memcpy(c+0xb0d80,c+0xb0c48,156);memcpy(c+0xb0e1c,c+0xb0ce4,156);break;
    case HB_RESTORE_CONFIRMED:memcpy(c+0xb0c48,c+0xb0d80,156);memcpy(c+0xb0ce4,c+0xb0e1c,156);break;
    case HB_REFERENCE_TO_LIVE:memcpy(c+0xb0c48,c+0xd3d8,156);memcpy(c+0xb0ce4,c+0xd3d8,156);break;
    case HB_REFERENCE_TO_CONFIRMED:memcpy(c+0xb0d80,c+0xd3d8,156);memcpy(c+0xb0e1c,c+0xd3d8,156);break;
    default:return HB_PREP_UNSUPPORTED;
    }
    return 0;
}
uint32_t hb_outer_complete(unsigned char*c,uint32_t status,hb_completion_record*out){
    if(!c)return HB_PREP_UNSUPPORTED;
    hb_completion_record r={status,status?HB_CONFIRMED_RESTORED:HB_LIVE_PUBLISHED,0};
    w32(c+0x174,0);
    if(c[0xd338]==1){
        hb_result_copy(c,HB_REFERENCE_TO_LIVE);hb_result_copy(c,HB_REFERENCE_TO_CONFIRMED);
        c[0xd338]=0;r.origin=HB_REFERENCE_PUBLISHED;r.reference_consumed=1;
    }
    uint32_t result=hb_result_copy(c,status?HB_RESTORE_CONFIRMED:HB_CONFIRM_LIVE);
    if(out)*out=r;
    return result;
}
uint32_t hb_shading_temperature(unsigned char*c){
    if(!c)return HB_PREP_UNSUPPORTED;
    if(c[0xb0b10]!=1)return 0;
    unsigned selected=0;
    for(unsigned i=1;i<7;++i)if(u16(c+0x3da42+2*i)>=u16(c+0x3da42+2*selected))selected=i;
    unsigned reference=selected==1||selected==4||(c[0xeff8]==3&&u32(c+0xeffc)>=60);
    memcpy(c+0xb2164,c+(reference?0xf008:0xb0b6c),4);
    return 0;
}
static void diagnostic(unsigned char*c,unsigned extended){
    c[0xa86de]=1;memcpy(c+0xa86df,c+0xb696a,16);
    c[0xa86ef]=c[0xb697c];memcpy(c+0xa86f0,c+0xb697e,4);
    memcpy(c+0xa86f4,c+0xb697a,2);
    if(extended){c[0xa86f6]=c[0xb6982];memcpy(c+0xa86f7,c+0xb6984,4);memcpy(c+0xa86fb,c+0xb6988,4);}
}
uint32_t hb_reawb_passive(unsigned char*c,unsigned char*r){
    if(!c||!r)return HB_PREP_UNSUPPORTED;
    unsigned save=r[0x1d]==1,enabled=r[0x1c]==1,mode=u32(c+0x194);
    uint32_t n=u32(c+0x28);
    uint16_t confidence=n?(uint16_t)(((uint32_t)u16(c+0xb142c)<<12)/n):0;
    if((save&&confidence>122)||(enabled&&!mode&&r[0x22]==1))return HB_PREP_UNSUPPORTED;
    if(save)r[0x1e]=1;
    if(!enabled)return 0;
    if(!mode){
        if(c[0xb6968]==1)diagnostic(c,1);
        w32(r+0x3b4,u32(r+0x3b4)+1);
    }
    if(c[0xb6968]==1)diagnostic(c,0);
    return 0;
}
