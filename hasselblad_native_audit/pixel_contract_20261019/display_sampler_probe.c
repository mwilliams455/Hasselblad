/* Bounded synthetic tests of three exact, exported X2D II display-HAL helpers.
 * This does not establish that the camera MAIN_3DLUT uses this format.
 * Original vendor code is loaded at run time and is not included here.
 */
#define _GNU_SOURCE 1
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

enum { WIDTH = 16, WORDS = 6144, TABLE_BYTES = WORDS * 4 };
typedef struct { double r, g, b; } PixelRGB;
_Static_assert(sizeof(PixelRGB) == 24, "PixelRGB ABI");
_Static_assert(sizeof(size_t) == 8, "ARM64 size_t ABI");
typedef PixelRGB *(*lookup_fn)(const void *, const size_t *, const size_t *,
                               const size_t *, PixelRGB *);
typedef int (*transform_fn)(PixelRGB *, const int32_t *, lookup_fn,
                            const void *, size_t);
typedef int (*identity_fn)(void *, const size_t *);
typedef struct { uint64_t before[2]; PixelRGB pixel; uint64_t after[2]; } GuardedPixel;
static const uint64_t SENTINEL = UINT64_C(0xd63281ba975ec04f);

static void fail(const char *why) { fprintf(stderr, "%s\n", why); exit(2); }
static void reset_pixel(GuardedPixel *p, PixelRGB value) {
    p->before[0] = p->before[1] = p->after[0] = p->after[1] = SENTINEL;
    p->pixel = value;
}
static int guarded(const GuardedPixel *p) {
    return p->before[0] == SENTINEL && p->before[1] == SENTINEL &&
           p->after[0] == SENTINEL && p->after[1] == SENTINEL;
}
static double max3diff(PixelRGB a, PixelRGB b) {
    return fmax(fabs(a.r-b.r), fmax(fabs(a.g-b.g), fabs(a.b-b.b)));
}
static int finite_pixel(PixelRGB p) {
    return isfinite(p.r) && isfinite(p.g) && isfinite(p.b);
}
static uint32_t component(unsigned channel, unsigned r, unsigned g, unsigned b) {
    switch (channel) {
    case 0: return (127*r + 37*g + 19*b + 53) & 4095;
    case 1: return (61*r + 83*g + 109*b + 311) & 4095;
    default: return (13*r*r + 17*g + 7*b*b + 911) & 4095;
    }
}
static PixelRGB analytic_node(unsigned r, unsigned g, unsigned b) {
    PixelRGB p = {component(0,r,g,b)/4095.0,
                  component(1,r,g,b)/4095.0,
                  component(2,r,g,b)/4095.0};
    return p;
}
static PixelRGB reference(PixelRGB p) {
    double pos[3] = {p.r*15.0, p.g*15.0, p.b*15.0};
    unsigned lo[3], hi[3]; double f[3];
    for (unsigned i=0;i<3;i++) {
        lo[i]=(unsigned)floor(pos[i]);
        hi[i]=lo[i]<15?lo[i]+1:15;
        f[i]=pos[i]-lo[i];
    }
    PixelRGB out={0,0,0};
    for (unsigned rr=0;rr<2;rr++) for (unsigned gg=0;gg<2;gg++)
        for (unsigned bb=0;bb<2;bb++) {
            double w=(rr?f[0]:1-f[0])*(gg?f[1]:1-f[1])*(bb?f[2]:1-f[2]);
            PixelRGB n=analytic_node(rr?hi[0]:lo[0],gg?hi[1]:lo[1],bb?hi[2]:lo[2]);
            out.r+=w*n.r; out.g+=w*n.g; out.b+=w*n.b;
        }
    return out;
}
static void *symbol(void *h, const char *path, const char *name, uintptr_t va, void **base) {
    dlerror(); void *p=dlsym(h,name); const char *e=dlerror();
    if (e || !p) fail(e?e:"dlsym null");
    Dl_info i={0};
    /* This exact ELF's first PT_LOAD starts at VA 0x2000. Bionic reports
     * the first mapped address, rather than the zero-VA load bias. */
    if (!dladdr(p,&i) || !i.dli_fbase || !i.dli_fname || strcmp(i.dli_fname,path) ||
        i.dli_saddr!=p || (uintptr_t)p-(uintptr_t)i.dli_fbase+0x2000!=va)
        fail("Resolved export did not have the expected ELF virtual address");
    if (*base && *base!=i.dli_fbase) fail("Exports resolved to different libraries");
    *base=i.dli_fbase; return p;
}

int main(int argc, char **argv) {
    if (argc!=2) fail("Expected exact libduml_hal.so pathname");
    if (sysconf(_SC_PAGESIZE)!=4096) fail("Guard mapping expects 4096-byte pages");
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if (!h) fail(dlerror());
    void *base=NULL;
    lookup_fn lookup=(lookup_fn)symbol(h,argv[1],"_Z24lookup_rgb_pixel_plt_fmtPKvRKmS2_S2_R8PixelRGB",0x74fb0,&base);
    transform_fn trans=(transform_fn)symbol(h,argv[1],"_Z14do_3dlut_transR8PixelRGBRKiPFS0_PKvRKmS6_S6_S0_ES4_m",0x72dc0,&base);
    identity_fn identity=(identity_fn)symbol(h,argv[1],"_Z22get_plt_fmt_unit_3dlutPvRKm",0x74e50,&base);
    uint8_t *mapping=mmap(NULL,TABLE_BYTES+8192,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if (mapping==MAP_FAILED) fail("mmap");
    uint32_t *table=(uint32_t *)(mapping+4096);
    if (mprotect(table,TABLE_BYTES,PROT_READ|PROT_WRITE)) fail("mprotect RW");
    /* Nonzero reserved high nibbles test the original 12-bit masking. */
    for (unsigned i=0;i<WORDS;i++) table[i]=UINT32_C(0xa0005000);
    for (unsigned r=0;r<16;r++) for (unsigned g=0;g<16;g++) for (unsigned b=0;b<16;b++) {
        unsigned q=128*r+8*g+b/2, shift=(b&1)*16;
        for (unsigned ch=0;ch<3;ch++) table[q+2048*ch]|=component(ch,r,g,b)<<shift;
    }
    uint32_t *saved=malloc(TABLE_BYTES);
    if (!saved) fail("malloc");
    memcpy(saved,table,TABLE_BYTES);
    if (mprotect(table,TABLE_BYTES,PROT_READ)) fail("mprotect read-only source");
    double lookup_error=0;
    for (size_t r=0;r<16;r++) for (size_t g=0;g<16;g++) for (size_t b=0;b<16;b++) {
        GuardedPixel out; reset_pixel(&out,(PixelRGB){-1,-1,-1});
        PixelRGB *ret=lookup(table,&b,&g,&r,&out.pixel);
        double error=max3diff(out.pixel,analytic_node((unsigned)r,(unsigned)g,(unsigned)b));
        if (ret!=&out.pixel || !guarded(&out) || !finite_pixel(out.pixel) || !isfinite(error) || error>1e-15)
            fail("Original lookup differs from analytic node or violated output guard");
        lookup_error=fmax(lookup_error,error);
    }
    printf("{\"test\":\"synthetic_lookup_all_nodes\",\"nodes\":4096,\"components\":12288,\"index_min\":0,\"index_max\":15,\"max_abs_error\":%.17g,\"output_guards\":true,\"return_pointer\":true,\"reserved_bits_masked\":true}\n",lookup_error);
    static const PixelRGB cases[] = {
        {0,0,0},{1,1,1},{1,0,0},{0,1,0},{0,0,1},{1,1,0},{1,0,1},{0,1,1},
        {1.0/15.0,7.0/15.0,14.0/15.0},{14.0/15.0,2.0/15.0,1.0/15.0},
        {0.123,0.456,0.789},{0.876,0.234,0.567},{0.5,0.5,0.5},
        {0.999999999,0.999999997,0.999999991},{0.000000001,0.000000003,0.000000009},
        {0.067,0.134,0.201},{0.934,0.867,0.799},{1,0.345,0.678},{0.123,1,0.789},{0.123,0.456,1}
    };
    const int32_t scale=1;
    double max_error=0;
    for (unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
        GuardedPixel out; reset_pixel(&out,cases[i]);
        PixelRGB expected=reference(cases[i]);
        int ret=trans(&out.pixel,&scale,lookup,table,WIDTH);
        double error=max3diff(out.pixel,expected);
        if (ret || !guarded(&out) || !finite_pixel(out.pixel) || !isfinite(error) || error>1e-12)
            fail("Original trilinear sampler mismatch, nonzero status, or output guard violation");
        max_error=fmax(max_error,error);
        printf("{\"test\":\"synthetic_trilinear_case\",\"case\":%u,\"input\":[%.17g,%.17g,%.17g],\"output\":[%.17g,%.17g,%.17g],\"max_abs_error\":%.17g,\"return_code\":%d,\"output_guards\":true}\n",i,cases[i].r,cases[i].g,cases[i].b,out.pixel.r,out.pixel.g,out.pixel.b,error,ret);
    }
    if (memcmp(saved,table,TABLE_BYTES)) fail("Synthetic source changed");
    printf("{\"test\":\"synthetic_trilinear_summary\",\"cases\":%zu,\"max_abs_error\":%.17g,\"source_unchanged\":true,\"source_read_only\":true,\"source_guard_pages\":true,\"original_lookup_callback\":true,\"scale\":1,\"cube_width\":16}\n",sizeof(cases)/sizeof(cases[0]),max_error);
    /* A separate original identity generator confirms axis/component pairing;
     * its 12-bit quantization is checked rather than assumed to be lossless. */
    if (mprotect(table,TABLE_BYTES,PROT_READ|PROT_WRITE)) fail("mprotect identity RW");
    memset(table,0,TABLE_BYTES);
    const size_t width=16;
    if (identity(table,&width)) fail("Original identity generator status");
    if (mprotect(table,TABLE_BYTES,PROT_READ)) fail("mprotect identity read-only");
    double identity_error=0;
    for (size_t r=0;r<16;r++) for (size_t g=0;g<16;g++) for (size_t b=0;b<16;b++) {
        GuardedPixel out; reset_pixel(&out,(PixelRGB){-1,-1,-1});
        PixelRGB *ret=lookup(table,&b,&g,&r,&out.pixel);
        PixelRGB expected={(uint32_t)((double)r/15.0*4095.0)/4095.0,
                           (uint32_t)((double)g/15.0*4095.0)/4095.0,
                           (uint32_t)((double)b/15.0*4095.0)/4095.0};
        double error=max3diff(out.pixel,expected);
        if (ret!=&out.pixel || !guarded(&out) || !finite_pixel(out.pixel) || !isfinite(error) || error>1e-15)
            fail("Original identity generator/lookup axis or component mismatch");
        identity_error=fmax(identity_error,error);
    }
    printf("{\"test\":\"original_identity_axis_control\",\"nodes\":4096,\"components\":12288,\"max_abs_error\":%.17g,\"guard_pages\":true,\"output_guards\":true,\"quantization_checked\":true}\n",identity_error);
    free(saved); munmap(mapping,TABLE_BYTES+8192); dlclose(h);
    return 0;
}
