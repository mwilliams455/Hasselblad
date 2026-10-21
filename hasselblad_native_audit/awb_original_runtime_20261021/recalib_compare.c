/* SPDX-License-Identifier: MIT
 * Runs original ARM64 and owned C in one Android/Bionic process.
 * All input vectors are synthetic. No photographic parity claim.
 */
#define _GNU_SOURCE
#include "hb_recalib_exact.h"
#include "hb_awb_recalib.h"
#include <dlfcn.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static uint32_t rng = UINT32_C(0x20261021);
static uint32_t next_u32(void) {
    rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng;
}
static uint32_t calls, failed, zero_cases, overflow_cases, alias_cases, safe_checks;
static uint64_t transcript = UINT64_C(14695981039346656037);
static void mix(uint32_t word) {
    for (unsigned i = 0; i < 4; ++i) {
        transcript ^= (word >> (i * 8)) & 255u;
        transcript *= UINT64_C(1099511628211);
    }
}
struct cells { uint32_t guard0, a, guard1, b, guard2; };

static void run_case(hb_awb_original_recalib_fn original, uint32_t a, uint32_t b,
                     uint32_t ca, uint32_t cb, int alias) {
    struct cells native = {0x13579bdf, a, 0xfdb97531, b, 0xa55a5aa5};
    struct cells owned = native;
    uint32_t status = original(&native.a, alias ? &native.a : &native.b, ca, cb);
    uint32_t expected = hb_recalib_exact(&owned.a, alias ? &owned.a : &owned.b, ca, cb);
    ++calls; zero_cases += (!ca || !cb); alias_cases += alias;
    overflow_cases += (ca && cb && (a > HB_AWB_MAX_SAFE_GAIN || (!alias && b > HB_AWB_MAX_SAFE_GAIN)));
    int ok = status == expected && memcmp(&native, &owned, sizeof native) == 0;
    /* Compare the unchanged production-safe portable core on its valid domain. */
    if (!alias && ca && cb && a <= HB_AWB_MAX_SAFE_GAIN && b <= HB_AWB_MAX_SAFE_GAIN) {
        hb_awb_recalib_result p = hb_awb_recalib_portable((hb_awb_q12_pair){a,b},
                                                       (hb_awb_q12_pair){ca,cb});
        ++safe_checks;
        ok &= p.adapter_status == HB_AWB_OK && !p.original_called &&
              p.output.a == native.a && p.output.b == native.b;
    }
    if (!ok) {
        if (failed < 8) fprintf(stderr, "mismatch at original call %u\n", calls);
        ++failed;
    }
    mix(a); mix(b); mix(ca); mix(cb); mix(alias); mix(status); mix(native.a); mix(native.b);
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    setvbuf(stdout, NULL, _IONBF, 0);
    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!handle) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
    dlerror();
    hb_awb_original_recalib_fn original = (hb_awb_original_recalib_fn)dlsym(handle, HB_AWB_SYMBOL);
    const char *error = dlerror();
    if (error || !original) { fprintf(stderr, "dlsym: %s\n", error ? error : "null"); return 3; }
    Dl_info info;
    if (!dladdr((void *)original, &info)) { fputs("dladdr failed\n",stderr); return 4; }
    /* This pinned ELF's first PT_LOAD has p_vaddr=0x1000, p_offset=0.
     * Bionic dladdr reports the mapped start, not the ELF load bias. */
    if ((uintptr_t)original - (uintptr_t)info.dli_fbase + 0x1000 != HB_AWB_SYMBOL_VA) {
        fprintf(stderr,"unexpected loaded offset: 0x%" PRIxPTR "\n",
                (uintptr_t)original - (uintptr_t)info.dli_fbase); return 4;
    }
    const uint32_t edge[] = {0,1,4095,4096,65535,1048575,1048576,0x7fffffff,0xffffffff};
    for (unsigned a=0;a<9;++a) for (unsigned b=0;b<9;++b)
      for (unsigned ca=0;ca<9;++ca) for (unsigned cb=0;cb<9;++cb)
        run_case(original,edge[a],edge[b],edge[ca],edge[cb],0);
    for (unsigned i=0;i<20000;++i) {
        uint32_t a=next_u32(), b=next_u32(), ca=next_u32()|1u, cb=next_u32()|1u;
        if (i<10000) { a &= HB_AWB_MAX_SAFE_GAIN; b &= HB_AWB_MAX_SAFE_GAIN; }
        if (i&1u) { ca=(ca&16383u)+1u; cb=(cb&16383u)+1u; }
        if (i>=10000 && i%11==0) ca=0;
        if (i>=10000 && i%13==0) cb=0;
        run_case(original,a,b,ca,cb,0);
    }
    for (unsigned i=0;i<1024;++i) {
        uint32_t a=next_u32(), ca=next_u32()|1u, cb=next_u32()|1u;
        if (i&1u) { a &= HB_AWB_MAX_SAFE_GAIN; ca=(ca&8191u)+1u; cb=(cb&8191u)+1u; }
        if (i%17==0) ca=0;
        run_case(original,a,0xabcdef01,ca,cb,1);
    }
    const uint32_t zeros[3][2] = {{0,4096},{4096,0},{0,0}};
    for (unsigned i=0;i<3;++i) {
        uint32_t status=original(NULL,NULL,zeros[i][0],zeros[i][1]);
        uint32_t expected=hb_recalib_exact(NULL,NULL,zeros[i][0],zeros[i][1]);
        ++calls; ++zero_cases; failed += status!=expected; mix(status);
    }
    printf("{\"event\":\"original_android28_recalib_comparison\",\"original_calls\":%u,"
           "\"failed\":%u,\"edge_grid_cases\":6561,\"random_cases\":20000,"
           "\"alias_cases\":%u,\"null_zero_cases\":3,\"zero_divisor_cases\":%u,"
           "\"input_overflow_cases\":%u,\"guarded_portable_valid_comparisons\":%u,"
           "\"seed\":\"0x20261021\",\"transcript_fnv1a64\":\"%016" PRIx64 "\","
           "\"original_symbol_offset\":\"0x4a39a0\",\"full_awb_validated\":false}\n",
           calls,failed,alias_cases,zero_cases,overflow_cases,safe_checks,transcript);
    _exit(failed ? 1 : 0);
}
