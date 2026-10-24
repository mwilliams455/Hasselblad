#include "wiring66.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const HB66Planes *p; unsigned prepared[5];
                 uint64_t green_sites_seen,colour_calls,mask_calls,rb_calls;
                 int abort_at; } Mock;
static int prepare(void *user,HB66Event ev,int y){
    Mock*m=user;(void)y;
    assert(ev>=HB66_SMOOTH_ROW && ev<=HB66_MID_GREEN_MAP);
    ++m->prepared[ev];return 0;
}
static int green(void *user,int x,int y,uint16_t *g,uint16_t *mask){
    Mock *m=user;
    const size_t p=(size_t)y*m->p->domain.stride+(size_t)x;
    *g=(uint16_t)(m->p->raw[p]+7);
    *mask=((x+y)/2)%3==0?0:0x101;
    ++m->green_sites_seen;
    return 0;
}
static int32_t opposite(void *user,int x,int y,int red_site,uint16_t mask){
    Mock*m=user;assert(mask==0x101);
    ++m->colour_calls;
    return (red_site?-131071:32769)+(x+y-x-y);
}
static int site_mask(void *user,int x,int y,uint16_t *mask){
    Mock*m=user;++m->mask_calls;
    *mask=(x+y)%3?0x101:0;
    return 0;
}
static int site_rb(void *user,int x,int y,uint16_t mask,uint16_t *r,uint16_t *b){
    Mock*m=user;assert(mask==0x101);++m->rb_calls;
    *r=(uint16_t)(3000+x);*b=(uint16_t)(7000+y);
    return 0;
}
static void fixture(int width,int height,int stride){
    const size_t n=(size_t)height*stride;
    uint16_t *input=malloc(n*2),*red=malloc(n*2),*greenp=malloc(n*2),
             *blue=malloc(n*2),*mask=malloc(n*2);
    assert(input&&red&&greenp&&blue&&mask);
    for(size_t i=0;i<n;++i) {
        input[i]=(uint16_t)(i*73u+7u);
        red[i]=111;greenp[i]=222;blue[i]=333;mask[i]=444;
    }
    HB66Planes p={{width,height,stride,0xffff},input,red,greenp,blue,mask};
    Mock m={0};m.p=&p;m.abort_at=-1;
    HB66Callbacks cb={&m,prepare,green,opposite,site_mask,site_rb};
    HB66WiringCounts c;
    assert(hb_wire_interpolate66(&p,&cb,&c)==0);
    assert(m.prepared[1]==(unsigned)(height-2) && m.prepared[2]==(unsigned)(height-4));
    assert(m.prepared[3]==1 && m.prepared[4]==1);
    assert(m.green_sites_seen==c.events.green_colour_estimates);
    assert(m.colour_calls==c.opposite_colour_calls);
    assert(m.mask_calls==c.events.green_site_masks && m.rb_calls==c.green_site_rb_calls);
    assert(c.opposite_colour_calls+c.opposite_zero_fallbacks==
           c.events.blue_at_red_candidates+c.events.red_at_blue_candidates);
    assert(c.green_site_rb_calls+c.green_site_zero_fallbacks==c.events.red_blue_green_candidates);
    for(int y=0;y<height;++y)for(int x=0;x<stride;++x){
        const size_t i=(size_t)y*stride+x;
        assert(input[i]==(uint16_t)(i*73u+7u));
        if(x<width) assert(greenp[i]==input[i] ||
            (((x&1)==(y&1))&& greenp[i]==(uint16_t)(input[i]+7)));
        if((x>=width || y<4 || y>=height-4 || x<4 || x>=width-4)) {
            assert(red[i]==111 && blue[i]==333 && mask[i]==444);
        }
        if(x>=width) assert(red[i]==111 && blue[i]==333 && mask[i]==444);
    }
    /* Unsupported dispatch must fail BEFORE mutating any buffers. */
    p.domain.flags=0x60;
    uint16_t frozen=red[4*stride+4];
    assert(hb_wire_interpolate66(&p,&cb,&c)==-2 && red[4*stride+4]==frozen);
    p.domain.flags=0xffff;
    p.red=p.green;
    assert(hb_wire_interpolate66(&p,&cb,&c)==-1);
    free(input);free(red);free(greenp);free(blue);free(mask);
}
int main(void){
    fixture(24,24,24); fixture(32,32,37);
    fixture(32,40,48);fixture(80,88,88);
    puts("STAGE66_BOUNDED_WIRING_SELF_TEST_PASS");
    return 0;
}
