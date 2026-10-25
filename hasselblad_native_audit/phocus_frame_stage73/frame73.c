#include "frame73.h"
#include "../phocus_integrated_stage69/interpolate69.h"
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Explicitly bounded original-CPU fixtures, not a general scheduler. */
static int scope(int w,int h){
    if ((w==64&&h==64)||(w==32&&h==32)||(w==24&&h==16)||
        (w==34&&h==18))return 1; /* Stage72 final RGB16 checked. */
    if (w==12&&h==15)return 1; /* Stage73 final RGB16 checked. */
    if ((w==9&&h==11)||(w==18&&h==34)||(w==23&&h==31)||
        (w==33&&h==35))return 2; /* Only original outer geometry checked. */
    return 0;
}
int hb73_plan(int output_width,int output_height,HB73Plan *plan){
    if(!plan)return HB73_BAD_ARGUMENT;
    memset(plan,0,sizeof *plan);
    if(output_width<=0||output_height<=0)return HB73_BAD_ARGUMENT;
    int s=scope(output_width,output_height);
    if(!s)return HB73_UNSUPPORTED;
    int w=output_width+64,h=output_height+64;
    plan->output_width=output_width;plan->output_height=output_height;
    plan->source_width=w;plan->source_height=h;
    plan->work_width=(w+7)&~7;
    plan->work_height=(h+7)&~7;
    plan->work_stride=1024;plan->crop_x=32;plan->crop_y=32;
    plan->evidence_scope=s;
    return HB73_OK;
}
static int disjoint(const void *a,size_t n,const void *b,size_t m){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=UINTPTR_MAX-n&&y<=UINTPTR_MAX-m&&(x+n<=y||y+m<=x);
}
static void free_all(void *items[11]){
    for(int i=0;i<11;++i)free(items[i]);
}
int hb73_render_pre_noise(const HB73Plan *p,const HB73Settings *s,
        const uint16_t *input,size_t input_count,int input_stride,
        uint16_t *output,size_t output_count,HB73Receipt *receipt){
    if(receipt)memset(receipt,0,sizeof *receipt);
    if(!p||!s||!input||!output)return HB73_BAD_ARGUMENT;
    HB73Plan original;
    int status=hb73_plan(p->output_width,p->output_height,&original);
    if(status)return status;
    if(original.output_width!=p->output_width||original.output_height!=p->output_height||
       original.source_width!=p->source_width||original.source_height!=p->source_height||
       original.work_width!=p->work_width||original.work_height!=p->work_height||
       original.work_stride!=p->work_stride||original.crop_x!=p->crop_x||
       original.crop_y!=p->crop_y||original.evidence_scope!=p->evidence_scope)
        return HB73_UNSUPPORTED;
    if(s->cfa!=HB73_RGGB||s->flags!=0xffffu||
       s->scale_threshold!=1.0||s->edge_gradient_floor!=32||
       s->raw_gradient_floor!=200)return HB73_UNSUPPORTED;
    if(input_stride<p->source_width||input_stride>4096)return HB73_BAD_ARGUMENT;
    size_t in_sites=(size_t)input_stride*(size_t)p->source_height;
    size_t out_sites=(size_t)p->output_width*(size_t)p->output_height*4;
    if(input_count<in_sites||output_count<out_sites)return HB73_BAD_ARGUMENT;
    if(!disjoint(input,in_sites*sizeof(uint16_t),output,out_sites*sizeof(uint16_t)))
        return HB73_BAD_ARGUMENT;
    size_t sites=(size_t)p->work_height*(size_t)p->work_stride;
    if(sites>SIZE_MAX/sizeof(float))return HB73_BAD_ARGUMENT;
    const size_t ushort_bytes=sites*sizeof(uint16_t),float_bytes=sites*sizeof(float);
    /* RAW, R, G, B, mask, smooth, edge, hscale, vscale, midscale, midcodes */
    void *items[11]={0};
    for(int i=0;i<11;++i){
        const size_t bytes=(i>=7&&i<=9)?float_bytes:ushort_bytes;
        items[i]=calloc(1,bytes);
        if(!items[i]){free_all(items);return HB73_ALLOCATION_FAILED;}
    }
    uint16_t *raw=items[0];
    for(int row=0;row<p->work_height;++row)
        for(int col=0;col<p->work_width;++col)
            raw[(size_t)row*p->work_stride+col]=s->alignment_tail_fill;
    for(int row=0;row<p->source_height;++row)
        memcpy(raw+(size_t)row*p->work_stride,
               input+(size_t)row*input_stride,(size_t)p->source_width*sizeof(uint16_t));
    HB66Planes planes={
        {p->work_width,p->work_height,p->work_stride,(uint16_t)s->flags},
        raw,items[1],items[2],items[3],items[4]
    };
    HB69Scratch scratch={items[5],items[6],items[7],items[8],items[9],items[10]};
    HB69Results results;
    status=hb_interpolate69(&planes,&scratch,
        (HB69Parameters){s->scale_threshold,
                         (int16_t)s->edge_gradient_floor,(int16_t)s->raw_gradient_floor},
        &results);
    if(status){free_all(items);return HB73_INTERPOLATION_FAILED;}
    uint16_t *r=items[1],*g=items[2],*b=items[3],*mask=items[4];
    size_t write=0;
    for(int y=0;y<p->output_height;++y){
        for(int x=0;x<p->output_width;++x){
            size_t idx=(size_t)(y+p->crop_y)*p->work_stride+(x+p->crop_x);
            output[write++]=r[idx];output[write++]=g[idx];
            output[write++]=b[idx];output[write++]=mask[idx];
        }
    }
    if(receipt){
        receipt->interpolator_events=results.wiring.events.total_events;
        receipt->red_blue_green_calls=results.real_red_blue_green_calls;
        receipt->colour_site_estimates=results.real_colour_site_estimates;
        receipt->allocated_bytes=8*ushort_bytes+3*float_bytes;
    }
    free_all(items);
    return HB73_OK;
}
