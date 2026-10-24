/* Direct composition checks with Stage61 previously verified implementation. */
#include "raw_gradient67.h"
#include "green_site_mask67.h"
#include "../phocus_gradient_stage61/gradient_maps61.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint32_t state=67001;
static uint32_t rnd(void){state=state*UINT32_C(1664525)+UINT32_C(1013904223);return state;}
int main(void){
 for(int w=9;w<=33;w+=8)for(int n=0;n<500;++n){
    uint16_t raw[9*33];int16_t edge[9*33];
    for(int y=0;y<9;++y)for(int x=0;x<w;++x){
        size_t k=(size_t)y*w+x;
        raw[k]=(uint16_t)rnd();
        const uint16_t bits=(uint16_t)rnd();
        memcpy(&edge[k],&bits,sizeof bits);
    }
    const uint16_t orig_raw=raw[4*w+4];
    const int16_t orig_edge=edge[4*w+4];
    int16_t first[8],second[8],a[8],b[8];uint16_t actual=0,expected=0;
    int16_t lo1=(int16_t)(n%5==0?-32768: n%5==1?32767:50);
    int16_t lo2=(int16_t)(n%3==0?-32768: n%3==1?32767:400);
    assert(hb_gradient_directions61(edge+4*w+4,w,a)==0);
    assert(hb_inline_raw_gradient67(raw+4*w+4,w,b)==0);
    expected=hb_gradient_mask61(a,b,lo1,lo2);
    assert(hb_green_site_mask67(raw+4*w+4,edge+4*w+4,w,lo1,lo2,first,second,&actual)==0);
    assert(actual==expected);
    assert(memcmp(first,a,sizeof a)==0 && memcmp(second,b,sizeof b)==0);
    assert(raw[4*w+4]==orig_raw && edge[4*w+4]==orig_edge);
 }
 assert(hb_green_site_mask67(NULL,NULL,9,50,400,(int16_t[8]){0},(int16_t[8]){0},
         &(uint16_t){0})==-1);
 puts("STAGE67_GREEN_SITE_MASK_COMPOSITION_PASS");
 return 0;
}
