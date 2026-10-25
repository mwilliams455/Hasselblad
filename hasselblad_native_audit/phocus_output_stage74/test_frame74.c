#include "frame74.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void fixture(int width,int height,int impulse){
    HB73Plan p; assert(hb73_plan(width,height,&p)==0);
    const size_t input_sites=(size_t)p.source_width*p.source_height;
    const size_t rgb_sites=(size_t)width*height*3;
    uint16_t *input=calloc(input_sites,sizeof(uint16_t));
    uint16_t *out1=calloc(rgb_sites,sizeof(uint16_t));
    uint16_t *out2=calloc(rgb_sites,sizeof(uint16_t));
    assert(input&&out1&&out2);
    for(size_t i=0;i<input_sites;++i)input[i]=10000;
    if(impulse)input[(size_t)(p.crop_y+height/2)*p.source_width+
                      p.crop_x+width/2]=65535;
    HB73Settings s={HB73_RGGB,0xffffu,1.0,32,200,0};
    HB74Receipt a,b;
    assert(hb74_render_final_bounded(&p,&s,input,input_sites,p.source_width,
                                    out1,rgb_sites,&a)==0);
    s.alignment_tail_fill=65535;
    assert(hb74_render_final_bounded(&p,&s,input,input_sites,p.source_width,
                                    out2,rgb_sites,&b)==0);
    assert(memcmp(out1,out2,rgb_sites*2)==0);
    assert(a.final_rgb16_pixels==(uint64_t)width*height);
    assert(a.colornoise_converted_sites>0&&a.colornoise_correction_sites>0);
    if(!impulse){for(size_t i=0;i<rgb_sites;++i)assert(out1[i]==10000);}
    if(impulse){int different=0;for(size_t i=0;i<rgb_sites;++i)different|=(out1[i]!=10000);assert(different);}
    uint16_t marker[3]={101,102,103};
    assert(hb74_render_final_bounded(&p,&s,input,input_sites,p.source_width,
                                    marker,2,0)==-1);
    assert(marker[0]==101&&marker[1]==102&&marker[2]==103);
    free(input);free(out1);free(out2);
}
int main(void){
    const int sizes[][2]={{9,11},{12,15},{18,34},{23,31},{33,35},
                          {24,16},{34,18},{32,32},{64,64}};
    for(size_t i=0;i<sizeof sizes/sizeof sizes[0];++i){
        fixture(sizes[i][0],sizes[i][1],0);
        fixture(sizes[i][0],sizes[i][1],1);
    }
    puts("STAGE74_FINAL_PIPELINE_18_CASES_PASS");
    return 0;
}
