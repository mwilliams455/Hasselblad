/* SPDX-License-Identifier: MIT
 * Offline Android/Bionic compatibility probe. Does not call camera functions.
 * dlopen executes library initializers; run this in a disposable bounded process.
 */
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>

static void json_string(const char *s) {
    putchar('"');
    if (s) {
        for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
            if (*p == '"' || *p == '\\') printf("\\%c", *p);
            else if (*p < 0x20) printf("\\u%04x", (unsigned)*p);
            else putchar(*p);
        }
    }
    putchar('"');
}

int main(int argc, char **argv) {
    if (argc < 2 || argc > 3) {
        fputs("usage: load_probe LIBRARY [SYMBOL_TO_RESOLVE_ONLY]\n", stderr);
        return 64;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("{\"event\":\"probe_start\",\"pointer_bits\":%zu,\"page_size\":%ld,\"library\":",
           sizeof(void *) * 8, sysconf(_SC_PAGESIZE));
    json_string(argv[1]);
    puts("}");
    dlerror();
    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        const char *err = dlerror();
        fputs("{\"event\":\"load_failed\",\"error\":", stdout);
        json_string(err ? err : "dlopen returned null without dlerror");
        puts("}");
        return 2;
    }
    puts("{\"event\":\"library_loaded\",\"photographic_routine_executed\":false}");
    if (argc == 3) {
        dlerror();
        void *symbol = dlsym(handle, argv[2]);
        const char *error = dlerror();
        fputs("{\"event\":\"symbol_lookup\",\"symbol\":", stdout);
        json_string(argv[2]);
        printf(",\"found\":%s,\"invoked\":false,\"error\":", (!error && symbol) ? "true" : "false");
        json_string(error ? error : "");
        puts("}");
        if (error || !symbol) return 3;
    }
    /* Process teardown owns cleanup. Avoid calling unknown library destructors
     * separately or mistaking successful lookup for a proven calling ABI. */
    _exit(0);
}
