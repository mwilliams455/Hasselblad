#include "frame76.h"
#include "../phocus_output_stage74/frame74.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

int hb76_render_band(const uint16_t *band,size_t input_count,int raw_width,
        int row_offset,int row_count,uint16_t *output,size_t output_capacity) {
    if(!band||!output||raw_width<128||raw_width>8192||row_offset<0||row_count<1||
       row_offset>63||row_count>64-row_offset)return -1;
    const int width=(raw_width-64)&~1;
    const size_t n=(size_t)width*(size_t)row_count*3;
    const size_t input_sites=(size_t)raw_width*128;
    if(input_count<input_sites||output_capacity<n)return -1;
    const uintptr_t a=(uintptr_t)band,b=(uintptr_t)output;
    if(a>UINTPTR_MAX-input_sites*2||b>UINTPTR_MAX-n*2||
       !(a+input_sites*2<=b||b+n*2<=a))return -1;
    uint16_t *prepared=malloc(128*128*sizeof(uint16_t));
    uint16_t *tile=malloc(64*64*3*sizeof(uint16_t));
    uint16_t *assembled=malloc(n*sizeof(uint16_t));
    if(!prepared||!tile||!assembled){free(prepared);free(tile);free(assembled);return -3;}
    HB73Plan plan;int status=hb73_plan(64,64,&plan);
    HB73Settings settings={HB73_RGGB,0xffffu,1.0,32,200,0};
    if(status)goto done;
    for(int x=0;x<width;x+=64) {
        const int anchor=x<width-64?x:width-64;
        const int skip=x-anchor;
        const int copy=width-x<64?width-x:64;
        for(int row=0;row<128;row++)
            memcpy(prepared+(size_t)row*128,band+(size_t)row*raw_width+anchor,256);
        status=hb74_render_final_bounded(&plan,&settings,prepared,128*128,128,tile,64*64*3,NULL);
        if(status)goto done;
        for(int row=0;row<row_count;row++)
            memcpy(assembled+((size_t)row*width+x)*3,
                tile+((size_t)(row+row_offset)*64+skip)*3,(size_t)copy*6);
    }
    memcpy(output,assembled,n*sizeof(uint16_t));
done:
    free(prepared);free(tile);free(assembled);return status;
}
