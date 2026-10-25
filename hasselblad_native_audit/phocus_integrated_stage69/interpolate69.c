#include "interpolate69.h"
#include "../phocus_gradient_stage61/gradient_maps61.h"
#include "../phocus_interpolation_stage62/interpolation62.h"
#include "../phocus_green_stage63/green63.h"
#include "../phocus_inline_stage67/green_site_mask67.h"
#include "../phocus_coloursite_stage68/colour_site68.h"
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct {
    const HB66Planes *planes;
    const HB69Scratch *scratch;
    HB69Parameters parameters;
    HB69Results *results;
} HB69Context;
static size_t at(const HB66Planes *p,int x,int y) {
    return (size_t)y*(size_t)p->domain.stride+(size_t)x;
}
static int disjoint(const void *a,size_t a_bytes,const void *b,size_t b_bytes) {
    const uintptr_t ua=(uintptr_t)a,ub=(uintptr_t)b;
    if (ua>UINTPTR_MAX-a_bytes || ub>UINTPTR_MAX-b_bytes)return 0;
    return ua+a_bytes<=ub || ub+b_bytes<=ua;
}
static int prepare(void *ctx,HB66Event event,int y) {
    HB69Context *c=(HB69Context*)ctx;
    const HB66Planes *p=c->planes;
    const HB69Scratch *s=c->scratch;
    int w=p->domain.width,h=p->domain.height,d=p->domain.stride;
    const uint16_t *r=p->raw;
    int ret=-1;
    switch(event) {
    case HB66_SMOOTH_ROW:
        ret=hb_gradient_smooth_row61(r+(size_t)y*d,s->smoothed_raw+(size_t)y*d,d,w);
        break;
    case HB66_EDGE_ROW:
        ret=hb_gradient_edge_row61(s->smoothed_raw+(size_t)y*d,
                                   s->signed_edge+(size_t)y*d,d,w);
        break;
    case HB66_SCALE_MAP:
        ret=hb_gradient_scale61(r,w,h,d,2,2,w-2,h-2,
                                c->parameters.scale_threshold,
                                s->horizontal_scale,s->vertical_scale);
        break;
    case HB66_MID_GREEN_MAP:
        ret=hb_gradient_green61(r,w,h,d,2,2,w-2,h-2,
                                s->horizontal_scale,s->vertical_scale,
                                s->midgreen_scale,s->midgreen_codes);
        break;
    default:return 1;
    }
    if(ret==0) ++c->results->successful_preparations;
    return ret;
}
static int estimate_green(void *ctx,int x,int y,uint16_t *green,uint16_t *mask) {
    HB69Context *c=(HB69Context*)ctx;
    const HB66Planes *p=c->planes;
    const HB69Scratch *s=c->scratch;
    const size_t i=at(p,x,y);
    int32_t g=0,m=0;
    int16_t maximum=0;
    int ret=hb_colour_site_green68(p->raw+i,s->signed_edge+i,
                                  s->horizontal_scale+i,s->vertical_scale+i,
                                  s->midgreen_scale+i,p->domain.stride,
                                  c->parameters.edge_floor,c->parameters.raw_floor,
                                  &g,&m,&maximum);
    if(ret)return 1;
    *green=(uint16_t)(uint32_t)g;
    *mask=(uint16_t)(uint32_t)m;
    ++c->results->real_colour_site_estimates;
    c->results->colour_sites_with_no_direction+=(m==0);
    return 0;
}
static int32_t estimate_opposite(void *ctx,int x,int y,int red_site,uint16_t mask) {
    HB69Context *c=(HB69Context*)ctx;
    const HB66Planes *p=c->planes;
    const size_t i=at(p,x,y);
    ++c->results->real_opposite_colour_calls;
    return hb_blue_at_red62((red_site?p->blue:p->red)+i,p->green+i,
                             (uint32_t)mask,p->domain.stride);
}
static int compute_green_mask(void *ctx,int x,int y,uint16_t *mask) {
    HB69Context *c=(HB69Context*)ctx;
    const HB66Planes *p=c->planes;
    const size_t i=at(p,x,y);
    int16_t edge[8],raw[8];
    uint16_t packed=0;
    if(hb_green_site_mask67(p->raw+i,c->scratch->signed_edge+i,
                            p->domain.stride,c->parameters.edge_floor,
                            c->parameters.raw_floor,edge,raw,&packed))return 1;
    *mask=packed;
    ++c->results->real_green_site_masks;
    return 0;
}
static int estimate_rb_green(void *ctx,int x,int y,uint16_t mask,
                             uint16_t *red,uint16_t *blue) {
    HB69Context *c=(HB69Context*)ctx;
    const HB66Planes *p=c->planes;
    size_t i=at(p,x,y);
    /* The Stage62 implementation reads all samples before writing either
     * output. The Stage66 wiring then writes the scalar results into planes. */
    hb_red_blue_at_green62(p->red+i,p->green+i,p->blue+i,red,blue,
                            (uint32_t)mask,p->domain.stride);
    ++c->results->real_red_blue_green_calls;
    return 0;
}
int hb_interpolate69(const HB66Planes *p,const HB69Scratch *s,
                     HB69Parameters params,HB69Results *results) {
    if(!p || !s || !results)return -1;
    memset(results,0,sizeof *results);
    if(!isfinite(params.scale_threshold) || params.scale_threshold<1.0 ||
       params.scale_threshold>100.0)return -1;
    HB66Counts contract;
    const int status=hb_schedule66(p->domain,NULL,NULL,&contract);
    if(status)return status;
    const size_t n=(size_t)contract.copy_raw_codes;
    if(n>SIZE_MAX/sizeof(float))return -1;
    const size_t uintbytes=n*sizeof(uint16_t),floatbytes=n*sizeof(float);
    const void *arrays[11]={p->raw,p->red,p->green,p->blue,p->mask,
        s->smoothed_raw,s->signed_edge,s->horizontal_scale,s->vertical_scale,
        s->midgreen_scale,s->midgreen_codes};
    const size_t lengths[11]={uintbytes,uintbytes,uintbytes,uintbytes,uintbytes,
        uintbytes,uintbytes,floatbytes,floatbytes,floatbytes,uintbytes};
    for(int i=0;i<11;++i){
        if(!arrays[i])return -1;
        for(int j=i+1;j<11;++j)
            if(arrays[j]&&!disjoint(arrays[i],lengths[i],arrays[j],lengths[j]))return -1;
    }
    HB69Context context={p,s,params,results};
    const HB66Callbacks callbacks={&context,prepare,estimate_green,
                                    estimate_opposite,compute_green_mask,
                                    estimate_rb_green};
    return hb_wire_interpolate66(p,&callbacks,&results->wiring);
}
