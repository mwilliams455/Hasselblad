/* Independent bounded output arithmetic. Original CPU instruction inspection
 * informed the wrap, shift and signedness contracts. No vendor binary/data.
 */
#include "output74.h"
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

static int32_t signed32(uint32_t bits){
    int32_t result;
    memcpy(&result,&bits,sizeof result);
    return result;
}
static int32_t asr14(int32_t v){
    return v>=0 ? v/16384 : (int32_t)(-((-(int64_t)v+16383)/16384));
}
static uint16_t clip_positive_u16(int32_t value){
    return value<=0 ? 0 : (uint16_t)(value>=65535?65535:value);
}
int hb74_ycc_to_rgb_pixel(uint16_t y,int16_t cr,int16_t cb,
                          double gain,uint16_t rgb[3]){
    if(!rgb)return -1;
    if(!isfinite(gain)||gain!=1.0)return -2;
    /* Native fminnm clamps Y to 65534.0 before integer conversion. */
    const uint32_t yy=y>65534u ? 65534u:(uint32_t)y;
    const int32_t fr=3*(int32_t)cr-(int32_t)cb+32768;
    const int32_t fb=3*(int32_t)cb-(int32_t)cr+32768;
    /* Native W-register multiply deliberately wraps modulo 2^32. */
    const uint32_t rp=(uint32_t)((uint64_t)(yy>>1)*(uint64_t)(uint32_t)fr);
    const uint32_t bp=(uint32_t)((uint64_t)(yy>>1)*(uint64_t)(uint32_t)fb);
    const int32_t rraw=asr14(signed32(rp));
    const int32_t braw=asr14(signed32(bp));
    const uint32_t deltabits=(yy<<2)-(uint32_t)rraw-(uint32_t)braw;
    const int32_t delta=signed32(deltabits);
    const int32_t graw=delta/2; /* Native negative correction => toward zero. */
    const uint16_t result[3]={
      signed32(rp)<0 ? 0 : clip_positive_u16(rraw),
      delta<0 ? 0 : clip_positive_u16(graw),
      signed32(bp)<0 ? 0 : clip_positive_u16(braw)
    };
    memcpy(rgb,result,sizeof result);
    return 0;
}
static int disjoint(const void *a,size_t an,const void *b,size_t bn){
    const uintptr_t x=(uintptr_t)a,v=(uintptr_t)b;
    return x<=UINTPTR_MAX-an&&v<=UINTPTR_MAX-bn&&(x+an<=v||v+bn<=x);
}
int hb74_convert_roi(const uint16_t *y,const int16_t *cr,const int16_t *cb,
       int work_width,int work_height,int work_stride,int crop_x,int crop_y,
       int out_width,int out_height,double gain,uint16_t *rgb,size_t count){
    if(!y||!cr||!cb||!rgb)return -1;
    if(!isfinite(gain)||gain!=1.0)return -2;
    if(work_width<=0||work_height<=0||work_stride<work_width||
       crop_x<0||crop_y<0||out_width<=0||out_height<=0||
       (int64_t)crop_x+out_width>work_width||
       (int64_t)crop_y+out_height>work_height)return -1;
    const size_t work_sites=(size_t)work_height*(size_t)work_stride;
    const size_t out_sites=(size_t)out_width*(size_t)out_height;
    if(work_sites>SIZE_MAX/2||out_sites>SIZE_MAX/6||count<out_sites*3)return -1;
    const size_t source_bytes=work_sites*2,output_bytes=out_sites*6;
    if(!disjoint(y,source_bytes,rgb,output_bytes)||
       !disjoint(cr,source_bytes,rgb,output_bytes)||
       !disjoint(cb,source_bytes,rgb,output_bytes))return -1;
    for(int row=0;row<out_height;++row){
        const size_t source_row=(size_t)(row+crop_y)*(size_t)work_stride+crop_x;
        for(int col=0;col<out_width;++col){
            const size_t i=source_row+(size_t)col;
            uint16_t *dst=rgb+((size_t)row*out_width+col)*3;
            /* Validated input contracts ensure this cannot fail mid-write. */
            (void)hb74_ycc_to_rgb_pixel(y[i],cr[i],cb[i],1.0,dst);
        }
    }
    return 0;
}
