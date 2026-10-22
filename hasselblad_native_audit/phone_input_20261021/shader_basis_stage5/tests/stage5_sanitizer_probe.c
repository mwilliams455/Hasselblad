/* SPDX-License-Identifier: MIT */
#include "hb_phone_stage5_basis.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

int main(void) {
    const size_t count=64u*64u;
    uint8_t *raw=malloc(count*2u);
    float *map=malloc(sizeof(float)*2u*2u*4u);
    hb_s5_result *result=malloc(sizeof(*result));
    assert(raw && map && result);
    for(size_t i=0;i<count;++i) {
        uint16_t code=(uint16_t)(100u+(i%75u));
        raw[2u*i]=(uint8_t)code;raw[2u*i+1u]=(uint8_t)(code>>8);
    }
    for(size_t i=0;i<16u;++i)map[i]=1.f+0.21f*(float)i;
    hb_s5_input input={0};
    input.raw_le16=raw;input.raw_bytes=count*2u;
    input.width=64;input.height=64;input.row_stride_bytes=128;
    input.cfa=0;input.black_raw_code=64;input.white_raw_code=1023;
    input.lens_map_rg_gb_b=map;input.map_width=2;input.map_height=2;input.map_floats=16;
    input.study_basis=HB_S5_PHOTON_RELATIVE;
    input.timestamp_ns=219959124714440u;input.exposure_ns=24000000u;
    input.ISO=50;input.proven_sensor_and_frame=1;input.original_single_raw=1;
    assert(hb_s5_project(&input,result)==HB_S5_OK);
    assert(result->schema==1 && result->render_permitted==0 && result->study_only==1);
    assert(result->observed_pixels==count && result->map_quantized_as_fp16==1);
    for(size_t i=0;i<1024;++i) {
        assert(isfinite(result->observation.blocks[i].mean_brightness));
        assert(result->observation.blocks[i].mean_brightness>0);
        assert(result->observation.blocks[i].raw_flags==0);
        assert(result->observation.blocks[i].red_gain_q12>0);
        assert(result->observation.blocks[i].blue_gain_q12>0);
    }
    memset(result,0xa5,sizeof(*result));
    input.proven_sensor_and_frame=0;
    assert(hb_s5_project(&input,result)==HB_S5_UNPROVEN);
    for(size_t i=0;i<sizeof(*result);++i)assert(((unsigned char*)result)[i]==0xa5);
    input.proven_sensor_and_frame=1;
    map[2]=NAN;
    assert(hb_s5_project(&input,result)==HB_S5_INVALID_MAP);
    for(size_t i=0;i<sizeof(*result);++i)assert(((unsigned char*)result)[i]==0xa5);
    free(raw);free(map);free(result);
    return 0;
}
