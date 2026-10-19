/* Original research probe: bounded, read-only MAIN_GAMMA register metadata.
 * Requires the exact X2D II 1.3.16.2 librcam checked by the Python runner.
 * dlopen executes original initializers; no camera processing function runs.
 * This prints descriptors, never a photographic LUT or configuration payload.
 */
#define _GNU_SOURCE 1
#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static uintptr_t bias;

static void fail(const char *message) {
    fprintf(stderr, "%s\n", message);
    _exit(20);
}

static int inside(uintptr_t address, size_t bytes) {
    if (address < bias) return 0;
    uintptr_t value = address - bias;
    if (bytes > UINTPTR_MAX - value) return 0;
    return (value >= 0x2b000 && value + bytes <= 0x56e184) ||
           (value >= 0x580e20 && value + bytes <= 0x5b8608);
}

static uint64_t read64(uintptr_t address) {
    uint64_t value;
    if (!inside(address, sizeof(value))) fail("Metadata pointer outside audited ELF segments");
    memcpy(&value, (const void *)address, sizeof(value));
    return value;
}

static uint32_t read32(uintptr_t address) {
    uint32_t value;
    if (!inside(address, sizeof(value))) fail("Metadata word outside audited ELF segments");
    memcpy(&value, (const void *)address, sizeof(value));
    return value;
}

static void parameter(uintptr_t table, uintptr_t record, const char *kind,
                      uint32_t group, uint32_t index) {
    uintptr_t ids = read64(record);
    uint32_t count = read32(record + 8);
    if (count == 0 || count > 32) fail("Unexpected register-ID count");
    uintptr_t iq = read64(record + 16);
    uintptr_t module = read64(record + 32);
    if (!inside(iq, 4) || !inside(module, 4)) fail("Getter outside audited ELF segments");
    for (uint32_t field = 0; field < count; ++field) {
        uint32_t id = read32(ids + 4 * field);
        if (id > 8192) fail("Unexpected register ID");
        uintptr_t descriptor = table + 16 * (uintptr_t)id;
        printf("{\"event\":\"parameter\",\"kind\":\"%s\",\"group\":%u,"
               "\"index\":%u,\"field\":%u,\"field_count\":%u,"
               "\"record_va\":\"0x%" PRIxPTR "\",\"iq_getter_va\":\"0x%" PRIxPTR
               "\",\"module_getter_va\":\"0x%" PRIxPTR "\",\"register_id\":%u,"
               "\"descriptor_va\":\"0x%" PRIxPTR "\",\"word0\":%u,"
               "\"word1\":%u,\"word2\":%u,\"word3\":%u}\n",
               kind, group, index, field, count, record - bias, iq - bias,
               module - bias, id, descriptor - bias, read32(descriptor),
               read32(descriptor + 4), read32(descriptor + 8), read32(descriptor + 12));
    }
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    setvbuf(stdout, NULL, _IONBF, 0);
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
    void *anchor = dlsym(library, "dcam_isp_vreg_get_type");
    Dl_info info;
    if (!anchor || !dladdr(anchor, &info) || !info.dli_fname ||
        strcmp(info.dli_fname, argv[1]) != 0 || info.dli_saddr != anchor) return 3;
    bias = (uintptr_t)anchor - 0x54b88;
    uintptr_t table = read64(bias + 0x59e048);
    uintptr_t groups = read64(bias + 0x59e170);
    uint32_t group_count = read32(read64(bias + 0x59e168));
    if (group_count > 16) fail("Unexpected MAIN_GAMMA group count");
    printf("{\"event\":\"main_gamma_normal\",\"register_table_va\":\"0x%" PRIxPTR
           "\",\"groups_va\":\"0x%" PRIxPTR "\",\"group_count\":%u}\n",
           table - bias, groups - bias, group_count);
    for (uint32_t g = 0; g < group_count; ++g) {
        uintptr_t group = groups + 24 * g;
        uintptr_t records = read64(group);
        uint32_t count = read32(group + 8);
        if (count > 32) fail("Unexpected MAIN_GAMMA parameter count");
        printf("{\"event\":\"group\",\"index\":%u,\"records_va\":\"0x%" PRIxPTR
               "\",\"count\":%u,\"update_register_id\":%u}\n",
               g, records - bias, count, read32(group + 12));
        for (uint32_t i = 0; i < count; ++i)
            parameter(table, records + 48 * i, "vreg", g, i);
    }
    uint32_t count = read32(read64(bias + 0x59e178));
    uintptr_t extras = read64(bias + 0x59e180);
    if (count > 32) fail("Unexpected MAIN_GAMMA memory parameter count");
    for (uint32_t i = 0; i < count; ++i)
        parameter(table, extras + 48 * i, "memory", 0, i);
    /* _main_gamma_common_calc_mode names this table at 0x3a11ec/0x3a11f0
     * and bounds its group iteration by 2 at 0x3a1350. */
    groups = bias + 0x59ae60;
    for (uint32_t g = 0; g < 2; ++g) {
        uintptr_t group = groups + 24 * g;
        uintptr_t records = read64(group);
        count = read32(group + 8);
        if (count > 32) fail("Unexpected MAIN_GAMMA common parameter count");
        printf("{\"event\":\"common_group\",\"index\":%u,\"records_va\":\"0x%" PRIxPTR
               "\",\"count\":%u,\"update_register_id\":%u}\n",
               g, records - bias, count, read32(group + 12));
        for (uint32_t i = 0; i < count; ++i)
            parameter(table, records + 48 * i, "common_vreg", g, i);
    }
    _exit(0);
}
