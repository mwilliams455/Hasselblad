/* SPDX-License-Identifier: MIT */
#include "hb_phone_neutral_observation.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

static int domain_valid(const hb_ns_domain *domain, uint32_t *valid) {
    if (domain->schema != HB_NS_SCHEMA || domain->count < 1 ||
        domain->count > HB_NS_MAX_KNOTS) return 0;
    int32_t last_tint=-101;
    uint32_t last_kelvin=0;
    *valid=0;
    for (uint32_t i=0;i<domain->count;++i) {
        const hb_ns_knot *k=&domain->points[i];
        if (k->kelvin<1667 || k->kelvin>100000 ||
            k->tint<-100 || k->tint>100 || k->exclusion>HB_NS_KNOT_DUPLICATE ||
            k->tint<last_tint ||
            (k->tint==last_tint && k->kelvin<=last_kelvin)) return 0;
        last_kelvin=k->kelvin;last_tint=k->tint;
        if (k->exclusion==HB_NS_KNOT_VALID) {
            if (!k->red_gain_q12 || k->red_gain_q12>32767 ||
                !k->blue_gain_q12 || k->blue_gain_q12>32767) return 0;
            ++*valid;
        } else if (k->red_gain_q12 || k->blue_gain_q12) return 0;
    }
    return *valid>0;
}
static int policy_valid(const hb_ns_policy *p) {
    return p->study_radius_q12>=1 && p->study_radius_q12<=4096 &&
        p->spatial_edge_radius_q12>=1 && p->spatial_edge_radius_q12<=4096 &&
        p->minimum_support_blocks>=4 && p->minimum_support_blocks<=1024 &&
        isfinite(p->minimum_brightness) && isfinite(p->maximum_brightness) &&
        p->minimum_brightness>=0 && p->maximum_brightness<=1 &&
        p->minimum_brightness<p->maximum_brightness &&
        isfinite(p->maximum_green_site_disagreement) &&
        p->maximum_green_site_disagreement>0 && p->maximum_green_site_disagreement<=1;
}
static int frame_valid(const hb_ns_frame *f) {
    if (!f->bound_to_physical_sensor_and_frame || !f->original_single_raw_proven ||
        !f->sensor_timestamp_ns || f->exposure_time_ns<1000 ||
        f->exposure_time_ns>UINT64_C(60000000000) ||
        f->ISO<1 || f->ISO>409600 ||
        (f->basis!=HB_NS_BASIS_UNSHADED_SENSOR &&
         f->basis!=HB_NS_BASIS_HYPOTHETICAL_SHADED_STATISTICS)) return 0;
    for (uint32_t i=0;i<HB_NS_BLOCK_COUNT;++i) {
        const hb_ns_block *b=&f->blocks[i];
        if (b->raw_flags & ~7u || !isfinite(b->mean_brightness)) return 0;
        for (int j=0;j<4;++j) if (!isfinite(b->mean[j])) return 0;
        double sum=(b->mean[0]+b->mean[1]+b->mean[2]+b->mean[3])*0.25;
        if (fabs(sum-b->mean_brightness)>1.e-12*fmax(1.,fabs(sum))) return 0;
        if (b->raw_flags) {
            /* An invalid RAW block cannot publish a valid gain pair. */
            if (b->red_gain_q12 || b->blue_gain_q12) return 0;
            continue;
        }
        for (int j=0;j<4;++j) if (b->mean[j]<=0) return 0;
        double green=(b->mean[1]+b->mean[2])*0.5;
        double red=green/b->mean[0]*4096.,blue=green/b->mean[3]*4096.;
        if (!(red>=1 && red<65536 && blue>=1 && blue<65536)) return 0;
        if (b->red_gain_q12!=(uint32_t)red ||
            b->blue_gain_q12!=(uint32_t)blue) return 0;
    }
    return 1;
}
static uint64_t squared(uint32_t r1,uint32_t b1,uint32_t r2,uint32_t b2) {
    int64_t dr=(int64_t)r1-(int64_t)r2, db=(int64_t)b1-(int64_t)b2;
    return (uint64_t)(dr*dr+db*db);
}
int hb_phone_neutral_observe(const hb_ns_domain *domain, const hb_ns_frame *frame,
                             const hb_ns_policy *policy, hb_ns_result *out) {
    if (!domain || !frame || !policy || !out) return HB_NS_ARGUMENT;
    uint32_t valid=0;
    if (!domain_valid(domain,&valid)) return HB_NS_DOMAIN_INVALID;
    if (!policy_valid(policy)) return HB_NS_POLICY_INVALID;
    if (!frame_valid(frame)) return HB_NS_FRAME_UNPROVEN;

    hb_ns_result *result=calloc(1,sizeof(*result));
    if (!result) return HB_NS_MEMORY;
    result->schema=HB_NS_SCHEMA;
    result->render_permitted=0;
    result->calibrated_policy=0;
    result->shading_basis=frame->basis;
    result->usable_domain_points=valid;
    result->excluded_domain_points=domain->count-valid;
    int32_t min_tint=domain->points[0].tint,
            max_tint=domain->points[domain->count-1].tint;
    uint32_t near_indices[HB_NS_BLOCK_COUNT]={0};
    uint32_t near_count=0;
    uint64_t radius_sq=(uint64_t)policy->study_radius_q12*policy->study_radius_q12;
    for (uint32_t i=0;i<HB_NS_BLOCK_COUNT;++i) {
        const hb_ns_block *b=&frame->blocks[i];
        hb_ns_trace *t=&result->blocks[i];
        t->nearest_knot_index=HB_NS_NO_INDEX;
        t->component_index=HB_NS_NO_INDEX;
        if (b->raw_flags) {
            t->reason=HB_NS_BLOCK_RAW_REJECTED;
            ++result->raw_rejected;
            continue;
        }
        if (b->mean_brightness<policy->minimum_brightness ||
            b->mean_brightness>policy->maximum_brightness) {
            t->reason=HB_NS_BLOCK_BRIGHTNESS_REJECTED;
            ++result->brightness_rejected;
            continue;
        }
        double greens=(b->mean[1]+b->mean[2])*0.5;
        if (fabs(b->mean[1]-b->mean[2])/greens >
            policy->maximum_green_site_disagreement) {
            t->reason=HB_NS_BLOCK_GREEN_SPLIT_REJECTED;
            ++result->green_split_rejected;
            continue;
        }
        if (b->red_gain_q12>32767 || b->blue_gain_q12>32767) {
            t->reason=HB_NS_BLOCK_SIGNED_GAIN_REJECTED;
            ++result->signed_gain_rejected;
            continue;
        }
        ++result->evaluated_blocks;
        uint64_t best=UINT64_MAX;
        for (uint32_t k=0;k<domain->count;++k) {
            const hb_ns_knot *point=&domain->points[k];
            if (point->exclusion!=HB_NS_KNOT_VALID) continue;
            uint64_t dist=squared(b->red_gain_q12,b->blue_gain_q12,
                                 point->red_gain_q12,point->blue_gain_q12);
            if (dist<best) {best=dist;t->nearest_knot_index=k;}
        }
        if (best==UINT64_MAX) {free(result);return HB_NS_DOMAIN_INVALID;}
        t->distance_q12=(float)sqrt((double)best);
        if (best>radius_sq) {++result->far_from_grid;continue;}
        t->near_lattice=1;
        near_indices[near_count++]=i;
        ++result->near_valid_knot;
        const hb_ns_knot *k=&domain->points[t->nearest_knot_index];
        if (k->tint==min_tint || k->tint==max_tint) ++result->near_tint_edge;
        uint32_t q=((i/32)>=16 ? 2u:0u) | ((i%32)>=16 ? 1u:0u);
        result->near_quadrants_bitmask |= (1u<<q);
    }
    /* Valid 8-neighbour topology in a real 32x32 grid; unlike the recovered
     * older connected filter, links may NOT wrap across image-row borders. */
    uint32_t queue[HB_NS_BLOCK_COUNT];
    uint64_t max_edge_sq=(uint64_t)policy->spatial_edge_radius_q12*
                         policy->spatial_edge_radius_q12;
    for (uint32_t n=0;n<near_count;++n) {
        uint32_t initial=near_indices[n];
        if (result->blocks[initial].component_index!=HB_NS_NO_INDEX) continue;
        uint32_t head=0,tail=0,component=result->spatial_components++;
        queue[tail++]=initial;
        result->blocks[initial].component_index=component;
        while(head<tail) {
            uint32_t current=queue[head++];
            int y=(int)(current/32),x=(int)(current%32);
            for (int dy=-1;dy<=1;++dy) for (int dx=-1;dx<=1;++dx) {
                if (!dy && !dx) continue;
                int yy=y+dy,xx=x+dx;
                if (yy<0 || yy>=32 || xx<0 || xx>=32) continue;
                uint32_t next=(uint32_t)(yy*32+xx);
                if (!result->blocks[next].near_lattice ||
                    result->blocks[next].component_index!=HB_NS_NO_INDEX) continue;
                if (squared(frame->blocks[current].red_gain_q12,
                            frame->blocks[current].blue_gain_q12,
                            frame->blocks[next].red_gain_q12,
                            frame->blocks[next].blue_gain_q12)>max_edge_sq) continue;
                result->blocks[next].component_index=component;
                queue[tail++]=next;
            }
        }
        if (tail>result->largest_spatial_component)
            result->largest_spatial_component=tail;
    }
    result->support_threshold_met=(result->largest_spatial_component>=
                                   policy->minimum_support_blocks);
    /* Proximity, component size, uniformity and exposure alone never certify
     * a neutral target or provide a shipping WB gain. No measured reflector
     * or illuminant reference was supplied to this isolated research API. */
    result->decision=result->support_threshold_met ?
        HB_NS_ABSTAIN_UNCALIBRATED:HB_NS_ABSTAIN_NO_CANDIDATE_SUPPORT;
    *out=*result;
    free(result);
    return HB_NS_OK;
}
