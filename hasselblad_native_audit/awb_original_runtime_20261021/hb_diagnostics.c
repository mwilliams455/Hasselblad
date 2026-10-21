/* SPDX-License-Identifier: MIT
 * Owned diagnostic carry-forward, byte encoding and statistics packing. */
#include "hb_diagnostics.h"
#include "hb_stat_prepare.h"
#include <string.h>
static uint16_t u16(const void*p){uint16_t v;memcpy(&v,p,2);return v;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static unsigned lengths_ok(const unsigned char*c){unsigned a=u16(c+0xa8ba8),b=u16(c+0xa8baa);return a<=510&&a+b<=1015;}
static unsigned no_file(const unsigned char*c){return c[0xb1ef8]!=1||!u16(c+0xb1efa)||!u16(c+0xb1efc)||u32(c+0xb1f00)%u16(c+0xb1efc)!=0;}
uint32_t hb_debug_userdump_no_file(unsigned char*c){
    if(!c||!no_file(c))return HB_PREP_UNSUPPORTED;
    if(c[0xb1ef8]!=1)return 0;
    if(!u16(c+0xb1efa)||!u16(c+0xb1efc))c[0xb1ef8]=0;
    else w32(c+0xb1f00,u32(c+0xb1f00)+1);
    return 0;
}
uint32_t hb_debug_encode(unsigned char*c){
    if(!c||!lengths_ok(c))return HB_PREP_UNSUPPORTED;
    unsigned a=u16(c+0xa8ba8),b=u16(c+0xa8baa);
    for(unsigned section=0;section<2;++section){
        unsigned n=section?b:a;unsigned char*p=c+0xa8bc0+(section?a+4:2);
        memset(c+0xad310,0,0x3fb);uint32_t key=0x263b;
        for(unsigned i=0;i<n;++i){unsigned char v=(unsigned char)(p[i]^key);c[0xad310+i]=v;key+=v+25u;}
        memcpy(p,c+0xad310,n);
    }
    return 0;
}
static void carry(unsigned char*c){
    if(u32(c+0x194)>=2)return;
    if(c[0xa851d]){memcpy(c+0xa885c,c+0xa8510,0x34c);return;}
    memcpy(c+0xacfc4,c+0xa8510,0x34c);memcpy(c+0xa8510,c+0xa885c,0x34c);
    static const struct{uint32_t offset;unsigned bytes;} fields[]={
        {0xa85da,4},{0xa8518,4},{0xa851e,4},{0xa85d2,8},{0xa85c6,4},
        {0xa85de,2},{0xa85e0,4},{0xa85e4,2},{0xa85e6,2},{0xa85f8,4},
        {0xa860c,4},{0xa869e,2},{0xa86c0,8},{0xa86c8,2},{0xa86ca,2},
        {0xa86cc,2},{0xa8614,2},{0xa8610,4},{0xa861a,2},{0xa8616,4},
        {0xa8620,2},{0xa861c,4},{0xa8622,4},{0xa86ce,4},{0xa86da,4},
        {0xa86d2,8},{0xa85e8,16},{0xa8522,8},{0xa883f,1},{0xa85fc,16},
        {0xa8840,8},{0xa8848,8},{0xa86a0,16},{0xa8850,2},{0xa8510,8},
        {0xa86b0,16},{0xa8852,2}
    };
    for(unsigned i=0;i<sizeof fields/sizeof fields[0];++i)memcpy(c+fields[i].offset,c+fields[i].offset+0x4ab4,fields[i].bytes);
    c[0xa851d]=0;
}
static void packed(unsigned char*out,uint32_t r,uint32_t b,unsigned shift){
    out[0]=(unsigned char)(r>>shift);out[1]=(unsigned char)(((r>>(shift+4))&0xf0)|((b>>shift)&15));out[2]=(unsigned char)(b>>(shift+4));
}
static uint32_t sum(const unsigned char*c,unsigned width,unsigned x,unsigned y,unsigned side,unsigned channel){
    uint32_t result=0;
    for(unsigned dy=0;dy<side;++dy)for(unsigned dx=0;dx<side;++dx)result+=u32(c+0xf450+40*((y*side+dy)*width+x*side+dx)+channel);
    return result;
}
static unsigned char coarse(uint32_t value,unsigned side){
    unsigned shift=side==4?41:39;uint32_t limit=side==4?0x63fff:0x18fff;
    return value>limit?255:(unsigned char)(((uint64_t)value*UINT64_C(0x51eb851f))>>shift);
}
uint32_t hb_debug_process(unsigned char*c,unsigned char*w,size_t bytes){
    if(!c||!w||bytes<HB_DEBUG_WORKSPACE_BYTES||!lengths_ok(c)||!no_file(c))return HB_PREP_UNSUPPORTED;
    unsigned width=u32(c+0x18),height=u32(c+0x1c),n=u32(c+0x28);
    if(width>64||height>64||n!=width*height)return HB_PREP_UNSUPPORTED;
    memset(c+0xa8bc0,0,0x3fb);memset(c+0xa8fbb,0,0x3004);
    memset(c+0xabfbf,0,0xc04);memset(c+0xacbc3,0,0x200);
    carry(c);
    unsigned a=u16(c+0xa8ba8),b=u16(c+0xa8baa);
    w16(c+0xa8bc0,(uint16_t)a);memcpy(c+0xa8bc2,c+0xa8510,a);
    w16(c+0xa8bc2+a,(uint16_t)b);memcpy(c+0xa8bc4+a,c+0xa8518+a,b);
    hb_debug_encode(c);
    c[0xadb06]=(unsigned char)height;c[0xadb07]=(unsigned char)width;w16(c+0xadb08,0x80c);memset(c+0xadb0a,0,0x3000);
    for(unsigned i=0;i<n;++i)packed(c+0xadb0a+3*i,u32(c+0xf450+40*i),u32(c+0xf458+40*i),4);
    memcpy(c+0xa8fbb,c+0xadb06,0x3004);memset(w,0,HB_DEBUG_WORKSPACE_BYTES);w16(w+2,0x80c);
    unsigned scale=n>1024?2:1;w[0]=(unsigned char)(height/scale);w[1]=(unsigned char)(width/scale);
    if(scale==1){for(unsigned i=0;i<n;++i)packed(w+4+3*i,u32(c+0xf450+40*i),u32(c+0xf458+40*i),4);}
    else for(unsigned y=0;y<height/2;++y)for(unsigned x=0;x<width/2;++x)packed(w+4+3*(y*(width/2)+x),sum(c,width,x,y,2,0),sum(c,width,x,y,2,8),6);
    memcpy(c+0xabfbf,w,HB_DEBUG_WORKSPACE_BYTES);
    scale*=2;
    for(unsigned y=0;y<height/scale;++y)for(unsigned x=0;x<width/scale;++x){unsigned i=y*(width/scale)+x;c[0xacbc3+2*i]=coarse(sum(c,width,x,y,scale,0),scale);c[0xacbc4+2*i]=coarse(sum(c,width,x,y,scale,8),scale);}
    return hb_debug_userdump_no_file(c);
}
