/* SPDX-License-Identifier: MIT */
#include "hb_phone_stage5_basis.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* Round-to-nearest-even IEEE float32 -> binary16 and back; no fp16 dependency
 * in the Android or host ABI. Subnormal path is handled rather than flushed. */
static uint16_t half_bits(float value) {
    uint32_t x;memcpy(&x,&value,4);
    uint32_t sign=(x>>16)&0x8000u, e=(x>>23)&255u, m=x&0x7fffffu;
    if (e==255u) return (uint16_t)(sign|(m?0x7e00u:0x7c00u));
    int exp=(int)e-127+15;
    if (exp>=31) return (uint16_t)(sign|0x7c00u);
    if (exp<=0) {
        if (exp < -10) return (uint16_t)sign;
        m|=0x800000u;
        uint32_t shift=(uint32_t)(14-exp);
        uint32_t upper=m>>shift, rem=m&((1u<<shift)-1u);
        uint32_t half=1u<<(shift-1u);
        if (rem>half || (rem==half&&(upper&1u))) ++upper;
        return (uint16_t)(sign|upper);
    }
    uint32_t upper=m>>13,rem=m&8191u;
    if (rem>4096u || (rem==4096u && (upper&1u))) ++upper;
    uint32_t result=((uint32_t)exp<<10)+upper;
    return (uint16_t)(sign|result);
}
static float from_half(uint16_t h) {
    uint32_t sign=((uint32_t)h&0x8000u)<<16, e=(h>>10)&31u, m=h&1023u;
    uint32_t out;
    if (!e) {
        if (!m)out=sign;
        else {
            int exp=-14;
            while ((m&1024u)==0u) {m<<=1;--exp;}
            out=sign|((uint32_t)(exp+127)<<23)|((m&1023u)<<13);
        }
    } else if(e==31u)out=sign|0x7f800000u|(m<<13);
    else out=sign|((e+112u)<<23)|(m<<13);
    float value;memcpy(&value,&out,4);return value;
}
static float fp16(float x){return from_half(half_bits(x));}
static void gl_coord(uint32_t coord,uint32_t frame_size,uint32_t n,
                     uint32_t *low,uint32_t *high,double *mix) {
    /* For valid integer pixel coords, exact CPU reference to GL_LINEAR / clamp.
     * Do not silently switch to the commonly used (n-1)/(size-1) formula. */
    double x=(double)coord*(double)n/(double)frame_size - 0.5;
    double base=floor(x);
    int64_t k=(int64_t)base;
    *mix=x-base;
    *low=(uint32_t)(k<0?0:k>=(int64_t)n?(int64_t)n-1:k);
    ++k;
    *high=(uint32_t)(k<0?0:k>=(int64_t)n?(int64_t)n-1:k);
}
static double texture_component(const float *map,uint32_t n,
    uint32_t x0,uint32_t x1,double fx,
    uint32_t y0,uint32_t y1,double fy,uint32_t channel) {
    double a=map[((size_t)y0*n+x0)*4+channel];
    double b=map[((size_t)y0*n+x1)*4+channel];
    double c=map[((size_t)y1*n+x0)*4+channel];
    double d=map[((size_t)y1*n+x1)*4+channel];
    return (1.0-fy)*((1.0-fx)*a+fx*b)+fy*((1.0-fx)*c+fx*d);
}
int hb_s5_project(const hb_s5_input *in,hb_s5_result *out) {
    if (!in || !out || !in->raw_le16 || !in->lens_map_rg_gb_b)return HB_S5_ARGUMENT;
    if(!in->proven_sensor_and_frame||!in->original_single_raw||!in->timestamp_ns||
       in->exposure_ns<1000||in->exposure_ns>UINT64_C(60000000000)||
       in->ISO==0||in->ISO>409600)return HB_S5_UNPROVEN;
    uint64_t pixels=(uint64_t)in->width*in->height;
    if(in->width<64||in->height<64||(in->width%64u)||(in->height%64u)||
       pixels>UINT64_C(32000000)||in->cfa!=0||
       in->row_stride_bytes!=(uint64_t)in->width*2u||
       in->raw_bytes!=(uint64_t)in->row_stride_bytes*in->height||
       in->black_raw_code>=in->white_raw_code||in->white_raw_code>65535u||
       in->map_width<2||in->map_width>32||in->map_height<2||in->map_height>32||
       (in->study_basis!=HB_S5_RAW&&in->study_basis!=HB_S5_PHOTON_RELATIVE))
       return HB_S5_UNSUPPORTED_GEOMETRY;
    size_t map_count=(size_t)in->map_width*in->map_height*4u;
    if (in->map_floats!=map_count)return HB_S5_INVALID_MAP;
    float map[32*32*4];
    for(size_t i=0;i<map_count;++i) {
        float value=in->lens_map_rg_gb_b[i];
        if(!isfinite(value)||value<=0||value>16.0f)return HB_S5_INVALID_MAP;
        map[i]=fp16(value);
        if(!isfinite(map[i])||map[i]<=0)return HB_S5_INVALID_MAP;
    }
    hb_s5_result *result=calloc(1,sizeof(*result));
    if(!result)return HB_S5_MEMORY;
    result->schema=HB_S5_SCHEMA;result->study_basis=in->study_basis;
    result->study_only=1;result->render_permitted=0;
    result->map_quantized_as_fp16=1;result->green_channel_average=1;
    hb_ns_frame *outframe=&result->observation;
    outframe->sensor_timestamp_ns=in->timestamp_ns;
    outframe->exposure_time_ns=in->exposure_ns;outframe->ISO=in->ISO;
    outframe->bound_to_physical_sensor_and_frame=1;
    outframe->original_single_raw_proven=1;
    outframe->basis=in->study_basis==HB_S5_RAW ?
      HB_NS_BASIS_UNSHADED_SENSOR:HB_NS_BASIS_HYPOTHETICAL_SHADED_STATISTICS;
    uint32_t block_w=in->width/32u,block_h=in->height/32u;
    double sums[1024][4]={{0}};
    uint8_t flags[1024]={0};
    const double norm=(double)(in->white_raw_code-in->black_raw_code);
    for(uint32_t y=0;y<in->height;++y) {
        uint32_t y0,y1;
        double fy;
        gl_coord(y,in->height,in->map_height,&y0,&y1,&fy);
        for(uint32_t x=0;x<in->width;++x) {
            uint32_t x0,x1;
            double fx;
            gl_coord(x,in->width,in->map_width,&x0,&x1,&fx);
            uint32_t block=(y/block_h)*32u+(x/block_w);
            uint32_t site=((y&1u)<<1)|(x&1u);
            size_t off=(size_t)y*in->row_stride_bytes+(size_t)x*2u;
            uint32_t sample=(uint32_t)in->raw_le16[off]|((uint32_t)in->raw_le16[off+1]<<8);
            if(sample<=in->black_raw_code)flags[block]|=1u;
            if(sample>=in->white_raw_code)flags[block]|=2u;
            double value=((double)sample-in->black_raw_code)/norm;
            if(in->study_basis==HB_S5_PHOTON_RELATIVE) {
                double red=texture_component(map,in->map_width,x0,x1,fx,y0,y1,fy,0);
                double green=0.5*(texture_component(map,in->map_width,x0,x1,fx,y0,y1,fy,1)+
                                  texture_component(map,in->map_width,x0,x1,fx,y0,y1,fy,2));
                double blue=texture_component(map,in->map_width,x0,x1,fx,y0,y1,fy,3);
                double avg=(red+green+blue)/3.;
                value*=(site==0?red:site==3?blue:green)/fmax(avg,1.e-4);
            }
            sums[block][site]+=value;
        }
    }
    uint32_t pixels_per_site=(block_w/2u)*(block_h/2u);
    if(pixels_per_site==0){free(result);return HB_S5_UNSUPPORTED_GEOMETRY;}
    result->observed_pixels=(uint32_t)pixels;
    for(uint32_t i=0;i<1024;++i) {
        hb_ns_block *b=&outframe->blocks[i];
        for(uint32_t k=0;k<4;++k)b->mean[k]=sums[i][k]/pixels_per_site;
        b->mean_brightness=(b->mean[0]+b->mean[1]+b->mean[2]+b->mean[3])/4.;
        b->raw_flags=flags[i];
        if(b->raw_flags&2u)++result->saturated_blocks;
        double green=(b->mean[1]+b->mean[2])*0.5;
        if(!b->raw_flags && b->mean[0]>0 && b->mean[3]>0 && green>0) {
            double r=green/b->mean[0]*4096.,blue=green/b->mean[3]*4096.;
            if(isfinite(r)&&isfinite(blue)&&r>=1&&r<65536&&blue>=1&&blue<65536) {
                b->red_gain_q12=(uint32_t)r;b->blue_gain_q12=(uint32_t)blue;
            } else b->raw_flags|=4u;
        } else if (!b->raw_flags)b->raw_flags|=1u;
        if(b->raw_flags&4u)++result->invalid_ratio_blocks;
    }
    *out=*result;free(result);
    return HB_S5_OK;
}
