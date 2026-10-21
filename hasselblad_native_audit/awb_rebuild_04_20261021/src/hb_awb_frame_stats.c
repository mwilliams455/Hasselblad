/* SPDX-License-Identifier: MIT */
#include "hb_awb_frame_stats.h"
#include <limits.h>
#include <string.h>

static const uint8_t bayer_sites[4][4]={
    {HB_AWB_RED, HB_AWB_GREEN_RED_ROW, HB_AWB_GREEN_BLUE_ROW, HB_AWB_BLUE},
    {HB_AWB_GREEN_RED_ROW, HB_AWB_RED, HB_AWB_BLUE, HB_AWB_GREEN_BLUE_ROW},
    {HB_AWB_GREEN_BLUE_ROW, HB_AWB_BLUE, HB_AWB_RED, HB_AWB_GREEN_RED_ROW},
    {HB_AWB_BLUE, HB_AWB_GREEN_BLUE_ROW, HB_AWB_GREEN_RED_ROW, HB_AWB_RED}
};

static int valid_frame(const hb_awb_frame_input *f, size_t bytes) {
    if (!f || f->cfa<HB_AWB_RGGB || f->cfa>HB_AWB_BGGR ||
        f->width<64 || f->height<64 || f->width>65536 || f->height>65536 ||
        (uint64_t)f->width*f->height>HB_AWB_MAX_FRAME_PIXELS ||
        f->pixel_stride_bytes>65536 || f->row_stride_bytes>16777216 ||
        (f->width&1u) || (f->height&1u) ||
        f->pixel_stride_bytes<2u || f->row_stride_bytes<2u || !f->white_code ||
        f->left>=f->right || f->top>=f->bottom ||
        f->right>f->width || f->bottom>f->height ||
        ((f->left|f->right|f->top|f->bottom)&1u) ||
        f->right-f->left<64 || f->bottom-f->top<64 ||
        (uint64_t)(f->right-f->left)*(f->bottom-f->top)>HB_AWB_MAX_FRAME_PIXELS)
        return 0;
    for (unsigned i=0;i<4;++i)
        if (f->black_q16[i] < 0 || f->black_q16[i] > INT64_C(65535)*HB_AWB_Q16_ONE)
            return 0;
    /* Rows and pixels may be padded. Check last actually read sample, not a
     * guessed contiguous layout. All multiplication/addition is 64-bit. */
    if ((uint64_t)(f->width-1)*f->pixel_stride_bytes+2 > f->row_stride_bytes)
        return 0;
    uint64_t last=(uint64_t)(f->bottom-1)*f->row_stride_bytes +
                  (uint64_t)(f->right-1)*f->pixel_stride_bytes+2;
    if (last>SIZE_MAX || last>bytes) return 0;
    return 1;
}

int hb_awb_raw_to_block_stats(const uint8_t *raw, size_t raw_bytes,
                             const hb_awb_frame_input *f,
                             hb_awb_frame_stats *out) {
    if (!raw || !out || !valid_frame(f,raw_bytes)) return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_frame_stats accum;
    memset(&accum,0,sizeof accum);
    for (unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i)
        accum.blocks[i].min_sample=UINT16_MAX;
    const uint32_t halfwidth=(f->right-f->left)/2;
    const uint32_t halfheight=(f->bottom-f->top)/2;
    for (uint32_t qy=0;qy<halfheight;++qy) {
        const uint32_t y=f->top+2*qy;
        const uint32_t block_y=(uint32_t)((uint64_t)qy*32/halfheight);
        for (uint32_t qx=0;qx<halfwidth;++qx) {
            const uint32_t x=f->left+2*qx;
            const uint32_t block_x=(uint32_t)((uint64_t)qx*32/halfwidth);
            hb_awb_stat_block *b=&accum.blocks[block_y*32+block_x];
            for (uint32_t ry=0;ry<2;++ry) {
                for (uint32_t rx=0;rx<2;++rx) {
                    const uint32_t site=((y+ry)&1u)*2u+((x+rx)&1u);
                    const uint8_t *s=raw+(size_t)(y+ry)*f->row_stride_bytes+
                                        (size_t)(x+rx)*f->pixel_stride_bytes;
                    uint16_t code=(uint16_t)s[0] | ((uint16_t)s[1]<<8);
                    int64_t signed_q16=(int64_t)code*HB_AWB_Q16_ONE-f->black_q16[site];
                    uint8_t colour=bayer_sites[f->cfa][site];
                    b->site_sum_q16[colour]+=signed_q16;
                    ++b->site_count[colour];
                    b->raw_brightness_sum_q16+=signed_q16;
                    ++b->sample_count;
                    b->at_or_above_white_count+=(code>=f->white_code);
                    b->above_white_count+=(code>f->white_code);
                    b->at_or_below_black_count+=((int64_t)code*HB_AWB_Q16_ONE<=f->black_q16[site]);
                    if(code<b->min_sample) b->min_sample=code;
                    if(code>b->max_sample) b->max_sample=code;
                }
            }
        }
    }
    accum.input_sample_count=(uint64_t)(f->right-f->left)*(f->bottom-f->top);
    /* Nothing in this input bridge establishes matching vendor E2 semantics. */
    accum.vendor_e2_equivalence_proven=0;
    *out=accum;
    return HB_AWB_REBUILD_OK;
}

/* Arithmetic guard for externally supplied block statistics. */
static int add_scaled_i64(int64_t *dst, int64_t val, uint64_t w) {
    if(w==0) return 1;
    if(val>0 && val>INT64_MAX/(int64_t)w) return 0;
    if(val<0 && val<INT64_MIN/(int64_t)w) return 0;
    const int64_t delta=val*(int64_t)w;
    if(delta>0 && *dst>INT64_MAX-delta) return 0;
    if(delta<0 && *dst<INT64_MIN-delta) return 0;
    *dst+=delta;
    return 1;
}

int hb_awb_accumulate_owned_candidates(const hb_awb_frame_stats *frame,
        const uint8_t weights[HB_AWB_FRAME_BLOCKS],
        const uint8_t *accepted_by_classifier,
        enum hb_awb_connectivity neighbours, hb_awb_scene_accumulation *out) {
    if (!frame || !weights || !out ||
        (neighbours!=HB_AWB_NEIGHBORS_FOUR && neighbours!=HB_AWB_NEIGHBORS_EIGHT))
        return HB_AWB_REBUILD_BAD_INPUT;
    uint8_t selected[HB_AWB_FRAME_BLOCKS];
    uint8_t filtered[HB_AWB_FRAME_BLOCKS];
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i) {
        if(weights[i]>HB_AWB_MAX_SYNTHETIC_WEIGHT) return HB_AWB_REBUILD_BAD_INPUT;
        selected[i]=(weights[i]>0);
    }
    hb_awb_scene_accumulation acc={0};
    if(hb_awb_prune_small_components(selected,filtered,neighbours,&acc.filter)!=0)
        return HB_AWB_REBUILD_BAD_INPUT;
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i) {
        if(!filtered[i]) continue;
        const hb_awb_stat_block *b=&frame->blocks[i];
        const uint64_t w=weights[i];
        for(unsigned c=0;c<4;++c) {
            if(!add_scaled_i64(&acc.weighted_site_sum_q16[c], b->site_sum_q16[c],w))
                return HB_AWB_REBUILD_BAD_INPUT;
            acc.weighted_site_count[c]+=(uint64_t)b->site_count[c]*w;
        }
        if(!add_scaled_i64(&acc.weighted_raw_brightness_q16,b->raw_brightness_sum_q16,w))
            return HB_AWB_REBUILD_BAD_INPUT;
        acc.weighted_sample_count+=(uint64_t)b->sample_count*w;
        acc.weighted_at_or_above_white_count+=(uint64_t)b->at_or_above_white_count*w;
        ++acc.surviving_blocks;
        if(accepted_by_classifier && accepted_by_classifier[i]==0)
            ++acc.weighted_but_unclassified_blocks;
    }
    acc.vendor_candidate_equivalence_proven=0;
    *out=acc;
    return HB_AWB_REBUILD_OK;
}