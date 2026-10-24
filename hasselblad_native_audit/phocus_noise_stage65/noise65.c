/* Scene-neutral independent reconstruction of bounded ColorNoise operations.
 * NOT a complete original demosaic or proof of Android pixel parity.
 * Stage64 YCC helper is intentionally kept as a separate named dependency.
 */
#include "noise65.h"
#include "../phocus_colour_stage64/ycc64.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>

static int16_t from16(uint16_t bits) {
    int16_t out;
    memcpy(&out, &bits, sizeof out);
    return out;
}
static int16_t median3(int16_t a, int16_t b, int16_t c) {
    const int16_t low = a < b ? a : b, high = a > b ? a : b;
    return c < low ? low : c > high ? high : c;
}
static int valid(const HBNoiseContext65 *ctx) {
    if (!ctx || ctx->width < 1 || ctx->height < 1 || ctx->stride < ctx->width ||
        (uint64_t)ctx->height * (uint64_t)ctx->stride > SIZE_MAX/sizeof(uint16_t)) return 0;
    if ((ctx->flags & 0x20u) && (!ctx->red || !ctx->green || !ctx->blue ||
            !ctx->y || !ctx->c1 || !ctx->c2)) return 0;
    if ((ctx->flags & 0x40u) && !ctx->optimized_view &&
        (!ctx->y || !ctx->c1 || !ctx->c2 || !ctx->smooth_y ||
         !ctx->median_c1 || !ctx->median_c2 || !ctx->direction_mask ||
         !ctx->out_y || !ctx->out_c1 || !ctx->out_c2 || !ctx->out_aux)) return 0;
    return 1;
}
static void zero_counts(HBNoiseCounters65 *counts) {
    if (counts) memset(counts, 0, sizeof *counts);
}

int hb_color_noise_prepare65(const HBNoiseContext65 *c, HBNoiseCounters65 *counts) {
    if (!valid(c)) return -1;
    if (!(c->flags & 0x20u) || c->height < 17 || c->width < 17) return 0;
    const size_t s=(size_t)c->stride;
    for (int yy=8; yy<c->height-8; ++yy) {
        for (int xx=8; xx<c->width-8; ++xx) {
            const size_t p=(size_t)yy*s+(size_t)xx;
            const int32_t r=c->red[p], g=c->green[p], b=c->blue[p];
            const int32_t sum=r+2*g+b;
            const int32_t divisor=sum+1;
            const int32_t c1=((r-g)*INT32_C(32768))/divisor;
            const int32_t c2=((b-g)*INT32_C(32768))/divisor;
            c->y[p]=(uint16_t)((uint32_t)sum >> 2);
            c->c1[p]=from16((uint16_t)(uint32_t)c1);
            c->c2[p]=from16((uint16_t)(uint32_t)c2);
            if (counts) ++counts->converted_sites;
        }
    }
    /* Original mutates its Y plane in scan order; do NOT precompute a parallel
     * min/max image or use a non-overlapping temporary, as that changes the
     * already-updated neighbour reads at subsequent sites. */
    for (int yy=8; yy<c->height-8; ++yy) {
        for (int xx=8; xx<c->width-8; ++xx) {
            const size_t p=(size_t)yy*s+(size_t)xx;
            unsigned minval=65535u,maxval=0u;
            for (int dy=-1; dy<=1; ++dy) for (int dx=-1; dx<=1; ++dx) {
                if (!dx && !dy) continue;
                const uint16_t neighbour=c->y[(size_t)((int64_t)p+(int64_t)dy*c->stride+dx)];
                if (neighbour<minval) minval=neighbour;
                if (neighbour>maxval) maxval=neighbour;
            }
            if(c->y[p]<minval) c->y[p]=(uint16_t)minval;
            else if(c->y[p]>maxval) c->y[p]=(uint16_t)maxval;
            if(counts)++counts->clamped_sites;
        }
    }
    return 0;
}

int hb_color_noise_rows65(const HBNoiseContext65 *c, HBNoiseCounters65 *counts) {
    if (!valid(c)) return -1;
    if (!(c->flags & 0x40u) || c->optimized_view || c->height < 3) return 0;
    const size_t s=(size_t)c->stride;
    for (int yy=1;yy<c->height-1;++yy) {
        const size_t base=(size_t)yy*s;
        /* Stage61 row helpers perform the same three operations; implement
         * a self-contained equivalent here and compare independently. */
        c->smooth_y[base]=0;
        c->smooth_y[base+(size_t)c->width-1]=0;
        c->median_c1[base]=c->c1[base];
        c->median_c2[base]=c->c2[base];
        c->median_c1[base+(size_t)c->width-1]=c->c1[base+(size_t)c->width-1];
        c->median_c2[base+(size_t)c->width-1]=c->c2[base+(size_t)c->width-1];
        for(int xx=1;xx<c->width-1;++xx) {
            const size_t p=base+(size_t)xx;
            const uint32_t corners=(uint32_t)c->y[p-s-1]+c->y[p-s+1]+c->y[p+s-1]+c->y[p+s+1];
            const uint32_t cross=(uint32_t)c->y[p-s]+c->y[p+s]+c->y[p-1]+c->y[p+1];
            c->smooth_y[p]=(uint16_t)((corners+2*cross+4*c->y[p])/16u);
            const int16_t *planes[2]={c->c1,c->c2};
            int16_t *outputs[2]={c->median_c1,c->median_c2};
            for(int i=0;i<2;++i) {
                const int16_t *v=planes[i];
                outputs[i][p]=median3(median3(v[p-s-1],v[p-s],v[p-s+1]),
                                       median3(v[p-1],v[p],v[p+1]),
                                       median3(v[p+s-1],v[p+s],v[p+s+1]));
            }
        }
        if(counts){++counts->smoothing_rows;counts->median_rows+=2;}
    }
    return 0;
}

int hb_color_noise_correct65(const HBNoiseContext65 *c, HBNoiseCounters65 *counts) {
    if (!valid(c)) return -1;
    if (!(c->flags & 0x40u) || c->optimized_view || c->height<25 || c->width<25) return 0;
    const size_t s=(size_t)c->stride;
    for(int yy=12;yy<c->height-12;++yy)for(int xx=12;xx<c->width-12;++xx) {
        const size_t p=(size_t)yy*s+(size_t)xx;
        int16_t new_c1=c->c1[p], new_c2=c->c2[p];
        if(c->direction_mask[p]!=0) {
            /* OutC2 is the additional plane at native object offset 0x80.
             * The final local result is the helper's fourth scalar output. */
            if(hb_directional_ycc64(c->direction_mask[p],c->y+p,c->c1+p,c->c2+p,
                        c->smooth_y+p,c->median_c1+p,c->median_c2+p,
                        c->out_y+p,&new_c1,c->out_aux+p,&new_c2,c->stride)!=0)
                return -1;
            if(counts)++counts->nonzero_mask_sites;
        } else {
            c->out_y[p]=c->y[p];
            c->out_aux[p]=0;
        }
        const int32_t m1=c->median_c1[p],m2=c->median_c2[p];
        const int32_t a=(int32_t)new_c1,b=(int32_t)new_c2;
        const uint16_t med_bits=(uint16_t)(uint32_t)((m1<0?-m1:m1)+(m2<0?-m2:m2));
        const uint16_t cand_bits=(uint16_t)(uint32_t)((a<0?-a:a)+(b<0?-b:b));
        if(from16(cand_bits)>from16(med_bits)) {
            new_c1=(int16_t)m1;
            new_c2=(int16_t)m2;
            if(counts)++counts->median_selected_sites;
        }
        c->out_c1[p]=new_c1;
        c->out_c2[p]=new_c2;
        if(counts)++counts->correction_sites;
    }
    return 0;
}

int hb_color_noise65(HBNoiseContext65 *c, HBNoiseCounters65 *counts) {
    if (!valid(c)) return -1;
    /* Original positive-strength branch depends on unported functions. Never
     * silently claim native parity by falling back to a disabled route. */
    if((c->flags & 0x40u) && !c->optimized_view && c->strength>0) return -2;
    zero_counts(counts);
    int status=hb_color_noise_prepare65(c,counts);
    if(status!=0)return status;
    status=hb_color_noise_rows65(c,counts);
    if(status!=0)return status;
    return hb_color_noise_correct65(c,counts);
}
