/* SPDX-License-Identifier: MIT
 * Independent owned-data checks for the portable CCM adapter contract.
 * No original firmware or coefficient payload is read or executed.
 */
#include "ccm_prepare.h"
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checked;
static void check(const char *name, int passed) {
    printf("{\"case\":\"%s\",\"pass\":%s}\n", name, passed ? "true" : "false");
    if (!passed) exit(1);
    ++checked;
}
static void fixture(int32_t *source) {
    for (int p=0; p<8; ++p)
        for (int k=0; k<96; ++k)
            source[p*96+k]=p*5000+k*7-20000;
}
static int intact(const int32_t *a, const int32_t *b, size_t words) {
    return !memcmp(a,b,words*sizeof(*a));
}

int main(void) {
    int32_t source[768], source_before[768], output[98], output_before[98];
    fixture(source);
    memcpy(source_before,source,sizeof(source));
    for (int k=0; k<98; ++k) output[k]=0x31415926;
    memcpy(output_before,output,sizeof(output));
    struct { const char *name; size_t input_length; size_t output_length; int weight; } cases[] = {
        {"short_source",767,96,0},{"long_source",769,96,0},
        {"maximum_source_length",SIZE_MAX,96,0},
        {"short_output",768,95,0},{"long_output",768,97,0},
        {"maximum_output_length",768,SIZE_MAX,0},
        {"negative_weight",768,96,-1},{"excess_weight",768,96,257}
    };
    for (size_t i=0; i<sizeof(cases)/sizeof(cases[0]); ++i) {
        int status=hb_ccm_prepare(source,cases[i].input_length,4300,cases[i].weight,
                                  output+1,cases[i].output_length);
        check(cases[i].name,status==HB_CCM_INVALID_ARGUMENT &&
              intact(output,output_before,98) && intact(source,source_before,768));
    }
    check("null_source",hb_ccm_prepare(NULL,768,4300,128,output+1,96)==HB_CCM_INVALID_ARGUMENT && intact(output,output_before,98));
    check("null_output",hb_ccm_prepare(source,768,4300,128,NULL,96)==HB_CCM_INVALID_ARGUMENT && intact(source,source_before,768));
    source[767]=32768;
    check("positive_out_of_range",hb_ccm_prepare(source,768,4300,128,output+1,96)==HB_CCM_SOURCE_OUT_OF_RANGE && intact(output,output_before,98));
    source[767]=source_before[767];source[0]=-32769;
    check("negative_out_of_range",hb_ccm_prepare(source,768,4300,128,output+1,96)==HB_CCM_SOURCE_OUT_OF_RANGE && intact(output,output_before,98));
    memcpy(source,source_before,sizeof(source));
    struct { const char *name; int32_t cct; int weight; int expected_base; } valid[] = {
        {"minimum_int32_cct_clamp",INT32_MIN,0,-20000},
        {"maximum_int32_cct_clamp",INT32_MAX,256,15000},
        {"exact_cct_knot",3050,0,-15000},
        {"secondary_quarter_weight",3050,64,-10000},
        {"two_axis_midpoint",4300,128,-2500}
    };
    for (size_t i=0; i<sizeof(valid)/sizeof(valid[0]); ++i) {
        int status=hb_ccm_prepare(source,768,valid[i].cct,valid[i].weight,output+1,96);
        int passed=status==HB_CCM_OK && output[0]==output_before[0] && output[97]==output_before[97];
        for (int k=0; k<96; ++k) passed &= output[k+1]==valid[i].expected_base+k*7;
        check(valid[i].name,passed && intact(source,source_before,768));
    }
    const size_t offsets[]={0,48,672};
    const char *names[]={"exact_source_output_alias","partial_source_output_alias","last_profile_output_alias"};
    for (size_t i=0; i<3; ++i) {
        int32_t expected[768];
        memcpy(source,source_before,sizeof(source));
        memcpy(expected,source_before,sizeof(expected));
        for (int k=0; k<96; ++k) expected[offsets[i]+k]=-2500+k*7;
        int status=hb_ccm_prepare(source,768,4300,128,source+offsets[i],96);
        check(names[i],status==HB_CCM_OK && intact(source,expected,768));
    }
    return checked==20?0:2;
}
