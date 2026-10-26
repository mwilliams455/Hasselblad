#include "frame96.h"
#include "../phocus_speed_stage77/frame77.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    const int widths[]={128,130,318,320,322,642,4096};
    for(size_t k=0;k<sizeof(widths)/sizeof(widths[0]);k++) {
        int w=widths[k];size_t in=(size_t)w*128,n=(size_t)((w-64)&~1)*64*3;
        uint16_t *raw=malloc(in*2),*copy=malloc(in*2),*old=malloc(n*2),*a=malloc(n*2),*b=malloc(n*2);
        assert(raw&&copy&&old&&a&&b);
        for(size_t i=0;i<in;i++)raw[i]=(uint16_t)((i*331+(i/w)*197)^((i*31)>>7));
        memcpy(copy,raw,in*2);
        assert(!hb77_render_band(raw,in,w,0,64,4,old,n));
        assert(!hb96_render_band(raw,in,w,0,64,1,a,n,1,1));
        assert(!memcmp(old,a,n*2));
        assert(!hb96_render_band(raw,in,w,0,64,1,a,n,.315,.678));
        assert(!hb96_render_band(raw,in,w,0,64,4,b,n,.315,.678));
        assert(!memcmp(a,b,n*2));assert(!memcmp(copy,raw,in*2));
        size_t row=(size_t)((w-64)&~1)*3;
        assert(!hb96_render_band(raw,in,w,62,2,3,b,row*2,.315,.678));
        assert(!memcmp(a+62*row,b,row*2*2));
        const double bad[]={0,-1,NAN,INFINITY,1.0/32,32};
        for(size_t i=0;i<sizeof(bad)/sizeof(bad[0]);i++) {
            memcpy(b,old,n*2);
            assert(hb96_render_band(raw,in,w,0,64,4,b,n,bad[i],1)==-2);
            assert(!memcmp(b,old,n*2));
            assert(hb96_render_band(raw,in,w,0,64,4,b,n,1,bad[i])==-2);
        }
        assert(hb96_render_band(raw,in-1,w,0,64,4,b,n,1,1)==-1);
        assert(hb96_render_band(raw,in,w,0,64,4,b,n-1,1,1)==-1);
        assert(hb96_render_band(raw,in,w,0,64,0,b,n,1,1)==-1);
        assert(hb96_render_band(raw,in,w,63,2,1,b,n,1,1)==-1);
        assert(hb96_render_band(raw,in,w,0,64,1,raw,n,1,1)==-1);
        assert(!hb96_render_band(raw,in,w,0,64,4,b,n,.0625,16));
        free(raw);free(copy);free(old);free(a);free(b);
    }
    puts("PASS native unit-neutral parity, workers, tails, immutable input/output, metadata bounds and capacity checks");
}
