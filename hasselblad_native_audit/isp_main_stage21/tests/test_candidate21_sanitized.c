/* SPDX-License-Identifier: MIT
 * Sanitizer-only numerical contract test, no vendor LUT or photographs.
 */
#include "hb_main_candidate21.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t *words;
static double *input,*output;
static int fail(const char *reason){fprintf(stderr,"FAILED %s\n",reason);return 1;}
int main(void){
    words=(uint32_t*)calloc(HB21_TABLE_WORDS,sizeof(uint32_t));
    input=(double*)calloc(HB21_MAX_POINTS*3u,sizeof(double));
    output=(double*)calloc(HB21_MAX_POINTS*3u,sizeof(double));
    if(!words||!input||!output)return fail("allocation");
    for(unsigned r=0;r<16;r++)for(unsigned g=0;g<16;g++)for(unsigned b=0;b<16;b++){
       unsigned idx=128u*r+8u*g+b/2u;
       unsigned sh=16u*(b&1u);
       unsigned values[3]={273u*r,273u*g,273u*b};
       for(unsigned channel=0;channel<3;channel++)
           words[idx+2048u*channel]|=values[channel]<<sh;
    }
    for(unsigned i=0;i<HB21_MAX_POINTS;i++){
       input[3u*i]=(double)(i%251u)/250.0;
       input[3u*i+1]=(double)(i%127u)/126.0;
       input[3u*i+2]=(double)(i%199u)/198.0;
    }
    uint8_t ident[3]={0,1,2};hb21_receipt receipt;
    memset(&receipt,0xaf,sizeof(receipt));
    for(int mode=0;mode<=1;mode++){
      if(hb21_sample_candidate(words,HB21_TABLE_WORDS,input,3u*HB21_MAX_POINTS,output,
        3u*HB21_MAX_POINTS,HB21_MAX_POINTS,ident,ident,mode,&receipt)!=HB21_OK)return fail("sample");
      if(receipt.photographic_render_authorized || receipt.main_isp_pixel_equivalence_proven)return fail("authorization");
      for(unsigned i=0;i<3u*HB21_MAX_POINTS;i++)
        if(fabs(input[i]-output[i])>1.e-13)return fail("identity error");
    }
    for(unsigned i=0;i<3u*HB21_MAX_POINTS;i++) output[i]=314159.;
    input[3u*HB21_MAX_POINTS-1u]=-0.00001;
    receipt.schema=314159u;
    if(hb21_sample_candidate(words,HB21_TABLE_WORDS,input,3u*HB21_MAX_POINTS,output,
       3u*HB21_MAX_POINTS,HB21_MAX_POINTS,ident,ident,0,&receipt)!=HB21_INVALID_RGB)return fail("bad range accepted");
    for(unsigned i=0;i<3u*HB21_MAX_POINTS;i++)if(output[i]!=314159.)return fail("transaction failed");
    if(receipt.schema!=314159u)return fail("receipt mutated");
    input[3u*HB21_MAX_POINTS-1u]=0.5;
    if(hb21_sample_candidate(words,HB21_TABLE_WORDS,input,3u*HB21_MAX_POINTS,output,
       3u*HB21_MAX_POINTS,HB21_MAX_POINTS+1u,ident,ident,0,&receipt)!=HB21_BAD_SHAPE)return fail("overflow points accepted");
    if(hb21_sample_candidate(words,HB21_TABLE_WORDS,input,3u*HB21_MAX_POINTS,output,
       3u*HB21_MAX_POINTS,0,ident,ident,0,&receipt)!=HB21_BAD_SHAPE)return fail("zero points accepted");
    free(words);free(input);free(output);
    puts("PASS stage21 synthetic candidate ASan/UBSan; photographic rendering not authorized");
    return 0;
}
