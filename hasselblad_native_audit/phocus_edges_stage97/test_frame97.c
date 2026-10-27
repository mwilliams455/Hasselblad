#include "frame97.h"
#include "chroma97.h"
#include "../phocus_chroma_stage96/frame96.h"
#include "../phocus_speed_stage77/frame77.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    uint16_t roi[8*8*3],corrected[4*4*3];
    for(int y=0;y<8;y++)for(int x=0;x<8;x++)for(int c=0;c<3;c++)
        roi[(y*8+x)*3+c]=(x+y)%2?30000:7000;
    roi[(4*8+4)*3]=roi[(4*8+4)*3+2]=16000;roi[(4*8+4)*3+1]=14000;
    assert(!hb97_chroma_roi(roi,8*8*3,8,8,1,1,corrected,4*4*3));
    assert(corrected[(2*4+2)*3]==15850&&corrected[(2*4+2)*3+1]==14150&&corrected[(2*4+2)*3+2]==15850);
    roi[(5*8+5)*3+1]=65535;
    assert(!hb97_chroma_roi(roi,8*8*3,8,8,1,1,corrected,4*4*3));
    assert(!memcmp(corrected+(2*4+2)*3,roi+(4*8+4)*3,6));
    memset(corrected,0x11,sizeof(corrected));
    assert(hb97_chroma_roi(roi,8*8*3,8,8,1,1,corrected,4*4*3-1)==-1);
    for(size_t i=0;i<4*4*3;i++)assert(corrected[i]==0x1111);
    const int widths[]={128,130,318,320,322,642,4096};
    for(size_t k=0;k<sizeof(widths)/sizeof(widths[0]);k++) {
        int w=widths[k];size_t in=(size_t)w*128,n=(size_t)((w-64)&~1)*64*3;
        uint16_t *raw=malloc(in*2),*copy=malloc(in*2),*old=malloc(n*2),*a=malloc(n*2),*b=malloc(n*2);
        assert(raw&&copy&&old&&a&&b);
        for(size_t i=0;i<in;i++)raw[i]=(uint16_t)((i*331+(i/w)*197)^((i*31)>>7));
        memcpy(copy,raw,in*2);
        assert(!hb77_render_band(raw,in,w,0,64,4,old,n));
        assert(!hb97_render_band(raw,in,w,0,64,1,a,n,1,1));
        /* New correction may change unity-neutral high-contrast detail. */
        assert(!hb97_render_band(raw,in,w,0,64,1,a,n,.315,.678));
        assert(!hb97_render_band(raw,in,w,0,64,4,b,n,.315,.678));
        assert(!memcmp(a,b,n*2));assert(!memcmp(copy,raw,in*2));
        size_t row=(size_t)((w-64)&~1)*3;
        assert(!hb97_render_band(raw,in,w,62,2,3,b,row*2,.315,.678));
        assert(!memcmp(a+62*row,b,row*2*2));
        const double bad[]={0,-1,NAN,INFINITY,1.0/32,32};
        for(size_t i=0;i<sizeof(bad)/sizeof(bad[0]);i++) {
            memcpy(b,old,n*2);
            assert(hb97_render_band(raw,in,w,0,64,4,b,n,bad[i],1)==-2);
            assert(!memcmp(b,old,n*2));
            assert(hb97_render_band(raw,in,w,0,64,4,b,n,1,bad[i])==-2);
        }
        assert(hb97_render_band(raw,in-1,w,0,64,4,b,n,1,1)==-1);
        assert(hb97_render_band(raw,in,w,0,64,4,b,n-1,1,1)==-1);
        assert(hb97_render_band(raw,in,w,0,64,0,b,n,1,1)==-1);
        assert(hb97_render_band(raw,in,w,63,2,1,b,n,1,1)==-1);
        assert(hb97_render_band(raw,in,w,0,64,1,raw,n,1,1)==-1);
        assert(!hb97_render_band(raw,in,w,0,64,4,b,n,.0625,16));
        free(raw);free(copy);free(old);free(a);free(b);
    }
    puts("PASS native workers, tails, immutable input/output, metadata bounds and capacity checks");
}
