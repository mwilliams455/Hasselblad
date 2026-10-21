/* SPDX-License-Identifier: MIT */
#include "hb_post_results.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <stddef.h>
#include <string.h>
static uint32_t u32(const unsigned char *p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const unsigned char *p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(unsigned char *p,uint32_t v){memcpy(p,&v,4);}
static void w16(unsigned char *p,uint16_t v){memcpy(p,&v,2);}
static uint32_t fu(double v){return !(v>0)?0:v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int32_t fs(double v){return isnan(v)?0:v>=2147483647.0?INT32_MAX:v<=-2147483648.0?INT32_MIN:(int32_t)v;}
uint32_t hb_post_blend_normal(unsigned char *ctx,uint32_t wa,uint32_t wb,const unsigned char *a,const unsigned char *b){
    uint32_t sum=wa+wb;if(!sum)return 132;
    float reciprocal=(float)(1.0/(double)sum);
    for(unsigned i=1;i<=9;++i){uint32_t n=u32(a+4*i)*wa+u32(b+4*i)*wb;float v=(float)n*reciprocal;w32(ctx+0x84128+4*i,fu(v));}
    ctx[0x84128]=1;return 0;
}
uint32_t hb_post_golden_conversion(uint32_t r,uint32_t g,uint32_t b,uint32_t *or,uint32_t *og,uint32_t *ob,uint32_t scale,uint32_t divisor){
    if(!or||!og||!ob)return 158;
    uint32_t x=r*scale,y=g*scale,z=b*scale;
    /* AArch64 UDIV by zero produces zero; writes retain original alias order. */
    x=divisor?x/divisor:0;y=divisor?y/divisor:0;z=divisor?z/divisor:0;
    *or=x;*ob=z;*og=y;return 0;
}
uint32_t hb_post_result_ct(unsigned char *ctx,const unsigned char *cfg,const hb_temperature_model *model){
    static const size_t channels[]={0xb0c58,0xb0c4c,0xb0cf4,0xb0ce8};
    static const size_t temperatures[]={0xb0ca4,0xb0ca0,0xb0d40,0xb0d3c};
    static const size_t tints[]={0xb0cac,0xb0ca8,0xb0d48,0xb0d44};
    for(unsigned i=0;i<4;++i){const unsigned char *p=ctx+channels[i];uint32_t r=u32(p),g=u32(p+4),b=u32(p+8);if(!r||!g||!b)return 95;
        float ct,tint;uint32_t st=hb_temperature_calibrated(ctx,cfg,model,r,g,b,&ct,&tint);if(st)return st;
        uint32_t n=(uint32_t)fs(ct);w32(ctx+temperatures[i],n);memcpy(ctx+tints[i],&tint,4);
        if(i<2){w16(ctx+(i?0xa8514:0xa851a),(uint16_t)n);memcpy(ctx+(i?0xa85d2:0xa85d6),&tint,4);}
    }
    return 0;
}
uint32_t hb_post_golden_snapshot(unsigned char *ctx){memcpy(ctx+0xb0c78,ctx+0xb0c4c,24);memcpy(ctx+0xb0d14,ctx+0xb0ce8,24);return 0;}
static uint32_t recalibrate(unsigned char *ctx,size_t calibration){
    uint32_t r=u32(ctx+calibration),b=u32(ctx+calibration+4);if(!r||!b)return 89;
    static const size_t pairs[]={0xb0c58,0xb0c4c,0xb0ce8,0xb0cf4};
    for(unsigned i=0;i<4;++i){unsigned char *p=ctx+pairs[i];w32(p,(u32(p)<<12)/r);w32(p+8,(u32(p+8)<<12)/b);}return 0;
}
uint32_t hb_post_end_temperature(unsigned char *ctx){return ctx[0x2f4]?recalibrate(ctx,0x300):0;}
uint32_t hb_post_end_unit(unsigned char *ctx){return ctx[0x278]?recalibrate(ctx,0x2ec):0;}
uint32_t hb_post_recalibrate(unsigned char *ctx){return recalibrate(ctx,0x1c0);}
uint32_t hb_post_normalize(unsigned char *ctx,const unsigned char *cfg){
    static const size_t records[]={0xb0c58,0xb0c4c,0xb0cf4,0xb0ce8,0xb0cc8,0xb0cbc,0xb0d64,0xb0d58};
    for(unsigned i=0;i<8;++i){unsigned char *p=ctx+records[i];uint32_t r=u32(p),g=u32(p+4),b=u32(p+8),minimum=r<g?r:g;minimum=minimum<b?minimum:b;
        if(!minimum)return 133;
        uint64_t scale=i<4?4096:u32(cfg+0x80);w32(p,(uint32_t)(r*scale/minimum));w32(p+4,(uint32_t)(g*scale/minimum));w32(p+8,(uint32_t)(b*scale/minimum));
    }return 0;
}
uint32_t hb_post_color_mode(unsigned char *ctx,unsigned char *cfg){
    if(!cfg[0x153c0c])return 0;
    unsigned count=cfg[0x153c10];if(count>22){count=22;cfg[0x153c10]=22;}
    uint32_t mode=u32(ctx+0xd478);unsigned index=0;
    if(mode<=count)for(unsigned i=0;i<count;++i)if(u32(cfg+0x153c14+8*i)==mode){index=u32(cfg+0x153c18+8*i)&255;break;}
    if(index>1)return HB_PREP_UNSUPPORTED;
    const unsigned char *table=cfg+0x153cc4+248*index+(u32(ctx+0x194)>1?124:0);unsigned n=table[0];
    if(n>10)return 191;if(!n)return HB_PREP_UNSUPPORTED;
    const unsigned char *first=table+4,*last=first+12*(n-1);uint32_t ct=u32(ctx+0xb0ca0),r,b;
    /* Endpoint loads are 16-bit; interpolation loads the entire 32-bit words. */
    if(ct<=u32(first)){r=u16(first+4);b=u16(first+8);}
    else if(ct>=u32(last)){r=u16(last+4);b=u16(last+8);}
    else{unsigned hi=1;while(hi<n&&ct>=u32(first+12*hi))++hi;if(hi==n)return HB_PREP_UNSUPPORTED;
        const unsigned char *lo=first+12*(hi-1),*up=lo+12;float f=(float)(ct-u32(lo))/(float)(u32(up)-u32(lo)),g=1.0f-f;
        float x=g*(float)u32(lo+4),y=f*(float)u32(up+4);r=(uint32_t)fs(x+y);
        x=g*(float)u32(lo+8);y=f*(float)u32(up+8);b=(uint32_t)fs(x+y);
    }
    w32(ctx+0xb0c4c,(u32(ctx+0xb0c4c)*r)>>12);w32(ctx+0xb0c54,(u32(ctx+0xb0c54)*b)>>12);
    w16(ctx+0xa8632,(uint16_t)r);w16(ctx+0xa8634,(uint16_t)b);return 0;
}
uint32_t hb_post_finalize(unsigned char *ctx,unsigned char *cfg,const hb_temperature_model *model){
    uint32_t st=hb_post_result_ct(ctx,cfg,model);if(st)return st;
    hb_post_golden_snapshot(ctx);st=hb_post_end_temperature(ctx);if(st)return st;
    st=hb_post_end_unit(ctx);if(st)return st;st=hb_post_recalibrate(ctx);if(st)return st;
    st=hb_post_normalize(ctx,cfg);if(st)return st;return hb_post_color_mode(ctx,cfg);
}
static uint32_t validate(unsigned char *ctx){
    static const size_t groups[]={0xb0c4c,0xb0c58,0xb0cbc,0xb0cc8,0xb0ce8,0xb0cf4,0xb0d58,0xb0d64};
    for(unsigned i=0;i<8;++i){for(unsigned j=0;j<3;++j)if(!u32(ctx+groups[i]+4*j))return 151;
        if(i==3||i==7)for(unsigned j=0;j<2;++j){unsigned char *p=ctx+(i==3?0xb0ca0:0xb0d3c)+4*j;uint32_t v=u32(p);w32(p,v<2000?2000:v>10000?10000:v);}}
    return 0;
}
uint32_t hb_post_mode2(unsigned char *ctx,unsigned char *cfg){
    if(u32(ctx+0x194)!=2)return HB_PREP_UNSUPPORTED;
    w32(ctx+0xb0cb4,0);w32(ctx+0xb0d50,0);w32(ctx+0xb0b7c,0);
    uint32_t st=hb_post_normalize(ctx,cfg);if(!st)st=hb_post_color_mode(ctx,cfg);
    if(st==HB_PREP_UNSUPPORTED)return st;
    if(!st){
        static const size_t src[]={0xb0c4c,0xb0c54,0xb0ca0,0x1c0,0x1c4,0x218,0x21c,0x244,0x248,0x270,0x274,0x2ec,0x2f0,0x300,0x304};
        static const size_t dst[]={0xa8510,0xa8512,0xa8514,0xa851e,0xa8520,0xa8522,0xa8524,0xa8526,0xa8528,0xa8848,0xa884a,0xa884c,0xa884e,0xa8850,0xa8852};
        for(unsigned i=0;i<15;++i)w16(ctx+dst[i],(uint16_t)u32(ctx+src[i]));
        w32(ctx+0xa85d2,u32(ctx+0xb0ca8));w32(ctx+0xa85ce,u32(cfg+12));ctx[0xa851c]=(unsigned char)u32(ctx+0x194);
    }
    /* The outer function returns the validation status, even after helper errors. */
    return validate(ctx);
}
