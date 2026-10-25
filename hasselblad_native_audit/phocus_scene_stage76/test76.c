#include "frame76.h"
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
int main(void) {
    const int widths[]={128,129,160,226,257,8192};
    for(unsigned t=0;t<sizeof widths/sizeof widths[0];t++) {
        int w=widths[t],cw=(w-64)&~1;size_t n=(size_t)cw*64*3;
        uint16_t *raw=malloc((size_t)w*128*2),*out=malloc((n+2)*2);assert(raw&&out);
        for(int i=0;i<w*128;i++)raw[i]=10000;
        out[0]=123;out[n+1]=456;
        assert(hb76_render_band(raw,(size_t)w*128,w,0,64,out+1,n)==0);
        for(size_t i=1;i<=n;i++)assert(out[i]==10000);
        assert(out[0]==123&&out[n+1]==456);
        assert(hb76_render_band(raw,(size_t)w*128,w,63,2,out+1,n)==-1);
        assert(hb76_render_band(raw,1,w,0,64,out+1,n)==-1);
        assert(hb76_render_band(raw,(size_t)w*128,w,0,64,out+1,n-1)==-1);
        assert(hb76_render_band(raw,(size_t)w*128,w,0,64,raw,n)==-1);
        assert(out[0]==123&&out[n+1]==456);free(raw);free(out);
    }
    puts("STAGE76_C_BOUNDS_ASAN_UBSAN_PASS");return 0;
}
