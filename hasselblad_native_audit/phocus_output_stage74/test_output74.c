#include "output74.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void pixel(uint16_t y,int16_t a,int16_t b,uint16_t r,uint16_t g,uint16_t bl){
    uint16_t output[3]={123,456,789};
    assert(hb74_ycc_to_rgb_pixel(y,a,b,1.,output)==0);
    assert(output[0]==r&&output[1]==g&&output[2]==bl);
}
int main(void){
    pixel(0,0,0,0,0,0);
    pixel(10000,0,0,10000,10000,10000);
    pixel(65535,0,0,65534,65534,65534);
    pixel(37757,1120,-5997,48537,43378,15735);
    uint16_t sentinel[3]={15,16,17};
    assert(hb74_ycc_to_rgb_pixel(200,0,0,2.0,sentinel)==-2);
    assert(sentinel[0]==15&&sentinel[1]==16&&sentinel[2]==17);
    uint16_t y[8*16]={0};int16_t a[8*16]={0},b[8*16]={0};
    uint16_t out[2*3*3]={0};
    for(int yy=0;yy<8;++yy)for(int xx=0;xx<16;++xx)y[yy*16+xx]=10000;
    assert(hb74_convert_roi(y,a,b,10,8,16,2,2,3,2,1.,out,18)==0);
    for(int i=0;i<18;++i)assert(out[i]==10000);
    assert(hb74_convert_roi(y,a,b,10,8,16,9,2,3,2,1.,out,18)==-1);
    assert(hb74_convert_roi(y,a,b,10,8,16,2,2,3,2,0.8,out,18)==-2);
    assert(hb74_convert_roi(y,a,b,10,8,16,2,2,3,2,1.,out,17)==-1);
    assert(out[0]==10000&&out[17]==10000);
    assert(hb74_convert_roi(y,a,b,10,8,16,2,2,3,2,1.,y,18)==-1);
    assert(y[0]==10000);
    puts("STAGE74_OUTPUT_C11_TEST_PASS");
    return 0;
}
