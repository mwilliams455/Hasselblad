/* SPDX-License-Identifier: MIT */
#include "hb_phone_scene.h"
#include "../awb_original_runtime_20261021/hb_scene_candidates.h"
#include "../awb_original_runtime_20261021/hb_scene_filter.h"
#include "../awb_original_runtime_20261021/hb_scene_optimizer.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

struct hb_phone_scene {
    hb_phone_temperature *temperature;
    hb_phone_scene_policy policy;
    uint32_t locus[81][3];
    unsigned char cfg[1502800]; /* Disabled optional weighting; no auto profile. */
};
static uint32_t u32(const void *p) {uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void *p) {uint16_t v;memcpy(&v,p,2);return v;}
static void w32(void *p,uint32_t v) {memcpy(p,&v,4);}
static void wf(void *p,float v) {memcpy(p,&v,4);}

int hb_phone_scene_create(const hb_phone_temperature_input *input,
                         const hb_phone_scene_policy *p,hb_phone_scene **out) {
    if (!input || !p || !out) return HB_PHONE_SCENE_ARGUMENT;
    if (!isfinite(p->center_tint) || fabsf(p->center_tint)>100 ||
        p->radius_q12<1 || p->radius_q12>4096 ||
        p->neighbor_factor<1 || p->neighbor_factor>255 || p->neighbor_factor>p->radius_q12 ||
        p->minimum_blocks<4 || p->minimum_blocks>1020 || p->minimum_blocks%4 ||
        !isfinite(p->minimum_brightness) || !isfinite(p->maximum_brightness) ||
        p->minimum_brightness<0 || p->maximum_brightness>1 ||
        p->minimum_brightness>=p->maximum_brightness) return HB_PHONE_SCENE_POLICY;
    hb_phone_temperature *temperature=NULL;
    if (hb_phone_temperature_create(input,&temperature)) return HB_PHONE_SCENE_MODEL;
    hb_phone_scene *s=calloc(1,sizeof(*s));
    if (!s) {hb_phone_temperature_destroy(temperature);return HB_PHONE_SCENE_MEMORY;}
    s->temperature=temperature;s->policy=*p;
    for (unsigned i=0;i<81;++i) {
        hb_phone_temperature_gains gain;
        if (hb_phone_temperature_to_gain(temperature,2000+100*i,p->center_tint,&gain)) goto bad_model;
        s->locus[i][0]=2000+100*i;
        s->locus[i][1]=(uint32_t)(((uint64_t)gain.gain_q12[0]*4096)/gain.gain_q12[1]);
        s->locus[i][2]=(uint32_t)(((uint64_t)gain.gain_q12[2]*4096)/gain.gain_q12[1]);
        /* Native connected filtering compares signed 16-bit channel values.
         * Bound both the locus and admitted blocks to the positive domain. */
        if (!s->locus[i][1] || s->locus[i][1]>32767 || !s->locus[i][2] || s->locus[i][2]>32767) goto bad_model;
        if (i && s->locus[i][1]==s->locus[i-1][1] && s->locus[i][2]==s->locus[i-1][2]) goto bad_model;
    }
    *out=s;return HB_PHONE_SCENE_OK;
bad_model:
    hb_phone_scene_destroy(s);return HB_PHONE_SCENE_MODEL;
}
void hb_phone_scene_destroy(hb_phone_scene *s) {
    if (s) {hb_phone_temperature_destroy(s->temperature);free(s);}
}
int hb_phone_scene_locus(const hb_phone_scene *s,uint32_t out[81][3]) {
    if (!s || !out) return HB_PHONE_SCENE_ARGUMENT;
    memcpy(out,s->locus,sizeof(s->locus));return 0;
}
static int valid_block(const hb_phone_block *b) {
    if (b->flags&~7u || !isfinite(b->mean_brightness)) return 0;
    for (unsigned j=0;j<4;++j) if (!isfinite(b->mean[j])) return 0;
    double mean=((b->mean[0]+b->mean[1])+b->mean[2])+b->mean[3];mean*=0.25;
    if (fabs(mean-b->mean_brightness)>1e-12*fmax(1,fabs(mean))) return 0;
    if (b->flags) return b->red_gain_q12==0 && b->blue_gain_q12==0;
    for (unsigned j=0;j<4;++j) if (b->mean[j]<=0) return 0;
    double green=(b->mean[1]+b->mean[2])*0.5;
    double red=green/b->mean[0]*4096,blue=green/b->mean[3]*4096;
    if (red<1 || red>=65536 || blue<1 || blue>=65536) return 0;
    return b->red_gain_q12==(uint32_t)red && b->blue_gain_q12==(uint32_t)blue;
}
int hb_phone_scene_run(const hb_phone_scene *s,const hb_phone_raw_grid *grid,hb_phone_scene_result *out) {
    if (!s || !grid || !out) return HB_PHONE_SCENE_ARGUMENT;
    for (unsigned i=0;i<1024;++i) if (!valid_block(&grid->blocks[i])) return HB_PHONE_SCENE_ARGUMENT;
    unsigned char *c=calloc(1,920560);
    hb_phone_scene_result *result=calloc(1,sizeof(*result));
    if (!c || !result) {free(c);free(result);return HB_PHONE_SCENE_MEMORY;}
    w32(c+0x18,32);w32(c+0x1c,32);w32(c+0x28,1024);
    for (unsigned i=0;i<81;++i) {
        memcpy(c+0x344+16*i,s->locus[i],12);w32(c+0x350+16*i,s->policy.radius_q12);
        c[0x1734+i]=255; /* Uniform CT prior, explicitly not spectral data. */
    }
    for (unsigned i=0;i<1024;++i) {
        const hb_phone_block *b=&grid->blocks[i];hb_phone_scene_block_trace *t=&result->blocks[i];
        if (b->flags) {t->reason=HB_PHONE_SCENE_RAW_REJECTED;continue;}
        ++result->raw_valid;
        if (b->mean_brightness<s->policy.minimum_brightness || b->mean_brightness>s->policy.maximum_brightness) {
            t->reason=HB_PHONE_SCENE_BRIGHTNESS_REJECTED;continue;
        }
        if (b->red_gain_q12>32767 || b->blue_gain_q12>32767) {t->reason=HB_PHONE_SCENE_SIGNED_GAIN_REJECTED;continue;}
        ++result->admitted;
        /* Exhaustive phone classification: the calibrated curve need not meet
         * the recovered sparse LUT search's unimodality assumption. */
        uint64_t best=UINT64_MAX;unsigned nearest=0;
        for (unsigned j=0;j<81;++j) {
            int64_t dr=(int64_t)b->red_gain_q12-s->locus[j][1];
            int64_t db=(int64_t)b->blue_gain_q12-s->locus[j][2];
            uint64_t distance=(uint64_t)(dr*dr+db*db);
            if (distance<best) {best=distance;nearest=j;}
        }
        double distance=sqrt((double)best);t->locus_index=nearest;t->distance_q12=(float)distance;
        if (best>(uint64_t)s->policy.radius_q12*s->policy.radius_q12) continue;
        t->classified=1;++result->classified;
        unsigned char *d=c+0xf450+40*i;
        w32(d,b->red_gain_q12);w32(d+4,4096);w32(d+8,b->blue_gain_q12);
        w32(d+12,2000+100*nearest);w32(d+16,nearest);d[24]=1;
        wf(d+28,(float)(1-distance/s->policy.radius_q12));
    }
    unsigned char parameters[508]={0},curves[584]={0};
    w32(parameters+4,24); /* Exposure-independent eligibility and weights. */
    parameters[10]=parameters[11]=1;
    curves[0]=1;curves[5]=1;w32(curves+8,2000);curves[12]=1;curves[20]=1;
    c[0x3dacc]=1;
    uint32_t status=hb_candidate_weight(c,s->cfg,parameters,0,0);
    if (status) goto native_error;
    for (unsigned i=0;i<1024;++i) result->blocks[i].weight_before=u16(c+0x3dace +2*i);
    status=hb_scene_filter(c,0,0,s->policy.neighbor_factor);
    if (status) goto native_error;
    for (unsigned i=0;i<1024;++i) {
        hb_phone_scene_block_trace *t=&result->blocks[i];
        t->weight_after=u16(c+0x3dace +2*i);t->survives=t->weight_after!=0;result->retained+=t->survives;
    }
    if (result->retained<s->policy.minimum_blocks) goto done;
    status=hb_candidate_accumulate_with_model(c,s->cfg,parameters,curves,0,0,0,s->policy.minimum_blocks/4,NULL);
    if (status) goto native_error;
    status=hb_scene_optimizer(c,0,1,parameters);
    if (status) goto native_error;
    if (c[0x4dbcc]!=1) goto done;
    uint32_t gain[3]={u32(c+0x4dbd0),u32(c+0x4dbd4),u32(c+0x4dbd8)};
    hb_phone_temperature_estimate estimate;
    status=(uint32_t)hb_phone_temperature_from_gain(s->temperature,gain,&estimate);
    if (status) {
        result->decision=HB_PHONE_SCENE_TEMPERATURE_REJECTED;result->native_status=status;goto done;
    }
    result->decision=HB_PHONE_SCENE_DIAGNOSTIC_CANDIDATE;
    memcpy(result->gain_q12,gain,sizeof(gain));result->temperature=estimate;
    result->neutral[0]=4096.0f/gain[0];result->neutral[1]=1;result->neutral[2]=4096.0f/gain[2];
done:
    *out=*result;free(c);free(result);return HB_PHONE_SCENE_OK;
native_error:
    free(c);free(result);return HB_PHONE_SCENE_NATIVE;
}
