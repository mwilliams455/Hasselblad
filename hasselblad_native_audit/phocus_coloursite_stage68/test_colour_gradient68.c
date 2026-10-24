#include "colour_gradient68.h"
#include "../phocus_inline_stage67/raw_gradient67.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define W 23
#define H 9
static uint16_t input[H*W];
static uint32_t rand_state=UINT32_C(0x68c0012d);
static uint32_t random32(void) {rand_state^=rand_state<<13;rand_state^=rand_state>>17;rand_state^=rand_state<<5;return rand_state;}
static void fixture(uint16_t fill) {
    for(size_t i=0;i<H*W;++i) input[i]=fill;
}
static void compare(const int16_t expected[8]) {
    struct {int16_t before;int16_t code[8];int16_t after;} dst={1234,{0},5678};
    uint16_t original[H*W];memcpy(original,input,sizeof input);
    assert(hb_colour_raw_gradient68(input+4*W+W/2,W,dst.code)==0);
    assert(dst.before==1234&&dst.after==5678);
    assert(memcmp(original,input,sizeof input)==0);
    if(expected) for(int i=0;i<8;++i) assert(dst.code[i]==expected[i]);
}
int main(void) {
    int16_t zeros[8]={0};
    for(int i=0;i<5;++i) {fixture((uint16_t[]){0,1,32767,65534,65535}[i]);compare(zeros);}
    /* Witness: reusing green-site diagonals at R/B CFA sites is wrong.
     * One synthetic 8000-code impulse at (dy=-1, dx=0) produces NE/NW=2000
     * on the colour-site route, but NE/NW=0 on the green-site route. */
    fixture(0);input[(4-1)*W+W/2]=8000;
    int16_t colour[8],green_site[8];
    assert(hb_colour_raw_gradient68(input+4*W+W/2,W,colour)==0);
    assert(hb_inline_raw_gradient67(input+4*W+W/2,W,green_site)==0);
    assert(colour[4]==2000 && colour[7]==2000);
    assert(green_site[4]==0 && green_site[7]==0);
    for(int k=0;k<4;++k)assert(colour[k]==green_site[k]);
    for(int site=0;site<H*W;++site) {fixture(0);input[site]=65535;compare(NULL);}
    for(int trial=0;trial<8000;++trial){
        for(int site=0;site<H*W;++site) input[site]=(uint16_t)random32();
        compare(NULL);
    }
    assert(hb_colour_raw_gradient68(NULL,W,zeros)==-1);
    assert(hb_colour_raw_gradient68(input,4,zeros)==-1);
    assert(hb_colour_raw_gradient68(input,W,NULL)==-1);
    puts("STAGE68_COLOUR_GRADIENT_C11_PASS");
    return 0;
}
