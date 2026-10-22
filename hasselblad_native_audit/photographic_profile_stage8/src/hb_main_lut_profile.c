/* SPDX-License-Identifier: MIT */
#include "hb_main_lut_profile.h"
#include <stdint.h>
#include <stddef.h>

static int overlaps(const void *a, size_t a_bytes, const void *b, size_t b_bytes) {
    uintptr_t x = (uintptr_t)a, y=(uintptr_t)b;
    if (x<=y) return (y-x)<a_bytes;
    return (x-y)<b_bytes;
}
static int32_t signed16(uint32_t u, unsigned lane) {
    uint32_t v = (u >> (lane*16u)) & UINT32_C(0xffff);
    return v >= 32768u ? (int32_t)v-65536 : (int32_t)v;
}
static uint32_t pack16(int32_t a, int32_t b) {
    return (uint32_t)(uint16_t)a | ((uint32_t)(uint16_t)b<<16);
}
static int32_t q8_blend(int32_t a, int32_t b, int32_t f) {
    int64_t p = ((int64_t)b-(int64_t)a)*(int64_t)f;
    int32_t delta=p<0 ? -(int32_t)((-p+255)/256) : (int32_t)(p/256);
    return a+delta;
}
static void cct_coeff(int32_t cct, uint32_t *index, uint32_t *fraction) {
    const int32_t knots[4]={2400,3050,5550,9100};
    if(cct<knots[0]) {*index=0; *fraction=0;return;}
    if(cct>=knots[3]) {*index=2; *fraction=256;return;}
    for(uint32_t i=0;i<3;++i) {
        if(cct<knots[i+1]) {
            *index=i;
            *fraction=(uint32_t)(((int64_t)cct-knots[i])*256/(knots[i+1]-knots[i]));
            return;
        }
    }
}
int hb_main_lut_prepare(const uint32_t *source, size_t source_words,
                        size_t words_per_profile, int32_t cct_kelvin,
                        int32_t gamut_selector, uint32_t *dest,
                        size_t dest_capacity_words, hb_main_lut_receipt *receipt) {
    if(!source || !dest || !receipt) return HB_MAIN_LUT_INVALID_ARGS;
    if(words_per_profile==0 || words_per_profile>HB_MAIN_LUT_MAX_WORDS_PER_PROFILE ||
       source_words!=HB_MAIN_LUT_PROFILE_COUNT*words_per_profile ||
       dest_capacity_words<words_per_profile ||
       dest_capacity_words>HB_MAIN_LUT_MAX_WORDS_PER_PROFILE)
        return HB_MAIN_LUT_INVALID_SHAPE;
    if(gamut_selector!=0 && gamut_selector!=1) return HB_MAIN_LUT_UNSUPPORTED_GAMUT;
    if(overlaps(source,source_words*sizeof(uint32_t),dest,words_per_profile*sizeof(uint32_t)) ||
       overlaps(source,source_words*sizeof(uint32_t),receipt,sizeof(*receipt)) ||
       overlaps(dest,words_per_profile*sizeof(uint32_t),receipt,sizeof(*receipt)))
        return HB_MAIN_LUT_OVERLAPPING_MEMORY;

    uint32_t c=0,f=0;
    cct_coeff(cct_kelvin,&c,&f);
    /* First axis: CCT, then gamut (the exact original camera axis order). */
    for(size_t j=0;j<words_per_profile;++j) {
        int32_t lanes[2];
        for(unsigned lane=0;lane<2;++lane) {
            int32_t a=q8_blend(signed16(source[c*words_per_profile+j],lane),
                        signed16(source[(c+1)*words_per_profile+j],lane),(int32_t)f);
            int32_t b=q8_blend(signed16(source[(c+4)*words_per_profile+j],lane),
                        signed16(source[(c+5)*words_per_profile+j],lane),(int32_t)f);
            lanes[lane]=q8_blend(a,b,gamut_selector*256);
        }
        dest[j]=pack16(lanes[0],lanes[1]);
    }
    hb_main_lut_receipt r={0};
    r.schema=HB_MAIN_LUT_PROFILE_SCHEMA;
    r.cct_first_index=c;
    r.cct_fraction_q8=f;
    r.gamut_index=0;
    r.gamut_fraction_q8=(uint32_t)gamut_selector*256u;
    r.words_written=(uint32_t)words_per_profile;
    r.pixel_sampler_verified=0;
    r.photographic_render_authorized=0;
    *receipt=r;
    return HB_MAIN_LUT_OK;
}
