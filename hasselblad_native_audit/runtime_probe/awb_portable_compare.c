/* SPDX-License-Identifier: MIT
 * Differential test in real Android/Bionic ABI: compiled portable C versus
 * the original hash-verified Hasselblad ARM64 routine. Synthetic inputs only.
 */
#include "hb_awb_recalib.h"
#include <dlfcn.h>
#include <inttypes.h>
#include <stdio.h>
#include <unistd.h>

static uint32_t seed = UINT32_C(0x20261019);
static uint32_t next_u32(void) {
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    setvbuf(stdout, NULL, _IONBF, 0);
    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!handle) { fprintf(stderr, "%s\n", dlerror()); return 2; }
    dlerror();
    hb_awb_original_recalib_fn original =
        (hb_awb_original_recalib_fn)dlsym(handle, HB_AWB_SYMBOL);
    const char *err = dlerror();
    if (err || !original) { fprintf(stderr, "%s\n", err ? err : "missing symbol"); return 3; }

    unsigned failures = 0;
    for (unsigned i = 0; i < 10000; ++i) {
        hb_awb_q12_pair input = {next_u32() & HB_AWB_MAX_SAFE_GAIN,
                                next_u32() & HB_AWB_MAX_SAFE_GAIN};
        hb_awb_q12_pair calib = {next_u32() | 1u, next_u32() | 1u};
        /* Interleave common Q12 calibration magnitudes with the full unsigned
         * divisor range so both large and fractional results are exercised. */
        if (i & 1u) { calib.a = (calib.a & 16383u) + 1u; calib.b = (calib.b & 16383u) + 1u; }
        hb_awb_recalib_result port = hb_awb_recalib_portable(input, calib);
        hb_awb_recalib_result native = hb_awb_recalib_original(original, input, calib);
        if (port.adapter_status != HB_AWB_OK || native.adapter_status != HB_AWB_OK ||
            !native.original_called || native.original_status != 0 ||
            port.output.a != native.output.a || port.output.b != native.output.b) {
            if (failures < 5) fprintf(stderr, "mismatch %u: %" PRIu32 ",%" PRIu32 "\n", i,input.a,input.b);
            ++failures;
        }
    }
    printf("{\"event\":\"android_portable_vs_original\",\"cases\":10000,\"failed\":%u,"
           "\"seed\":\"0x20261019\",\"firmware\":\"X2D II 1.3.16.2\","
           "\"full_awb_or_hncs_validated\":false}\n", failures);
    _exit(failures ? 1 : 0);
}
