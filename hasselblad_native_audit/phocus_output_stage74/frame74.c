#include "frame74.h"
#include "output74.h"
#include "../phocus_integrated_stage69/interpolate69.h"
#include "../phocus_noise_stage65/noise65.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

/* Allocation and cleanup are *ours*, not a reproduction of the original
 * C++ allocator. No private input/output is published by this API. */
enum {
    RAW=0,RED,GREEN,BLUE,MASK,SMOOTH,EDGE,HORIZONTAL,VERTICAL,SCALE,MIDGREEN,
    Y,C1,C2,SMOOTH_Y,MEDIAN_C1,MEDIAN_C2,OUT_Y,OUT_C1,OUT_C2,OUT_AUX,
    ITEM_COUNT
};
static void free_all(void *p[ITEM_COUNT]){
    for(int i=0;i<ITEM_COUNT;++i)free(p[i]);
}
static int disjoint(const void *a,size_t n,const void *b,size_t m){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=UINTPTR_MAX-n&&y<=UINTPTR_MAX-m&&(x+n<=y||y+m<=x);
}
int hb74_render_final_bounded(const HB73Plan *p,const HB73Settings *s,
       const uint16_t *input,size_t input_count,int input_stride,
       uint16_t *rgb,size_t rgb_count,HB74Receipt *receipt){
    if(receipt)memset(receipt,0,sizeof *receipt);
    if(!p||!s||!input||!rgb)return -1;
    HB73Plan ref;
    int status=hb73_plan(p->output_width,p->output_height,&ref);
    if(status)return status;
    if(memcmp(p,&ref,sizeof ref)!=0)return -2;
    if(s->cfa!=HB73_RGGB||s->flags!=0xffffu||s->scale_threshold!=1.0||
       s->edge_gradient_floor!=32||s->raw_gradient_floor!=200)return -2;
    if(input_stride<p->source_width||input_stride>4096)return -1;
    const size_t input_sites=(size_t)input_stride*p->source_height;
    const size_t output_sites=(size_t)p->output_width*p->output_height;
    if(input_sites>SIZE_MAX/2||output_sites>SIZE_MAX/6||
       input_count<input_sites||rgb_count<output_sites*3)return -1;
    if(!disjoint(input,input_sites*sizeof(uint16_t),rgb,output_sites*6))return -1;
    const size_t work_sites=(size_t)p->work_height*p->work_stride;
    if(work_sites>SIZE_MAX/sizeof(float))return -1;
    const size_t u16_bytes=work_sites*2,f32_bytes=work_sites*4;
    void *v[ITEM_COUNT]={0};
    size_t total_allocated=0;
    for(int i=0;i<ITEM_COUNT;++i){
        const size_t n=(i>=HORIZONTAL&&i<=SCALE)?f32_bytes:u16_bytes;
        v[i]=calloc(1,n);
        if(!v[i]){free_all(v);return -3;}
        total_allocated+=n;
    }
    uint16_t *raw=v[RAW];
    for(int row=0;row<p->work_height;++row){
        for(int col=0;col<p->work_width;++col)
            raw[(size_t)row*p->work_stride+col]=s->alignment_tail_fill;
    }
    for(int row=0;row<p->source_height;++row)
        memcpy(raw+(size_t)row*p->work_stride,
               input+(size_t)row*input_stride,
               (size_t)p->source_width*2);
    HB66Planes planes={{p->work_width,p->work_height,p->work_stride,
                        (uint16_t)s->flags},raw,v[RED],v[GREEN],v[BLUE],v[MASK]};
    HB69Scratch scratch={v[SMOOTH],v[EDGE],v[HORIZONTAL],v[VERTICAL],v[SCALE],v[MIDGREEN]};
    HB69Results interpolated;
    status=hb_interpolate69(&planes,&scratch,
        (HB69Parameters){s->scale_threshold,
                         (int16_t)s->edge_gradient_floor,
                         (int16_t)s->raw_gradient_floor},&interpolated);
    if(status){free_all(v);return -4;}
    HBNoiseContext65 noise={
        .width=p->work_width,.height=p->work_height,.stride=p->work_stride,
        .flags=(uint16_t)s->flags,.optimized_view=0,.strength=0,
        .red=v[RED],.green=v[GREEN],.blue=v[BLUE],
        .y=v[Y],.c1=v[C1],.c2=v[C2],.direction_mask=v[MASK],
        .smooth_y=v[SMOOTH_Y],.median_c1=v[MEDIAN_C1],.median_c2=v[MEDIAN_C2],
        .out_y=v[OUT_Y],.out_c1=v[OUT_C1],.out_c2=v[OUT_C2],.out_aux=v[OUT_AUX]
    };
    HBNoiseCounters65 counters;
    if(hb_color_noise65(&noise,&counters)!=0){free_all(v);return -5;}
    status=hb74_convert_roi(v[OUT_Y],v[OUT_C1],v[OUT_C2],
       p->work_width,p->work_height,p->work_stride,
       p->crop_x,p->crop_y,p->output_width,p->output_height,
       1.0,rgb,rgb_count);
    if(status){free_all(v);return -6;}
    if(receipt){
        receipt->interpolation_events=interpolated.wiring.events.total_events;
        receipt->colour_site_estimates=interpolated.real_colour_site_estimates;
        receipt->red_blue_green_calls=interpolated.real_red_blue_green_calls;
        receipt->colornoise_converted_sites=counters.converted_sites;
        receipt->colornoise_correction_sites=counters.correction_sites;
        receipt->colornoise_directional_sites=counters.nonzero_mask_sites;
        receipt->final_rgb16_pixels=output_sites;
        receipt->allocated_bytes=total_allocated;
    }
    free_all(v);
    return 0;
}
