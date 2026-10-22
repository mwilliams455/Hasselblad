/* SPDX-License-Identifier: MIT */
#include "hb_display_lut16.h"
#include <math.h>
#include <stdint.h>
#include <stddef.h>

static int overlapping(const void *a, size_t asize, const void *b, size_t bsize) {
    uintptr_t x=(uintptr_t)a, y=(uintptr_t)b;
    return x<=y ? (y-x)<asize : (x-y)<bsize;
}
static void node_unchecked(const uint32_t *words, uint32_t r, uint32_t g,
                           uint32_t b, double out[3]) {
    const uint32_t q=128u*r+8u*g+b/2u;
    const unsigned shift=(b&1u)*16u;
    for(unsigned i=0;i<3;++i) {
        out[i]=(double)((words[q+2048u*i]>>shift)&0xfffu)/4095.0;
    }
}
int hb_display_lut16_node(const uint32_t *words, size_t count,
                          uint32_t r, uint32_t g, uint32_t b, double out[3]) {
    if(!words||!out) return HB_DISPLAY_LUT16_BAD_ARGUMENT;
    if(count!=HB_DISPLAY_LUT16_WORDS) return HB_DISPLAY_LUT16_BAD_TABLE;
    if(r>=16u||g>=16u||b>=16u) return HB_DISPLAY_LUT16_OUT_OF_DOMAIN;
    if(overlapping(words,count*sizeof(*words),out,3u*sizeof(*out)))
        return HB_DISPLAY_LUT16_OVERLAP;
    double temp[3];
    node_unchecked(words,r,g,b,temp);
    for(unsigned i=0;i<3;++i)out[i]=temp[i];
    return HB_DISPLAY_LUT16_OK;
}
int hb_display_lut16_trilinear(const uint32_t *words, size_t count,
                               const double input[3], double output[3]) {
    if(!words||!input||!output) return HB_DISPLAY_LUT16_BAD_ARGUMENT;
    if(count!=HB_DISPLAY_LUT16_WORDS) return HB_DISPLAY_LUT16_BAD_TABLE;
    if(overlapping(words,count*sizeof(*words),input,3u*sizeof(*input))||
       overlapping(words,count*sizeof(*words),output,3u*sizeof(*output)))
        return HB_DISPLAY_LUT16_OVERLAP;
    uint32_t lo[3],hi[3]; double f[3];
    for(unsigned i=0;i<3;++i) {
        double x=input[i];
        if(!isfinite(x)||x<0.0||x>1.0) return HB_DISPLAY_LUT16_OUT_OF_DOMAIN;
        double pos=x*15.0;
        lo[i]=(uint32_t)floor(pos);
        hi[i]=lo[i]<15u ? lo[i]+1u : 15u;
        f[i]=pos-(double)lo[i];
    }
    double result[3]={0.0,0.0,0.0};
    for(unsigned rr=0;rr<2;++rr) for(unsigned gg=0;gg<2;++gg)
        for(unsigned bb=0;bb<2;++bb) {
            const double weight=(rr?f[0]:1.0-f[0])*(gg?f[1]:1.0-f[1])*
                                (bb?f[2]:1.0-f[2]);
            double node[3];
            node_unchecked(words,rr?hi[0]:lo[0],gg?hi[1]:lo[1],
                           bb?hi[2]:lo[2],node);
            result[0]+=weight*node[0];
            result[1]+=weight*node[1];
            result[2]+=weight*node[2];
        }
    for(unsigned i=0;i<3;++i)output[i]=result[i];
    return HB_DISPLAY_LUT16_OK;
}
