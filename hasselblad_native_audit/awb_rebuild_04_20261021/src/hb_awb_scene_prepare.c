/* SPDX-License-Identifier: MIT */
#include "hb_awb_scene_prepare.h"
#include <limits.h>
#include <string.h>

/* All arithmetic is defined by C11 for signed positive/negative values;
 * unlike direct x*Q16 multiplication, the division-first decomposition
 * cannot invoke intermediate signed overflow. */
static int checked_add(int64_t a, int64_t b, int64_t *out) {
    if ((b>0 && a>INT64_MAX-b) || (b<0 && a<INT64_MIN-b)) return 0;
    *out=a+b;
    return 1;
}
static int checked_mul_positive(int64_t a, uint64_t p, int64_t *out) {
    if (!p) { *out=0;return 1; }
    if(p>(uint64_t)INT64_MAX) return 0;
    int64_t s=(int64_t)p;
    if((a>0 && a>INT64_MAX/s)||(a<0 && a<INT64_MIN/s)) return 0;
    *out=a*s;
    return 1;
}
static int scale_trunc0_q16(int64_t value, uint32_t gain, int64_t *out) {
    int64_t base=0;
    const int64_t q=value / HB_AWB_Q16_ONE;
    const int64_t r=value % HB_AWB_Q16_ONE;
    if (!checked_mul_positive(q,gain,&base))return 0;
    /* Abs(r)<65536 and gain<=524288 so multiplication fits int64. */
    const int64_t fraction=(r*(int64_t)gain)/HB_AWB_Q16_ONE;
    return checked_add(base,fraction,out);
}
static int valid_calibration(const hb_awb_explicit_calibration *c) {
    if(!c)return 0;
    for(unsigned j=0;j<4;++j) {
        if(c->channel_gain_q16[j]>HB_AWB_GAIN_Q16_MAX ||
           c->channel_bias_q16[j]<-HB_AWB_BIAS_Q16_MAX ||
           c->channel_bias_q16[j]>HB_AWB_BIAS_Q16_MAX) return 0;
    }
    if(c->spatial_gain_q16)
        for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i)
            if(c->spatial_gain_q16[i]>HB_AWB_GAIN_Q16_MAX) return 0;
    return 1;
}
int hb_awb_apply_explicit_calibration(const hb_awb_frame_stats *input,
        const hb_awb_explicit_calibration *calibration,
        hb_awb_frame_stats *output) {
    if(!input || !output || !valid_calibration(calibration))return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_frame_stats tmp=*input;
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i){
        uint32_t spatial=calibration->spatial_gain_q16?
                         calibration->spatial_gain_q16[i]:65536u;
        for(unsigned j=0;j<4;++j){
            int64_t a,b,bias,result;
            if(!scale_trunc0_q16(input->blocks[i].site_sum_q16[j],
                         calibration->channel_gain_q16[j],&a) ||
               !scale_trunc0_q16(a,spatial,&b) ||
               !checked_mul_positive(calibration->channel_bias_q16[j],
                                     input->blocks[i].site_count[j],&bias) ||
               !checked_add(b,bias,&result))
                return HB_AWB_REBUILD_BAD_INPUT;
            tmp.blocks[i].site_sum_q16[j]=result;
        }
    }
    tmp.vendor_e2_equivalence_proven=0;
    *output=tmp;
    return HB_AWB_REBUILD_OK;
}
int hb_awb_prepare_raw_ae_evidence(const hb_awb_frame_stats *input,
                                     hb_awb_ae_evidence *output) {
    if(!input || !output) return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_ae_evidence tmp={0};
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i){
        const hb_awb_stat_block *b=&input->blocks[i];
        if (!b->sample_count || b->at_or_above_white_count>b->sample_count ||
           b->at_or_below_black_count>b->sample_count)return HB_AWB_REBUILD_BAD_INPUT;
        uint64_t site_total=0;
        for(unsigned j=0;j<4;++j)site_total+=b->site_count[j];
        if(site_total!=b->sample_count)return HB_AWB_REBUILD_BAD_INPUT;
        if(tmp.total_samples>UINT64_MAX-b->sample_count ||
           tmp.total_at_or_above_white>UINT64_MAX-b->at_or_above_white_count ||
           tmp.total_at_or_below_black>UINT64_MAX-b->at_or_below_black_count ||
           !checked_add(tmp.total_raw_sum_q16,b->raw_brightness_sum_q16,
                        &tmp.total_raw_sum_q16))return HB_AWB_REBUILD_BAD_INPUT;
        tmp.total_samples+=b->sample_count;
        tmp.total_at_or_above_white+=b->at_or_above_white_count;
        tmp.total_at_or_below_black+=b->at_or_below_black_count;
        tmp.raw_block_mean_q16[i]=b->raw_brightness_sum_q16/(int64_t)b->sample_count;
        tmp.at_or_above_white_ppm[i]=(uint32_t)
             (((uint64_t)b->at_or_above_white_count*HB_AWB_EVIDENCE_PPM)/b->sample_count);
        tmp.at_or_below_black_ppm[i]=(uint32_t)
             (((uint64_t)b->at_or_below_black_count*HB_AWB_EVIDENCE_PPM)/b->sample_count);
    }
    if(tmp.total_samples!=input->input_sample_count || tmp.total_samples==0)
        return HB_AWB_REBUILD_BAD_INPUT;
    tmp.frame_raw_mean_q16=tmp.total_raw_sum_q16/(int64_t)tmp.total_samples;
    tmp.vendor_ae_equivalence_proven=0;
    *output=tmp;
    return HB_AWB_REBUILD_OK;
}
int hb_awb_scene_prepare_bounded(const hb_awb_frame_stats *original,
            const hb_awb_explicit_calibration *calibration,
            const hb_awb_replay_masks *recorded,
            hb_awb_scene_prepare_result *out){
    if(!original || !calibration || !recorded || !out ||
       (recorded->neighbours!=HB_AWB_NEIGHBORS_FOUR &&
        recorded->neighbours!=HB_AWB_NEIGHBORS_EIGHT))return HB_AWB_REBUILD_BAD_INPUT;
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i){
        uint8_t accepted=recorded->classifier_accepted[i];
        uint8_t zone=recorded->zone_override[i];
        uint8_t weight=recorded->final_weight[i];
        if(accepted>1 || zone>1 || weight>HB_AWB_MAX_SYNTHETIC_WEIGHT)
            return HB_AWB_REBUILD_BAD_INPUT;
        /* Do not manufacture unexplained weight for classifier-rejected cells.
         * An unknown other original branch needs its own explicit replay. */
        if(weight && !accepted && !zone) return HB_AWB_REBUILD_UNSUPPORTED;
    }
    hb_awb_scene_prepare_result tmp={0};
    if(hb_awb_prepare_raw_ae_evidence(original,&tmp.ae)!=HB_AWB_REBUILD_OK ||
       hb_awb_apply_explicit_calibration(original,calibration,&tmp.calibrated)!=HB_AWB_REBUILD_OK)
        return HB_AWB_REBUILD_BAD_INPUT;
    int status=hb_awb_accumulate_owned_candidates(&tmp.calibrated,
                       recorded->final_weight,recorded->classifier_accepted,
                       recorded->neighbours,&tmp.accumulation);
    if(status!=HB_AWB_REBUILD_OK)return status;
    uint8_t filtered[HB_AWB_FRAME_BLOCKS];
    hb_awb_component_stats filter={0};
    if(hb_awb_prune_small_components(recorded->final_weight,filtered,
                                    recorded->neighbours,&filter)!=HB_AWB_REBUILD_OK)
        return HB_AWB_REBUILD_BAD_INPUT;
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i){
        if(!filtered[i])continue;
        unsigned c=recorded->classifier_accepted[i], z=recorded->zone_override[i];
        if(z&&!c)++tmp.weighted_from_zone_not_classifier;
        if(c&&!z)++tmp.weighted_from_classifier;
        if(c&&z)++tmp.weighted_with_both_origins;
    }
    tmp.vendor_calibration_equivalence_proven=0;
    tmp.vendor_classification_equivalence_proven=0;
    tmp.produces_selected_neutral=0;
    *out=tmp;
    return HB_AWB_REBUILD_OK;
}