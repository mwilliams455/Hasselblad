#include "raw_gradient67.h"
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void constant_case(uint16_t value,int width) {
    uint16_t image[9*37];
    for(unsigned i=0;i<sizeof(image)/sizeof(image[0]);++i)image[i]=value;
    int16_t out[10];
    for(unsigned i=0;i<10;++i)out[i]=12345;
    assert(hb_inline_raw_gradient67(image+4*width+4,width,out+1)==0);
    for(int j=1;j<=8;++j)assert(out[j]==0);
    assert(out[0]==12345 && out[9]==12345);
    for(unsigned i=0;i<sizeof(image)/sizeof(image[0]);++i)assert(image[i]==value);
}
static void ramp_case(int dx,int dy,int width) {
    uint16_t image[9*37];
    for(int y=0;y<9;++y)for(int x=0;x<width;++x)
        image[(size_t)y*width+x]=(uint16_t)(1000+dx*x+dy*y);
    int16_t out[8];
    assert(hb_inline_raw_gradient67(image+4*width+4,width,out)==0);
    int expect[8]={2*dy,2*dx,2*dy,2*dx,2*(dx-dy),2*(dx+dy),
                   2*(dx-dy),2*(dx+dy)};
    /* Inputs are measured across distances of TWO sites and then /8. For
     * nonnegative linear ramps the output equals the single-site slopes. */
    for(int i=0;i<8;++i){
        int v=expect[i];if(v<0)v=-v;
        assert(out[i]==v/2);
    }
}
static void rounding_witness(void) {
    /* Synthetic (not from a photograph). Grouping two half-sums into one
     * produces 2, while the native and independent C preserve result 1. */
    const uint16_t grid[25]={
        9,8,8,2,7,
        2,9,3,8,0,
        7,0,5,9,2,
        1,10,2,0,1,
        9,6,5,2,0
    };
    int16_t out[8]={0};
    assert(hb_inline_raw_gradient67(grid+12,5,out)==0);
    assert(out[0]==1);
    const uint32_t merged_halves=(4u+(8u+7u+1u+8u)/2u)>>3;
    assert(merged_halves==2u);
}
int main(void) {
    rounding_witness();
    assert(hb_inline_raw_gradient67(NULL,9,(int16_t[8]){0})==-1);
    assert(hb_inline_raw_gradient67((uint16_t[25]){0},4,(int16_t[8]){0})==-1);
    assert(hb_inline_raw_gradient67((uint16_t[25]){0},5,NULL)==-1);
    for(int width=9;width<=37;width+=7){
        constant_case(0,width);constant_case(1,width);
        constant_case(65535,width);
        ramp_case(100,53,width);ramp_case(17,22,width);
    }
    puts("STAGE67_SCALAR_RAW_GRADIENT_C11_PASS");
    return 0;
}
