/* Memory/undefined-behaviour checks through the real C API, run under sanitizers. */
#include "sharpen85.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
int main(void) {
    const size_t widths[] = {1, 2, 7, 8, 9, 33, 65};
    uint32_t seed = 85;
    for (size_t wi = 0; wi < sizeof(widths)/sizeof(widths[0]); ++wi) {
        size_t w = widths[wi], h = 71, n = w*h*3;
        uint16_t *in = malloc(n*sizeof(*in)), *out = malloc(n*sizeof(*out));
        assert(in && out);
        for (size_t i = 0; i < n; ++i) { seed = seed*1664525u+1013904223u; in[i]=(uint16_t)(seed%16384); }
        for (int amount = 0; amount <= 1000; amount += 100)
            for (int radius = 1; radius <= 8; ++radius) {
                assert(hb85_sharpen14(in,out,w,h,amount,(double)radius/2,0,10)==0);
                for (size_t i=0;i<n;++i) assert(out[i]<=16383);
            }
        assert(hb85_sharpen14(in,out,w,h,0,1,0,10)==0);
        assert(memcmp(in,out,n*sizeof(*in))==0);
        assert(hb85_sharpen14(in,in,w,h,1000,1,0,10)==0);
        assert(hb85_sharpen14(in,out,w,h,100,NAN,0,10)==-1);
        in[n-1]=16384;
        assert(hb85_sharpen14(in,out,w,h,100,1,0,10)==-1);
        free(out); free(in);
    }
    assert(hb85_sharpen14(NULL,NULL,0,0,100,1,0,10)==-1);
    return 0;
}
