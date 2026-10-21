/* SPDX-License-Identifier: MIT */
#include "hb_phone_raw.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

static const unsigned colour_at_site[4][4]={
    {0,1,2,3},{1,0,3,2},{2,3,0,1},{3,2,1,0}
};

int hb_phone_raw_build(const uint8_t *raw, size_t raw_bytes,
    const hb_awb_frame_input *f, enum hb_phone_history history,
    hb_phone_raw_grid *out) {
    if (!raw || !f || !out) return HB_PHONE_BAD_INPUT;
    if (history!=HB_PHONE_UNTOUCHED_RAW16_LE) return HB_PHONE_PROCESSED_INPUT;
    if ((unsigned)f->cfa>HB_AWB_BGGR || !f->white_code) return HB_PHONE_BAD_INPUT;
    double span[4];
    for (unsigned site=0;site<4;++site) {
        if (f->black_q16[site]<0 ||
            f->black_q16[site]>=(int64_t)f->white_code*HB_AWB_Q16_ONE)
            return HB_PHONE_BAD_INPUT;
        span[colour_at_site[f->cfa][site]]=
            (double)((int64_t)f->white_code*HB_AWB_Q16_ONE-f->black_q16[site]);
    }
    hb_phone_raw_grid *g=calloc(1,sizeof *g);
    if (!g) return HB_PHONE_NO_MEMORY;
    if (hb_awb_raw_to_block_stats(raw,raw_bytes,f,&g->raw)!=HB_AWB_REBUILD_OK) {
        free(g);return HB_PHONE_BAD_INPUT;
    }
    for (unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i) {
        const hb_awb_stat_block *s=&g->raw.blocks[i];
        hb_phone_block *b=&g->blocks[i];
        for (unsigned c=0;c<4;++c) {
            b->mean[c]=(double)s->site_sum_q16[c]/((double)s->site_count[c]*span[c]);
            if (!(b->mean[c]>0)) b->flags|=HB_PHONE_NONPOSITIVE;
        }
        b->mean_brightness=((b->mean[0]+b->mean[1])+b->mean[2]+b->mean[3])*0.25;
        if (s->at_or_above_white_count) b->flags|=HB_PHONE_SATURATED;
        if (!(b->flags&HB_PHONE_NONPOSITIVE)) {
            double green=(b->mean[1]+b->mean[2])*0.5;
            double r=green/b->mean[0]*4096.0,blue=green/b->mean[3]*4096.0;
            if (!isfinite(r) || !isfinite(blue) || r<1 || blue<1 ||
                r>=65536 || blue>=65536) b->flags|=HB_PHONE_RATIO_RANGE;
            else if (!b->flags) {
                b->red_gain_q12=(uint32_t)r;b->blue_gain_q12=(uint32_t)blue;
            }
        }
        g->ratio_blocks+=b->flags==0;
        g->nonpositive_blocks+=(b->flags&HB_PHONE_NONPOSITIVE)!=0;
        g->saturated_blocks+=(b->flags&HB_PHONE_SATURATED)!=0;
        g->range_blocks+=(b->flags&HB_PHONE_RATIO_RANGE)!=0;
    }
    memcpy(out,g,sizeof *g);free(g);return HB_PHONE_OK;
}
