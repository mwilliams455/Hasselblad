/* SPDX-License-Identifier: MIT */
#include "hb_user_finish.h"
#include "hb_user_e_nd.h"
#include "hb_user_manual.h"
#include "hb_user_controls.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
uint32_t hb_user_gain_record_valid(const unsigned char*p){
    for(unsigned i=4;i<=24;i+=4)if(!u32(p+i))return 247;
    return 246;
}
static unsigned fixed_valid(const unsigned char*c){
    return (u32(c+0xb1d54)-UINT32_C(2000))<=8000 &&
        (u32(c+0xb1d58)-UINT32_C(2000))<=8000 &&
        hb_user_gain_record_valid(c+0xb1cfc)==246 &&
        hb_user_gain_record_valid(c+0xb1d6c)==246;
}
uint32_t hb_user_finish(unsigned char*c){
    unsigned fixed=c[0xb1cf8]==1 && fixed_valid(c);
    if(fixed && c[0x1a0]>2)return HB_PREP_UNSUPPORTED;
    if(c[0xb1f84]==1){c[0xb1f84]=0;c[0x190]=c[0xb1f85];}
    if(c[0xb14f0]==1){c[0xb14f0]=0;c[0xf028]=c[0xb14f1];}
    if(c[0xb1cf8]==1){
        c[0xb1cf8]=0;c[0xd338]=(unsigned char)fixed;
        if(fixed){
            memcpy(c+0xd33c,c+0xb1cfc,156);memcpy(c+0xd3d8,c+0xb1cfc,156);
            w32(c+0x1bc,u32(c+0xd398));
            (void)hb_update_calib_gain(c); /* Supported lookup always returns0. */
            const unsigned red[]={0xd340,0xd34c,0xd3b0,0xd3bc};
            const unsigned blue[]={0xd348,0xd354,0xd3b8,0xd3c4};
            for(unsigned i=0;i<4;++i){
                w32(c+red[i],(u32(c+red[i])*u32(c+0x1c0))>>12);
                w32(c+blue[i],(u32(c+blue[i])*u32(c+0x1c4))>>12);
            }
        }
    }
    if(c[0xb1ff6]!=c[0x42d3]){c[0x42d2]=1;c[0x42d3]=c[0xb1ff6];}
    if(c[0xb1ff8]==1){
        c[0xb1ff8]=0;float ct=f32(c+0xb2000);
        unsigned valid=u32(c+0xb1ffc)<=1024 && !((ct<2000 || ct>10000) && ct!=0);
        for(unsigned i=0;i<12;++i)if(u16(c+0xb2008+2*i)>256)valid=0;
        c[0xd324]=(unsigned char)valid;
        if(valid){w32(c+0xc5a0,u32(c+0xb1ffc));w32(c+0xc6d4,u32(c+0xb2000));w32(c+0xc6e4,u32(c+0xb2004));}
    }
    return 0;
}
uint32_t hb_user_process(unsigned char*c,const unsigned char*k,const hb_temperature_model*m){
    uint32_t status=hb_user_prepare_calibration(c,k);
    if(!status)status=hb_user_manual_samples(c,k,m);
    if(!status)status=hb_user_controls(c,k,m);
    if(!status)status=hb_user_finish(c);
    return status;
}
