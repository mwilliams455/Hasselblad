#include "frame73.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>

static HB73Settings settings(uint16_t pad) {return (HB73Settings){0,0xffffu,1.0,32,200,pad};}
static void fixture(int w,int h,int pattern){
    HB73Plan p; assert(hb73_plan(w,h,&p)==0);
    assert(p.work_width==((w+71)&~7));
    assert(p.work_height==((h+71)&~7));
    assert(p.work_stride==1024);
    assert(p.crop_x==32&&p.crop_y==32);
    int in_stride=w+64+5;
    size_t n=(size_t)in_stride*(h+64);
    size_t count=(size_t)w*h*4;
    uint16_t *in=calloc(n+16,sizeof(uint16_t));
    uint16_t *a=calloc(count+16,sizeof(uint16_t));
    uint16_t *b=calloc(count+16,sizeof(uint16_t));
    assert(in&&a&&b);
    for(int y=0;y<h+64;++y)for(int x=0;x<w+64;++x){
        uint16_t z=(uint16_t)((y*419+x*383+pattern*7109) % 65536);
        in[(size_t)y*in_stride+x]=(pattern==0?10000:pattern==1?z:
            pattern==2?(x<(w+64)/2?300:65000):
            (uint16_t)((x*17+y*33+pattern*19)%65536));
    }
    memset(a+count,0xa5,16*sizeof(uint16_t));memset(b+count,0xa5,16*sizeof(uint16_t));
    HB73Receipt x,y;
    HB73Settings sa=settings(0),sb=settings(65535);
    assert(hb73_render_pre_noise(&p,&sa,in,n,in_stride,a,count,&x)==0);
    assert(hb73_render_pre_noise(&p,&sb,in,n,in_stride,b,count,&y)==0);
    assert(memcmp(a,b,count*sizeof(uint16_t))==0);
    for(int i=0;i<16;++i){assert(a[count+i]==0xa5a5);assert(b[count+i]==0xa5a5);}
    assert(x.interpolator_events>0&&x.allocated_bytes>0);
    if(pattern==0){for(size_t i=0;i<count;i+=4)
        assert(a[i]==10000&&a[i+1]==10000&&a[i+2]==10000);}
    uint16_t untouched=0x7777;HB73Settings bad=settings(0);bad.flags=0;
    assert(hb73_render_pre_noise(&p,&bad,in,n,in_stride,&untouched,1,NULL)==HB73_UNSUPPORTED);
    assert(untouched==0x7777);
    assert(hb73_render_pre_noise(&p,&sa,in,n-1,in_stride,a,count,NULL)==HB73_BAD_ARGUMENT);
    assert(hb73_render_pre_noise(&p,&sa,in,n,in_stride,a,count-1,NULL)==HB73_BAD_ARGUMENT);
    assert(hb73_render_pre_noise(&p,&sa,in,n,in_stride,in,n,NULL)==HB73_BAD_ARGUMENT);
    assert(hb73_render_pre_noise(&p,&sa,in,n,w+63,a,count,NULL)==HB73_BAD_ARGUMENT);
    free(in);free(a);free(b);
}
int main(void){
    const int dimensions[][2]={{9,11},{12,15},{18,34},{23,31},{33,35},
                               {24,16},{34,18},{32,32},{64,64}};
    HB73Plan p;
    assert(hb73_plan(0,64,&p)==HB73_BAD_ARGUMENT);
    assert(hb73_plan(40,40,&p)==HB73_UNSUPPORTED);
    assert(hb73_plan(64,64,NULL)==HB73_BAD_ARGUMENT);
    int cases=0;
    for(size_t i=0;i<sizeof(dimensions)/sizeof(dimensions[0]);++i)
        for(int k=0;k<4;++k){fixture(dimensions[i][0],dimensions[i][1],k);++cases;}
    printf("STAGE73_PRENOISE_HOST_CASES_PASS=%d\n",cases);
    return 0;
}
