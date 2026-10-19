/* SPDX-License-Identifier: MIT
 * Original research harness. No vendor implementation or IQ table is bundled.
 * Run only with the hash-verified X2D II 1.3.16.2 librcam.so and its matching
 * Android/Bionic runtime. This proves a profile preparation helper, not a
 * per-pixel colour renderer. Local function addresses are specific to that ELF.
 */
#define _GNU_SOURCE 1
#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define PROFILE_WORDS 7
#define PROFILE_COUNT 8
#define ANCHOR_VA UINT64_C(0x54b88)
#define MIX_VA UINT64_C(0x2bbc08)
#define COEFF_VA UINT64_C(0x2bac00)

struct coefficient { uint32_t index; int32_t fraction_q8; };
typedef uint32_t *(*mix_fn)(const uint32_t *, uint32_t,
                           const struct coefficient *, const uint32_t *,
                           uint32_t, uint32_t *);
typedef uint64_t (*coeff_fn)(const int32_t *, uint64_t, int32_t);

static uint32_t pack(int32_t low, int32_t high) {
    return (uint32_t)(uint16_t)low | ((uint32_t)(uint16_t)high << 16);
}

/* floor division, matching AArch64 ASR without relying on host signed shifts. */
static int32_t blend(int32_t a, int32_t b, int32_t q8) {
    int64_t product = (int64_t)(b - a) * q8;
    int32_t delta = product < 0 ? -(int32_t)((-product + 255) / 256)
                                : (int32_t)(product / 256);
    return a + delta;
}

static int32_t component(uint32_t word, unsigned half) {
    uint32_t bits = (word >> (half * 16)) & UINT32_C(0xffff);
    return bits >= 32768 ? (int32_t)bits - 65536 : (int32_t)bits;
}

static struct coefficient unpack_coeff(uint64_t value) {
    struct coefficient c = {(uint32_t)value, (int32_t)(value >> 32)};
    return c;
}

static struct coefficient expected_coeff(const int32_t *axis, unsigned n, int32_t value) {
    struct coefficient c = {0, 0};
    if (value < axis[0]) return c;
    if (value >= axis[n-1]) { c.index = n-2; c.fraction_q8 = 256; return c; }
    for (unsigned i = 0; i+1 < n; ++i) {
        if (axis[i] <= value && value < axis[i+1]) {
            c.index = i;
            c.fraction_q8 = (int32_t)(((int64_t)value-axis[i])*256/(axis[i+1]-axis[i]));
            return c;
        }
    }
    return c;
}

static int run_case(mix_fn mix, coeff_fn coefficient, unsigned case_id,
                    int32_t cct, int32_t gamut, const uint32_t *source) {
    const int32_t cct_axis[4] = {2400,3050,5550,9100};
    const int32_t gamut_axis[2] = {0,1};
    const uint32_t strides[2] = {4,8};
    struct coefficient coefficients[2] = {
        unpack_coeff(coefficient(cct_axis,4,cct)),
        unpack_coeff(coefficient(gamut_axis,2,gamut))
    };
    struct coefficient expect_coefficients[2] = {
        expected_coeff(cct_axis,4,cct),expected_coeff(gamut_axis,2,gamut)
    };
    uint32_t source_before[PROFILE_COUNT*PROFILE_WORDS];
    memcpy(source_before,source,sizeof(source_before));
    struct guarded { uint32_t before[4], words[PROFILE_WORDS], after[4]; } output;
    memset(&output,0xa5,sizeof(output));
    uint32_t *returned = mix(source,PROFILE_WORDS,coefficients,strides,2,output.words);
    unsigned failed_words = 0;
    for (unsigned j=0; j<PROFILE_WORDS; ++j) {
        int32_t result[2];
        for (unsigned half=0; half<2; ++half) {
            unsigned c = coefficients[0].index;
            int32_t a = blend(component(source[(c+0)*PROFILE_WORDS+j],half),
                              component(source[(c+1)*PROFILE_WORDS+j],half),
                              coefficients[0].fraction_q8);
            int32_t b = blend(component(source[(c+4)*PROFILE_WORDS+j],half),
                              component(source[(c+5)*PROFILE_WORDS+j],half),
                              coefficients[0].fraction_q8);
            result[half] = blend(a,b,coefficients[1].fraction_q8);
        }
        failed_words += output.words[j] != pack(result[0],result[1]);
    }
    int guards_ok = 1;
    for (unsigned j=0; j<4; ++j) guards_ok &= output.before[j] == UINT32_C(0xa5a5a5a5)
                                            && output.after[j] == UINT32_C(0xa5a5a5a5);
    int source_ok = !memcmp(source_before,source,sizeof(source_before));
    int coeff_ok = !memcmp(coefficients,expect_coefficients,sizeof(coefficients));
    int passed = !failed_words && guards_ok && source_ok && coeff_ok
                 && returned == output.words+PROFILE_WORDS;
    printf("{\"case\":%u,\"cct\":%" PRId32 ",\"gamut\":%" PRId32
           ",\"coefficients\":[[%" PRIu32 ",%" PRId32 "],[%" PRIu32 ",%" PRId32
           "]],\"output\":[",case_id,cct,gamut,coefficients[0].index,
           coefficients[0].fraction_q8,coefficients[1].index,coefficients[1].fraction_q8);
    for (unsigned j=0; j<PROFILE_WORDS; ++j) printf("%s%" PRIu32,j?",":"",output.words[j]);
    printf("],\"failed_words\":%u,\"guards_ok\":%s,\"source_unchanged\":%s,"
           "\"coefficient_matches\":%s,\"returned_destination_end\":%s,\"passed\":%s}\n",
           failed_words,guards_ok?"true":"false",source_ok?"true":"false",
           coeff_ok?"true":"false",returned == output.words+PROFILE_WORDS?"true":"false",
           passed?"true":"false");
    return passed;
}

static int run_real_profiles(mix_fn mix, coeff_fn coefficient,
                             const char *input_path, const char *output_path) {
    const unsigned words = 6144, source_words = 49152;
    const int32_t cct_axis[4] = {2400,3050,5550,9100};
    const int32_t gamut_axis[2] = {0,1};
    const uint32_t strides[2] = {4,8};
    const int32_t cases[][2] = {
        {2400,0},{2400,1},{4300,0},{4300,1},{5550,0},
        {5550,1},{7001,0},{7001,1},{9100,0},{9100,1}
    };
    uint32_t *source = malloc(source_words*sizeof(uint32_t));
    uint32_t *source_before = malloc(source_words*sizeof(uint32_t));
    uint32_t *guarded = malloc((words+8)*sizeof(uint32_t));
    if (!source || !source_before || !guarded) return 10;
    FILE *input = fopen(input_path,"rb");
    if (!input) { perror("input"); return 11; }
    if (fread(source,sizeof(uint32_t),source_words,input)!=source_words || fgetc(input)!=EOF) {
        fputs("real fixture must contain exactly 49152 little-endian words\n",stderr); return 12;
    }
    fclose(input);
    memcpy(source_before,source,source_words*sizeof(uint32_t));
    FILE *output = fopen(output_path,"wb");
    if (!output) { perror("output"); return 13; }
    unsigned failed=0;
    for (unsigned k=0;k<sizeof(cases)/sizeof(cases[0]);++k) {
        int32_t cct=cases[k][0],gamut=cases[k][1];
        struct coefficient coefficients[2]={unpack_coeff(coefficient(cct_axis,4,cct)),
                                             unpack_coeff(coefficient(gamut_axis,2,gamut))};
        struct coefficient expected[2]={expected_coeff(cct_axis,4,cct),
                                         expected_coeff(gamut_axis,2,gamut)};
        memset(guarded,0xa5,(words+8)*sizeof(uint32_t));
        uint32_t *destination=guarded+4;
        uint32_t *returned=mix(source,words,coefficients,strides,2,destination);
        unsigned failed_lanes=0;
        for (unsigned j=0;j<words;++j) {
            for (unsigned half=0;half<2;++half) {
                unsigned c=expected[0].index;
                int32_t a=blend(component(source_before[(c+0)*words+j],half),
                                component(source_before[(c+1)*words+j],half),expected[0].fraction_q8);
                int32_t b=blend(component(source_before[(c+4)*words+j],half),
                                component(source_before[(c+5)*words+j],half),expected[0].fraction_q8);
                int32_t reference=blend(a,b,expected[1].fraction_q8);
                failed_lanes += component(destination[j],half) != reference;
            }
        }
        int guards_ok=1;
        for (unsigned j=0;j<4;++j)
            guards_ok &= guarded[j]==UINT32_C(0xa5a5a5a5)
                         && guarded[4+words+j]==UINT32_C(0xa5a5a5a5);
        int source_ok=!memcmp(source,source_before,source_words*sizeof(uint32_t));
        int coeff_ok=!memcmp(coefficients,expected,sizeof(coefficients));
        int returned_ok=returned==destination+words;
        int passed=!failed_lanes && guards_ok && source_ok && coeff_ok && returned_ok;
        failed += !passed;
        if (fwrite(destination,sizeof(uint32_t),words,output)!=words) return 14;
        printf("{\"case\":%u,\"fixture\":\"original_camera_lut\",\"cct\":%" PRId32
               ",\"gamut\":%" PRId32 ",\"coefficients\":[[%" PRIu32 ",%" PRId32
               "],[%" PRIu32 ",%" PRId32 "]],\"output_words\":%u,\"output_lanes\":%u,"
               "\"failed_lanes\":%u,\"guards_ok\":%s,\"source_unchanged\":%s,"
               "\"coefficient_matches\":%s,\"returned_destination_end\":%s,\"passed\":%s}\n",
               k,cct,gamut,coefficients[0].index,coefficients[0].fraction_q8,
               coefficients[1].index,coefficients[1].fraction_q8,words,words*2,failed_lanes,
               guards_ok?"true":"false",source_ok?"true":"false",coeff_ok?"true":"false",
               returned_ok?"true":"false",passed?"true":"false");
    }
    if (fclose(output)) return 15;
    free(source);free(source_before);free(guarded);
    printf("{\"event\":\"original_camera_profiles_prepared\",\"cases\":%zu,\"failed\":%u,"
           "\"source_words\":%u,\"words_per_profile\":%u,\"profiles\":8,"
           "\"photographic_lut_values_used\":true,\"per_pixel_renderer_validated\":false}\n",
           sizeof(cases)/sizeof(cases[0]),failed,source_words,words);
    return failed?1:0;
}

int main(int argc, char **argv) {
    if (argc != 2 && argc != 4) {
        fputs("usage: lut_profile_probe EXACT_HASH_LIBRCAM_PATH [EXACT_CAMERA_LUT_WORDS TEMPORARY_PROFILE_OUTPUT]\n",stderr);
        return 64;
    }
    setvbuf(stdout,NULL,_IONBF,0);
    void *handle = dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if (!handle) { fprintf(stderr,"dlopen: %s\n",dlerror()); return 2; }
    /* Use the delta from an exact defined export, avoiding assumptions about
     * load bias for this ELF's nonzero first PT_LOAD virtual address. */
    dlerror();
    void *anchor = dlsym(handle,"dcam_isp_vreg_get_type");
    const char *error = dlerror();
    if (!anchor || error) { fprintf(stderr,"dlsym: %s\n",error?error:"null"); return 3; }
    Dl_info identity;
    if (!dladdr(anchor,&identity) || !identity.dli_fname ||
        strcmp(identity.dli_fname,argv[1]) || identity.dli_saddr != anchor ||
        !identity.dli_sname || strcmp(identity.dli_sname,"dcam_isp_vreg_get_type")) {
        fputs("resolved export does not belong to the requested library\n",stderr);
        return 4;
    }
    uintptr_t bias = (uintptr_t)anchor - ANCHOR_VA;
    /* rcam_adj_calc_common indexes this relocated table. The exact firmware
     * schema assigns calc::lerp_lut_mem_3d the value 37. Read, do not invoke,
     * the selected wrapper to verify the static config-to-function connection. */
    const uintptr_t *dispatch = (const uintptr_t *)(bias+UINT64_C(0x59c240));
    int dispatch_ok = dispatch[37] == bias+UINT64_C(0x3b8c78);
    printf("{\"event\":\"calc_dispatch_read\",\"table_va\":\"0x59c240\","
           "\"index\":37,\"target_va\":\"0x%" PRIxPTR "\",\"matches\":%s}\n",
           dispatch[37]-bias,dispatch_ok?"true":"false");
    if (!dispatch_ok) { fputs("unexpected calc dispatch target\n",stderr); return 5; }
    mix_fn mix = (mix_fn)(bias+MIX_VA);
    coeff_fn coefficient = (coeff_fn)(bias+COEFF_VA);
    if (argc==4) _exit(run_real_profiles(mix,coefficient,argv[2],argv[3]));
    uint32_t source[PROFILE_COUNT*PROFILE_WORDS];
    for (unsigned p=0; p<PROFILE_COUNT; ++p) {
        for (unsigned j=0; j<PROFILE_WORDS; ++j) {
            /* Synthetic, deliberately asymmetric and signed; no camera LUT. */
            int32_t low = (int32_t)((p*7171+j*2339+137)%60001)-30000;
            int32_t high = 30000-(int32_t)((p*4813+j*3251+977)%60001);
            source[p*PROFILE_WORDS+j] = pack(low,high);
        }
    }
    const int32_t cases[][2] = {
        {1000,0},{2400,0},{2725,0},{3001,1},{3050,1},{4300,0},
        {5550,1},{7001,0},{9099,1},{9100,1},{14000,0},{14000,1}
    };
    unsigned failed = 0;
    for (unsigned i=0; i<sizeof(cases)/sizeof(cases[0]); ++i)
        failed += !run_case(mix,coefficient,i,cases[i][0],cases[i][1],source);
    printf("{\"event\":\"original_profile_lut_helpers_executed\",\"cases\":%zu,"
           "\"failed\":%u,\"words_per_profile\":%u,\"profiles\":%u,"
           "\"photographic_lut_values_used\":false,\"per_pixel_renderer_validated\":false}\n",
           sizeof(cases)/sizeof(cases[0]),failed,PROFILE_WORDS,PROFILE_COUNT);
    _exit(failed?1:0);
}
