/* SPDX-License-Identifier: MIT
 * An owned composition of Stage18, Stage19, and optionally Stage21. No vendor
 * photographic LUT data, undocumented CCM matrix, Film Tone or Android hooks.
 */
#include "hb24_renderer.h"
#include <math.h>
#include <stdint.h>
#include <string.h>

static int overlap(const void *a, size_t n, const void *b, size_t m) {
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=y ? (y-x)<n : (x-y)<m;
}
static int finite_all(const double *x,size_t n){
    if(!x)return 0;
    for(size_t i=0;i<n;i++)if(!isfinite(x[i]))return 0;
    return 1;
}
int hb24_build(const double fm1[9], const double fm2[9],
               const double cc1[9], const double cc2[9],
               const double analog_balance[3], const double neutral[3],
               int gamut, hb24_context *ctx, hb24_receipt *receipt) {
    if(!ctx||!receipt||!fm1||!neutral)return HB24_BAD_INPUT;
    if(gamut!=HB19_SRGB&&gamut!=HB19_DISPLAY_P3)return HB24_BAD_INPUT;
    if(overlap(ctx,sizeof(*ctx),receipt,sizeof(*receipt)))return HB24_OVERLAP;
    hb24_context draft={0};hb_dng_pcs_receipt dr={0};hb19_output_receipt gr={0};
    const double identity_analog_balance[3]={1.0,1.0,1.0};
    int a=hb_dng_pcs_build(fm1,fm2,cc1,cc2,
                           analog_balance?analog_balance:identity_analog_balance,neutral,
                           draft.camera_to_xyz_d50,&dr);
    if(a!=HB_DNG_PCS_OK)return a==HB_DNG_PCS_UNSUPPORTED_INTERPOLATION?
        HB24_UNSUPPORTED_PROFILE:HB24_BAD_INPUT;
    if(hb19_build_output_matrix(gamut,draft.xyz_d50_to_linear_rgb,&gr)!=HB19_OK)
        return HB24_NUMERIC;
    draft.schema=HB24_SCHEMA;draft.gamut=(uint32_t)gamut;
    hb24_receipt r={0};r.schema=HB24_SCHEMA;r.display_gamut=(uint32_t)gamut;
    r.pcs_normalized_neutral=dr.numerical_pcs_white_verified;
    r.output_linear_light=1;
    memcpy(ctx,&draft,sizeof(draft));*receipt=r;
    return HB24_OK;
}
int hb24_process(const hb24_context *ctx, const double *camera, size_t n,
                 double *output, int mode, const uint32_t *lut,size_t lut_words,
                 const uint8_t axes[3],const uint8_t banks[3],int interpolation,
                 hb24_receipt *receipt) {
    if(!ctx||!camera||!output||!receipt||ctx->schema!=HB24_SCHEMA)
        return HB24_BAD_INPUT;
    if(!n||n>HB24_MAX_PIXELS)return HB24_BAD_SIZE;
    if(ctx->gamut>1||!finite_all(ctx->camera_to_xyz_d50,9)||
       !finite_all(ctx->xyz_d50_to_linear_rgb,9))return HB24_BAD_INPUT;
    if(mode!=HB24_PCS_ONLY&&mode!=HB24_MAIN_HYPOTHESIS)return HB24_BAD_INPUT;
    if(mode==HB24_MAIN_HYPOTHESIS &&
       (!lut||!axes||!banks||lut_words!=HB21_TABLE_WORDS))return HB24_BAD_INPUT;
    size_t b=n*3*sizeof(double);
    if(overlap(camera,b,output,b)||overlap(camera,b,ctx,sizeof(*ctx))||
       overlap(output,b,ctx,sizeof(*ctx))||
       overlap(camera,b,receipt,sizeof(*receipt))||
       overlap(output,b,receipt,sizeof(*receipt))||
       overlap(ctx,sizeof(*ctx),receipt,sizeof(*receipt)))return HB24_OVERLAP;
    if(mode==HB24_MAIN_HYPOTHESIS &&
       (overlap(lut,lut_words*sizeof(uint32_t),camera,b)||
        overlap(lut,lut_words*sizeof(uint32_t),output,b)||
        overlap(lut,lut_words*sizeof(uint32_t),receipt,sizeof(*receipt))||
        overlap(lut,lut_words*sizeof(uint32_t),ctx,sizeof(*ctx))))return HB24_OVERLAP;
    if(!finite_all(camera,n*3))return HB24_BAD_INPUT;
    double xyz[HB24_MAX_PIXELS*3];
    double display[HB24_MAX_PIXELS*3];
    if(hb_dng_pcs_apply(ctx->camera_to_xyz_d50,camera,n,xyz)!=HB_DNG_PCS_OK)
        return HB24_NUMERIC;
    if(hb19_apply_output_matrix(ctx->xyz_d50_to_linear_rgb,xyz,n,display)!=HB19_OK)
        return HB24_NUMERIC;
    if(mode==HB24_MAIN_HYPOTHESIS){
        for(size_t i=0;i<3*n;i++)
            if(!isfinite(display[i])||display[i]<0.||display[i]>1.)
                return HB24_UNVERIFIED_DOMAIN;
        hb21_receipt tmp={0};
        int status=hb21_sample_candidate(lut,lut_words,display,n*3,xyz,n*3,n,
                                          axes,banks,interpolation,&tmp);
        if(status!=HB21_OK)return status==HB21_INVALID_RGB?
            HB24_UNVERIFIED_DOMAIN:HB24_BAD_INPUT;
        if(tmp.photographic_render_authorized||tmp.main_isp_pixel_equivalence_proven)
            return HB24_NUMERIC;
        memcpy(display,xyz,b);
    }
    hb24_receipt r={0};r.schema=HB24_SCHEMA;r.pixel_count=(uint32_t)n;
    r.display_gamut=ctx->gamut;r.pcs_normalized_neutral=1;
    r.output_linear_light=1;r.uses_stage21_MAIN_hypothesis=(mode==HB24_MAIN_HYPOTHESIS);
    /* Other fields deliberately remain zero: no false HNCS parity claim. */
    memcpy(output,display,b);*receipt=r;
    return HB24_OK;
}
