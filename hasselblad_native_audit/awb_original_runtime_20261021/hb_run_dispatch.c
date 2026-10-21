/* SPDX-License-Identifier: MIT */
#include "hb_run_dispatch.h"
#include "hb_stat_difference.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
uint32_t hb_run_dispatch(unsigned char*c,const unsigned char*k,const unsigned char*r,hb_dispatch_result*out){
    if(!c||!k||!out)return HB_PREP_UNSUPPORTED;
    hb_dispatch_result result={HB_DISPATCH_RETURN,0};
    if(u32(c+0xb2020)==2){*out=result;return 0;}
    uint32_t mode=u32(c+0x194);w32(c+0x174,2);
    if(mode>=2)result.action=mode==2?HB_DISPATCH_MANUAL:HB_DISPATCH_CUSTOM;
    else{
        result.status=hb_stat_difference(c,k,r);
        if(result.status==HB_PREP_UNSUPPORTED)return result.status;
        if(result.status)result.action=HB_DISPATCH_COMPLETE_ERROR;
        else if(c[0xd328]||c[0xd32a]){
            result.action=HB_DISPATCH_AUTO_REFRESH;
            memset(c+0xa8510,0,0x34c);memset(c+0xf450,0,0x75af8);
        }else result.action=HB_DISPATCH_AUTO_REUSE;
    }
    *out=result;return 0;
}
