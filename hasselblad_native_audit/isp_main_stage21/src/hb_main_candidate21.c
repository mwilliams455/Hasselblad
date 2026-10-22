/* SPDX-License-Identifier: MIT */
#include "hb_main_candidate21.h"
#include <math.h>
#include <stddef.h>
#include <stdint.h>

static int overlaps(const void *a,size_t n,const void *b,size_t m) {
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return x<=y ? (y-x)<n : (x-y)<m;
}
static int valid_perm(const uint8_t *p) {
    if(!p)return 0;
    unsigned mask=0;
    for(unsigned i=0;i<3;i++) {
        if(p[i]>2)return 0;
        mask|=1u<<p[i];
    }
    return mask==7u;
}
static uint32_t code_perm(const uint8_t *p) {
    return 100u*p[0]+10u*p[1]+p[2];
}
/* Stage9's known DISPLAY planar decoder, reused here ONLY as a hypothesis. */
static void node(const uint32_t *src, const uint8_t *map,
                 uint32_t r,uint32_t g,uint32_t b,double out[3]) {
    uint32_t q=128u*r+8u*g+b/2u;
    unsigned shift=(b&1u)*16u;
    for(unsigned bank=0;bank<3;bank++) {
        out[map[bank]]=(double)((src[q+2048u*bank]>>shift)&0xfffu)/4095.0;
    }
}
static void one(const uint32_t *src,const double *input,double *output,
                const uint8_t *axes,const uint8_t *bank,int interp) {
    uint32_t lo[3],hi[3];double f[3];
    for(unsigned a=0;a<3;a++) {
        double pos=15.0*input[axes[a]];
        lo[a]=(uint32_t)floor(pos);
        hi[a]=lo[a]<15u?lo[a]+1u:15u;
        f[a]=pos-(double)lo[a];
    }
    double out[3]={0,0,0};
    if(interp==HB21_TRILINEAR) {
        for(unsigned rr=0;rr<2;rr++)for(unsigned gg=0;gg<2;gg++)for(unsigned bb=0;bb<2;bb++) {
            double weight=(rr?f[0]:1.0-f[0])*(gg?f[1]:1.0-f[1])*(bb?f[2]:1.0-f[2]);
            double values[3];
            node(src,bank,rr?hi[0]:lo[0],gg?hi[1]:lo[1],bb?hi[2]:lo[2],values);
            for(unsigned i=0;i<3;i++)out[i]+=weight*values[i];
        }
    }else {
        /* A common tetrahedral interpolation convention, NOT verified for MAIN. */
        unsigned order[3]={0,1,2};
        if(f[order[1]]>f[order[0]]){unsigned t=order[0];order[0]=order[1];order[1]=t;}
        if(f[order[2]]>f[order[1]]){unsigned t=order[1];order[1]=order[2];order[2]=t;}
        if(f[order[1]]>f[order[0]]){unsigned t=order[0];order[0]=order[1];order[1]=t;}
        uint32_t xyz[3]={lo[0],lo[1],lo[2]};
        double previous[3],next[3];
        node(src,bank,xyz[0],xyz[1],xyz[2],previous);
        for(unsigned i=0;i<3;i++)out[i]=previous[i];
        for(unsigned j=0;j<3;j++) {
            unsigned axis=order[j];
            xyz[axis]=hi[axis];
            node(src,bank,xyz[0],xyz[1],xyz[2],next);
            for(unsigned i=0;i<3;i++) {
                out[i]+=f[axis]*(next[i]-previous[i]);
                previous[i]=next[i];
            }
        }
    }
    for(unsigned i=0;i<3;i++)output[i]=out[i];
}
int hb21_sample_candidate(const uint32_t *source, size_t source_words,
                          const double *input, size_t input_scalars,
                          double *output, size_t output_scalars,
                          size_t points, const uint8_t axis_to_input[3],
                          const uint8_t bank_to_output[3],
                          int interpolation, hb21_receipt *receipt) {
    if(!source||!input||!output||!receipt)return HB21_BAD_ARGUMENT;
    if(source_words!=HB21_TABLE_WORDS || !points||points>HB21_MAX_POINTS||
       input_scalars!=3u*points || output_scalars!=3u*points)return HB21_BAD_SHAPE;
    if(!valid_perm(axis_to_input)||!valid_perm(bank_to_output))return HB21_INVALID_PERMUTATION;
    if(interpolation!=HB21_TRILINEAR && interpolation!=HB21_TETRAHEDRAL)
        return HB21_INVALID_INTERPOLATION;
    size_t tablebytes=source_words*sizeof(uint32_t);
    size_t pixbytes=3u*points*sizeof(double);
    if(overlaps(source,tablebytes,input,pixbytes)||
       overlaps(source,tablebytes,output,pixbytes)||
       (input!=output && overlaps(input,pixbytes,output,pixbytes))||
       overlaps(source,tablebytes,receipt,sizeof(*receipt))||
       overlaps(input,pixbytes,receipt,sizeof(*receipt))||
       overlaps(output,pixbytes,receipt,sizeof(*receipt)))return HB21_OVERLAP;
    /* Entire input must validate before a single output is modified. */
    for(size_t w=0;w<source_words;w++)
        if(source[w]&UINT32_C(0xf000f000))return HB21_INVALID_LUT;
    for(size_t i=0;i<3u*points;i++)
        if(!isfinite(input[i])||input[i]<0.0||input[i]>1.0)return HB21_INVALID_RGB;
    for(size_t i=0;i<points;i++)
        one(source,input+3u*i,output+3u*i,axis_to_input,bank_to_output,interpolation);
    hb21_receipt r={0};
    r.schema=HB21_SCHEMA;
    r.points=(uint32_t)points;
    r.interpolation=(uint32_t)interpolation;
    r.axis_to_input_code=code_perm(axis_to_input);
    r.bank_to_output_code=code_perm(bank_to_output);
    r.source_words=HB21_TABLE_WORDS;
    r.planar_packing_assumed=1;
    r.main_isp_pixel_equivalence_proven=0;
    r.photographic_render_authorized=0;
    *receipt=r;
    return HB21_OK;
}
