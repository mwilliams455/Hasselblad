/* SPDX-License-Identifier: MIT
 * Owned sparse white-reference expansion and E-ND table preparation. */
#include "hb_white_lut.h"
#include "hb_stat_prepare.h"
#include <math.h>
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static int32_t signed32(uint32_t v){int32_t s;memcpy(&s,&v,4);return s;}
static float f32(const void*p){float v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static uint32_t fu(float v){return !(v>0)?0:(double)v>=4294967295.0?UINT32_MAX:(uint32_t)v;}
static int valid_points(const unsigned char*p,unsigned n){
    if(n>15||(!p&&n>=2))return 0;
    if(n>=2)for(unsigned i=0;i<n;++i){uint32_t ct=u32(p+16*i);if(ct<2000||ct>10000)return 0;}
    return 1;
}
static uint32_t step(uint32_t a,uint32_t b,unsigned d){
    return d?(uint32_t)(signed32((b-a)<<10)/(int32_t)d):0;
}
static uint32_t advance(uint32_t slope,unsigned j){return (uint32_t)(signed32(slope*j)/1024);}
uint32_t hb_white_lut_expand(unsigned char*c,const unsigned char*p,unsigned n,unsigned char*out){
    if(!c||!out||!valid_points(p,n))return HB_PREP_UNSUPPORTED;
    if(n<2){w32(c+0x308,0);return 0;}
    unsigned upper=0;
    for(unsigned i=0;i<n-1;++i){
        const unsigned char*a=p+16*i,*b=a+16;
        uint32_t ct=u32(a);unsigned lower=(ct-2000)/100;upper=(u32(b)-2000)/100;
        w32(c+0x308+4*i,lower);if(upper<lower)return 33;
        unsigned d=upper-lower;uint32_t v[3],s[3];
        for(unsigned k=0;k<3;++k){v[k]=u32(a+4+4*k);s[k]=step(v[k],u32(b+4+4*k),d);}
        memcpy(out+16*lower,a,16);
        for(unsigned j=1;j<=d;++j){unsigned char*q=out+16*(lower+j);w32(q,ct+100*j);
            for(unsigned k=0;k<3;++k)w32(q+4+4*k,v[k]+advance(s[k],j));}
        /* The original first-segment branch excludes upper extrapolation
         * even when the same segment is also the last (two-point input). */
        if(i==0){
            for(unsigned j=1;j<=lower;++j){unsigned char*q=out+16*(lower-j);w32(q,ct-100*j);
                uint32_t r=v[0]-advance(s[0],j);if(signed32(r)<1)return 30;w32(q+4,r);
                uint32_t blue=v[1]-advance(s[1],j);if(signed32(blue)<1)return 30;w32(q+8,blue);
                uint32_t radius=v[2]-advance(s[2],j);w32(q+12,signed32(radius)>300?radius:300);}
        }else if(i==n-2){
            for(unsigned j=d+1;j<81-lower;++j){unsigned char*q=out+16*(lower+j);w32(q,ct+100*j);
                uint32_t r=v[0]+advance(s[0],j);if(signed32(r)<1)return 30;w32(q+4,r);
                uint32_t blue=v[1]+advance(s[1],j);if(signed32(blue)<1)return 30;w32(q+8,blue);
                uint32_t radius=v[2]+advance(s[2],j);w32(q+12,signed32(radius)>300?radius:300);}
        }
    }
    w32(c+0x308+4*(n-1),upper);return 0;
}
uint32_t hb_white_lut_prepare(unsigned char*c,const unsigned char*k){
    if(!c||!k)return HB_PREP_UNSUPPORTED;
    if(c[0x990dc]!=1){
        if(c[0xd4c0])return 0;
        unsigned n=k[0xc88];const unsigned char*p=k+0xc8c;
        if(!valid_points(p,n))return HB_PREP_UNSUPPORTED;
        uint32_t status=hb_white_lut_expand(c,p,n,c+0x344);if(status)return status;
        status=hb_white_lut_expand(c,p,n,c+0x854);if(status)return status;
        c[0xd4c0]=1;w32(c+0xd4bc,0);return 0;
    }
    unsigned axes=k[0xd7c];if(c[0xd4c2]!=1||!axes)return 0;
    float value=f32(c+0x990d8);unsigned lo=0,hi=0;
    for(unsigned i=0;i<axes;++i){if(value<=f32(k+0xd80+248*i)){lo=i?i-1:0;hi=i;break;}}
    const unsigned char*a=k+0xd80+248*lo,*b=k+0xd80+248*hi;unsigned n=a[4];
    if(n>15||n!=k[0xc88])return HB_PREP_UNSUPPORTED;
    unsigned char points[15*16];
    if(lo==hi)memcpy(points,a+8,16*n);
    else{
        float lower=f32(a),upper=f32(b),wa,wb;
        if(!isfinite(lower)||!isfinite(upper)||upper<lower||b[4]!=n)return HB_PREP_UNSUPPORTED;
        if(value==lower){wa=1;wb=0;}else if(value==upper){wa=0;wb=1;}
        else{wa=(upper-value)/(upper-lower);wb=1-wa;}
        for(unsigned i=0;i<4*n;++i){float x=wa*(float)u32(a+8+4*i),y=wb*(float)u32(b+8+4*i);w32(points+4*i,fu(x+y));}
    }
    if(!valid_points(points,n))return HB_PREP_UNSUPPORTED;
    uint32_t status=hb_white_lut_expand(c,points,n,c+0x344);
    if(!status)c[0xd4c0]=0;
    return status;
}
