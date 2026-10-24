/* Synthetic self-test only. Native ARM64 parity is a separate private audit. */
#include "interpolate62.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void test_constants(void) {
    uint16_t red[25],green[25],blue[25];
    for (int i=0;i<25;++i){red[i]=32000;green[i]=16000;blue[i]=41000;}
    for (unsigned mask=0;mask<256;++mask) {
        uint16_t outred=0,outblue=0;
        assert(hb_blue_at_red_code62(blue+12,green+12,mask,5)==41000);
        assert(hb_red_blue_at_green62(red+12,green+12,blue+12,
                                    &outred,&outblue,mask,5)==0);
        assert(outred==32000&&outblue==41000);
        /* Both outputs can alias their own input plane after snapshots. */
        uint16_t ar[25],ab[25];memcpy(ar,red,sizeof red);memcpy(ab,blue,sizeof blue);
        assert(hb_red_blue_at_green62(ar+12,green+12,ab+12,
                                     ar+12,ab+12,mask,5)==0);
        assert(ar[12]==32000&&ab[12]==41000);
    }
}
static void test_fallback_and_clamp(void) {
    uint16_t red[25]={0},green[25]={0},blue[25]={0};
    blue[6]=4;blue[8]=8;blue[16]=12;blue[18]=16;
    assert(hb_blue_at_red_code62(blue+12,green+12,0,5)==10);
    /* No usable denominator selects same four-diagonal fallback. */
    assert(hb_blue_at_red_code62(blue+12,green+12,255,5)==10);
    red[7]=8;red[13]=16;red[17]=24;red[11]=32;
    blue[7]=12;blue[13]=24;blue[17]=36;blue[11]=48;
    uint16_t r=0,b=0;
    assert(hb_red_blue_at_green62(red+12,green+12,blue+12,
                                  &r,&b,0,5)==0);
    assert(r==20&&b==30);
    assert(hb_red_blue_at_green62(red+12,green+12,blue+12,
                                  &r,&b,255,5)==0);
    assert(r==20&&b==30);
    for(int i=0;i<25;++i){green[i]=red[i]=blue[i]=65535;}
    assert(hb_blue_at_red_code62(blue+12,green+12,255,5)==65534);
    assert(hb_red_blue_at_green62(red+12,green+12,blue+12,
                                  &r,&b,255,5)==0);
    assert(r==65534&&b==65534);
}
static void test_invalid(void) {
    uint16_t a[25]={0};
    assert(hb_blue_at_red_code62(NULL,a+12,1,5)==0);
    assert(hb_blue_at_red_code62(a+12,a+12,1,2)==0);
    assert(hb_red_blue_at_green62(a+12,a+12,a+12,a+12,a+12,1,2)==-1);
    assert(hb_red_blue_at_green62(a+12,a+12,a+12,NULL,a+12,1,5)==-1);
}
int main(void){test_constants();test_fallback_and_clamp();test_invalid();
    puts("STAGE62_INTERPOLATE_C11_SELF_TEST_PASS");return 0;}
