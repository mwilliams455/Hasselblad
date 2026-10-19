/* SPDX-License-Identifier: MIT
 * Executes the original X2D II 1.3.16.2 libaaa scene_awb_result_recalib_unit.
 * ABI established from its 56-byte leaf and real callers in the same ELF.
 * Only synthetic, owned 4-byte gain cells are passed; no camera is accessed.
 */
#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

typedef uint32_t (*recalib_fn)(uint32_t *, uint32_t *, uint32_t, uint32_t);
struct vector { uint32_t a, b, ca, cb; };

static int run_case(recalib_fn fn, unsigned index, struct vector in) {
    struct guarded { uint32_t before, gain, after; } a = {0xa17e93c4, in.a, 0x47ab298c},
                                                   b = {0xb193da42, in.b, 0x9358feca};
    uint32_t status = fn(&a.gain, &b.gain, in.ca, in.cb);
    uint32_t expected_status = (!in.ca || !in.cb) ? 89u : 0u;
    uint32_t expected_a = expected_status ? in.a : (uint32_t)(((uint64_t)in.a * 4096u) / in.ca);
    uint32_t expected_b = expected_status ? in.b : (uint32_t)(((uint64_t)in.b * 4096u) / in.cb);
    int guard_ok = a.before == 0xa17e93c4 && a.after == 0x47ab298c &&
                   b.before == 0xb193da42 && b.after == 0x9358feca;
    int passed = status == expected_status && a.gain == expected_a &&
                 b.gain == expected_b && guard_ok;
    printf("{\"case\":%u,\"input\":[%" PRIu32 ",%" PRIu32 "],\"calibration\":[%" PRIu32 ",%" PRIu32
           "],\"output\":[%" PRIu32 ",%" PRIu32 "],\"status\":%" PRIu32 ",\"guard_ok\":%s,\"passed\":%s}\n",
           index, in.a, in.b, in.ca, in.cb, a.gain, b.gain, status,
           guard_ok ? "true" : "false", passed ? "true" : "false");
    return passed;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fputs("usage: awb_recalib_probe HASH_VERIFIED_LIBAAA_PATH\n", stderr);
        return 64;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
    dlerror();
    recalib_fn fn = (recalib_fn)dlsym(library, "scene_awb_result_recalib_unit");
    const char *error = dlerror();
    if (error || !fn) { fprintf(stderr, "dlsym: %s\n", error ? error : "null symbol"); return 3; }
    const struct vector cases[] = {
        {4096,4096,4096,4096}, {8192,2048,4096,4096},
        {5001,3333,3072,5120}, {65535,65535,65535,1},
        {0,0,4096,4096}, {1,4095,8192,65535},
        {4096,8192,0,4096}, {8192,4096,4096,0}, {1234,5678,0,0}
    };
    unsigned failed = 0;
    for (unsigned i=0; i<sizeof(cases)/sizeof(cases[0]); ++i) failed += !run_case(fn,i,cases[i]);
    printf("{\"event\":\"original_hasselblad_routine_executed\",\"cases\":%zu,\"failed\":%u,"
           "\"full_awb_or_hncs_validated\":false}\n", sizeof(cases)/sizeof(cases[0]), failed);
    _exit(failed ? 1 : 0);
}
