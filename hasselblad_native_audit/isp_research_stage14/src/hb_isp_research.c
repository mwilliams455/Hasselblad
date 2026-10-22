/* SPDX-License-Identifier: MIT */
#include "hb_isp_research.h"
#include "hb_main_lut_profile.h"
#include "hb_display_lut16.h"
#include "ccm_prepare.h"
#include <math.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

static int intersects(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x=(uintptr_t)a, y=(uintptr_t)b;
    return x<=y ? y-x<an : x-y<bn;
}
static int regions_distinct(const void *const *v, const size_t *n, size_t count) {
    for(size_t i=0;i<count;++i) {
        if(!v[i] || !n[i]) return 0;
        for(size_t j=0;j<i;++j)
            if(intersects(v[i],n[i],v[j],n[j])) return 0;
    }
    return 1;
}

int hb_isp_research_gamma_knots(const uint32_t divisions[7],
                                 uint32_t coordinates[257]) {
    if(!divisions || !coordinates) return HB_ISP_BAD_ARGS;
    if(intersects(divisions,7u*sizeof(*divisions),coordinates,
                  257u*sizeof(*coordinates))) return HB_ISP_ALIAS;
    static const uint32_t boundaries[8]={0,1024,2048,4096,8192,
                                         16384,32768,65536};
    uint32_t intervals=0;
    for(unsigned i=0;i<7;++i) {
        if(divisions[i]>7u) return HB_ISP_BAD_DOMAIN;
        intervals+=1u<<divisions[i];
    }
    if(intervals!=256u) return HB_ISP_BAD_DOMAIN;
    uint32_t tmp[257]={0};
    unsigned cursor=1;
    for(unsigned i=0;i<7;++i) {
        const uint32_t n=1u<<divisions[i];
        const uint32_t left=boundaries[i],right=boundaries[i+1];
        /* Same rounded-region step as original [0x3866b0,0x386d28). */
        const uint32_t step=((right-left)+(n/2u))/n;
        for(uint32_t j=1;j<n;++j)
            tmp[cursor++]=left+j*step;
        tmp[cursor++]=right;
    }
    if(cursor!=257u) return HB_ISP_PREPARATION_FAILED;
    memcpy(coordinates,tmp,sizeof(tmp));
    return HB_ISP_OK;
}

int hb_isp_research_prepare(const uint32_t *lut_profiles, size_t lut_source_count,
                            const int32_t *ccm_profiles, size_t ccm_source_count,
                            const uint32_t gamma_divisions[7],
                            int32_t cct_kelvin, int32_t gamut_selector,
                            int32_t secondary_ccm_weight_q8, uint32_t route,
                            uint32_t prepared_lut[6144],
                            int32_t prepared_ccm[96],
                            uint32_t gamma_coordinates[257],
                            hb_isp_research_receipt *receipt) {
    if(!lut_profiles || !ccm_profiles || !gamma_divisions || !prepared_lut ||
       !prepared_ccm || !gamma_coordinates || !receipt) return HB_ISP_BAD_ARGS;
    if(lut_source_count!=HB_ISP_MAIN_SOURCE_WORDS ||
       ccm_source_count!=HB_ISP_CCM_SOURCE_VALUES) return HB_ISP_BAD_SHAPE;
    if(route>HB_ISP_ROUTE_ENHANCED_HDR_STILL0 || gamut_selector<0 ||
       gamut_selector>1 || secondary_ccm_weight_q8<0 ||
       secondary_ccm_weight_q8>256) return HB_ISP_BAD_DOMAIN;
    const void *v[]={lut_profiles, ccm_profiles, gamma_divisions,
                     prepared_lut,prepared_ccm,gamma_coordinates,receipt};
    const size_t n[]={49152u*sizeof(uint32_t),768u*sizeof(int32_t),
        7u*sizeof(uint32_t),6144u*sizeof(uint32_t),96u*sizeof(int32_t),
        257u*sizeof(uint32_t),sizeof(*receipt)};
    if(!regions_distinct(v,n,7)) return HB_ISP_ALIAS;

    /* Atomic stage bundle: no public outputs before every prerequisite passes.
     * This does NOT claim validity of CCM/gamma/MMAIN per-pixel algorithms. */
    uint32_t *tmp_lut=malloc(6144u*sizeof(uint32_t));
    int32_t *tmp_ccm=malloc(96u*sizeof(int32_t));
    uint32_t *tmp_gamma=malloc(257u*sizeof(uint32_t));
    if(!tmp_lut || !tmp_ccm || !tmp_gamma) {
        free(tmp_lut);free(tmp_ccm);free(tmp_gamma);
        return HB_ISP_ALLOCATION;
    }
    int status=hb_isp_research_gamma_knots(gamma_divisions,tmp_gamma);
    hb_main_lut_receipt profile={0};
    if(status==HB_ISP_OK && hb_main_lut_prepare(lut_profiles,lut_source_count,
           6144u,cct_kelvin,gamut_selector,tmp_lut,6144u,&profile)!=HB_MAIN_LUT_OK)
        status=HB_ISP_PREPARATION_FAILED;
    if(status==HB_ISP_OK && hb_ccm_prepare(ccm_profiles,ccm_source_count,
           cct_kelvin,secondary_ccm_weight_q8,tmp_ccm,96u)!=HB_CCM_OK)
        status=HB_ISP_PREPARATION_FAILED;
    if(status==HB_ISP_OK) {
        if(profile.photographic_render_authorized || profile.pixel_sampler_verified ||
           profile.words_written!=6144u) status=HB_ISP_PREPARATION_FAILED;
    }
    if(status==HB_ISP_OK) {
        hb_isp_research_receipt r={0};
        r.schema=HB_ISP_RESEARCH_SCHEMA;
        r.research_only=1u;
        r.photographic_render_authorized=0u;
        r.main_pixel_sampler_verified=0u;
        r.ccm_pixel_equation_verified=0u;
        r.gamma_pixel_evaluation_verified=0u;
        r.display_only_sampler_reference=1u;
        r.route=route;
        r.cct_first_index=profile.cct_first_index;
        r.cct_fraction_q8=profile.cct_fraction_q8;
        r.gamut_selector=(uint32_t)gamut_selector;
        r.secondary_ccm_weight_q8=(uint32_t)secondary_ccm_weight_q8;
        r.prepared_lut_words=6144u;
        r.prepared_ccm_values=96u;
        r.gamma_coordinate_count=257u;
        r.unresolved_contracts_mask=HB_ISP_UNRESOLVED_ALL;
        memcpy(prepared_lut,tmp_lut,6144u*sizeof(uint32_t));
        memcpy(prepared_ccm,tmp_ccm,96u*sizeof(int32_t));
        memcpy(gamma_coordinates,tmp_gamma,257u*sizeof(uint32_t));
        *receipt=r;
    }
    free(tmp_lut);free(tmp_ccm);free(tmp_gamma);
    return status;
}

int hb_isp_research_display_candidate(const uint32_t prepared_lut[6144],
             const double *input_rgb, size_t rgb_count,
             double *output_rgb, hb_isp_research_receipt *receipt) {
    if(!prepared_lut || !input_rgb || !output_rgb || !receipt)
        return HB_ISP_BAD_ARGS;
    if(!rgb_count || rgb_count>HB_ISP_MAX_PROBE_PIXELS) return HB_ISP_BAD_SHAPE;
    const size_t rgb_bytes=rgb_count*3u*sizeof(double);
    const void *v[]={prepared_lut,input_rgb,output_rgb,receipt};
    const size_t n[]={6144u*sizeof(uint32_t),rgb_bytes,rgb_bytes,sizeof(*receipt)};
    if(!regions_distinct(v,n,4)) return HB_ISP_ALIAS;
    if(receipt->schema!=HB_ISP_RESEARCH_SCHEMA ||
       receipt->prepared_lut_words!=6144u ||
       receipt->photographic_render_authorized!=0u ||
       receipt->main_pixel_sampler_verified!=0u ||
       receipt->display_only_sampler_reference!=1u ||
       receipt->unresolved_contracts_mask!=HB_ISP_UNRESOLVED_ALL)
        return HB_ISP_BAD_DOMAIN;
    for(size_t i=0;i<rgb_count*3u;++i) {
        if(!isfinite(input_rgb[i]) || input_rgb[i]<0.0 || input_rgb[i]>1.0)
            return HB_ISP_BAD_DOMAIN; /* Never silently crush signed headroom. */
    }
    double *tmp=malloc(rgb_bytes);
    if(!tmp) return HB_ISP_ALLOCATION;
    int status=HB_ISP_OK;
    for(size_t i=0;i<rgb_count;++i) {
        if(hb_display_lut16_trilinear(prepared_lut,6144u,
              input_rgb+3u*i,tmp+3u*i)!=HB_DISPLAY_LUT16_OK) {
            status=HB_ISP_PREPARATION_FAILED;break;
        }
    }
    if(status==HB_ISP_OK) {
        hb_isp_research_receipt r=*receipt;
        r.sampled_test_pixels=(uint32_t)rgb_count;
        memcpy(output_rgb,tmp,rgb_bytes);
        *receipt=r;
    }
    free(tmp);
    return status;
}

int hb_isp_research_main_gate(uint32_t *missing_contracts_mask) {
    if(!missing_contracts_mask) return HB_ISP_BAD_ARGS;
    *missing_contracts_mask=HB_ISP_UNRESOLVED_ALL;
    return HB_ISP_UNVERIFIED_PHOTOGRAPHIC;
}
