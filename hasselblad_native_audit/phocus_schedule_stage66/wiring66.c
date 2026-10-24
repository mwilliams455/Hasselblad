#include "wiring66.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static int separated(const uint16_t *a, const uint16_t *b,size_t bytes) {
    const uintptr_t ua=(uintptr_t)a, ub=(uintptr_t)b;
    /* ptr arithmetic is performed on integers to guard overflow. */
    if(ua>UINTPTR_MAX-bytes || ub>UINTPTR_MAX-bytes)return 0;
    return ua+bytes<=ub || ub+bytes<=ua;
}
typedef struct {
    const HB66Planes *p;
    const HB66Callbacks *cb;
    HB66WiringCounts *count;
    size_t bytes;
} Context66;
static int emit(void *user,HB66Event ev,int x,int y) {
    Context66 *ctx=user;
    const HB66Planes *p=ctx->p;
    HB66WiringCounts *c=ctx->count;
    const size_t ix=(size_t)y*(size_t)p->domain.stride+(size_t)x;
    uint16_t g=0,mask=0,r=0,b=0;
    int32_t value;
    switch(ev){
    case HB66_SMOOTH_ROW:case HB66_EDGE_ROW:case HB66_SCALE_MAP:case HB66_MID_GREEN_MAP:
        return ctx->cb->prepare(ctx->cb->user,ev,y);
    case HB66_COPY_RAW_TO_GREEN:
        memcpy(p->green,p->raw,ctx->bytes);
        return 0;
    case HB66_GREEN_AT_RED:
        if(ctx->cb->estimate_green(ctx->cb->user,x,y,&g,&mask)!=0)return 1;
        p->red[ix]=p->raw[ix];p->green[ix]=g;p->blue[ix]=0;p->mask[ix]=mask;
        ++c->green_red_calls;
        return 0;
    case HB66_GREEN_AT_BLUE:
        if(ctx->cb->estimate_green(ctx->cb->user,x,y,&g,&mask)!=0)return 1;
        p->red[ix]=0;p->green[ix]=g;p->blue[ix]=p->raw[ix];p->mask[ix]=mask;
        ++c->green_blue_calls;
        return 0;
    case HB66_GREEN_SITE_TOP:case HB66_GREEN_SITE_LEFT:
        p->red[ix]=0;p->green[ix]=p->raw[ix];p->blue[ix]=0;
        return 0;
    case HB66_BLUE_AT_RED:case HB66_RED_AT_BLUE:
        mask=p->mask[ix];
        if(mask){
            value=ctx->cb->estimate_opposite_colour(ctx->cb->user,x,y,
                ev==HB66_BLUE_AT_RED,mask);
            ++c->opposite_colour_calls;
        }else{value=0;++c->opposite_zero_fallbacks;}
        if(ev==HB66_BLUE_AT_RED)p->blue[ix]=(uint16_t)(uint32_t)value;
        else p->red[ix]=(uint16_t)(uint32_t)value;
        return 0;
    case HB66_MASK_GREEN_RED_ROW:case HB66_MASK_GREEN_BLUE_ROW:
        if(ctx->cb->compute_green_site_mask(ctx->cb->user,x,y,&mask)!=0)return 1;
        p->mask[ix]=mask;++c->green_site_mask_calls;
        return 0;
    case HB66_RB_GREEN_RED_ROW:case HB66_RB_GREEN_BLUE_ROW:
        mask=p->mask[ix];
        if(mask){
            if(ctx->cb->estimate_red_blue_green_site(ctx->cb->user,x,y,mask,&r,&b)!=0)
                return 1;
            ++c->green_site_rb_calls;
        }else{r=0;b=0;++c->green_site_zero_fallbacks;}
        p->red[ix]=r;p->blue[ix]=b;
        return 0;
    default:return 1;
    }
}
int hb_wire_interpolate66(const HB66Planes *p,const HB66Callbacks *cb,
                          HB66WiringCounts *out) {
    if(!p||!cb||!out ||!cb->prepare||!cb->estimate_green||
       !cb->estimate_opposite_colour||!cb->compute_green_site_mask||
       !cb->estimate_red_blue_green_site||!p->raw||!p->red||!p->green||
       !p->blue||!p->mask) return -1;
    memset(out,0,sizeof *out);
    HB66Counts expected;
    const int status=hb_schedule66(p->domain,NULL,NULL,&expected);
    if(status!=0)return status;
    const size_t bytes=(size_t)expected.copy_raw_codes*sizeof(uint16_t);
    const uint16_t *arrays[5]={p->raw,p->red,p->green,p->blue,p->mask};
    for(int i=0;i<5;++i) for(int j=i+1;j<5;++j)
        if(!separated(arrays[i],arrays[j],bytes))return -1;
    Context66 ctx={p,cb,out,bytes};
    int result=hb_schedule66(p->domain,emit,&ctx,&out->events);
    if(result==0 && out->events.total_events!=expected.total_events)return -1;
    return result;
}
