/* SPDX-License-Identifier: MIT
 * Exact pinned-firmware connected-component filter, including its linear
 * neighbor indices, signed 16-bit channel comparisons and scratch writes.
 */
#include "hb_scene_filter.h"
#include <string.h>
static uint32_t u32(const unsigned char *p){uint32_t x;memcpy(&x,p,4);return x;}
static uint16_t u16(const unsigned char *p){uint16_t x;memcpy(&x,p,2);return x;}
static int16_t s16(const unsigned char *p){int16_t x;memcpy(&x,p,2);return x;}
static void w16(unsigned char *p,uint16_t x){memcpy(p,&x,2);}
static int absdiff(int a,int b){int d=a-b;return d<0?-d:d;}
uint32_t hb_scene_filter(unsigned char *ctx,uint32_t scene,uint32_t slot,uint32_t factor){
    unsigned char *labels=ctx+0x7e0ec,*sizes=ctx+0x800ec,*stack=ctx+0x820ec;
    memset(labels,0,8192);memset(sizes,0,8192);memset(stack,0,8192);
    factor&=255;if(!factor)return 38;
    int count=(int16_t)u32(ctx+0x28);if(count<=0)return 0;
    uint32_t width=u32(ctx+0x18);
    uint16_t delta[8]={(uint16_t)(~width),(uint16_t)(0-width),(uint16_t)(1-width),65535,1,
                       (uint16_t)(width-1),(uint16_t)width,(uint16_t)(width+1)};
    unsigned char *weight=ctx+0x3dace +(slot&255)*0x10188+(scene&255)*0x2020;
    uint16_t group=0;
    for(int i=0;i<count;++i){
        if(!u16(weight+2*i)||u16(labels+2*i))continue;
        ++group;int top=0;w16(stack,(uint16_t)i);w16(labels+2*i,group);w16(sizes+2*group,(uint16_t)(u16(sizes+2*group)+1));
        while(top!=-1){
            uint16_t index=u16(stack+2*top--);const unsigned char *record=ctx+0xf450+40*(int16_t)index;
            int r=s16(record),b=s16(record+8);
            int threshold=(int16_t)(u32(ctx+0x350+16*u32(record+16))/factor);
            for(unsigned j=0;j<8;++j){
                uint16_t other=(uint16_t)(index+delta[j]);
                if((int16_t)other<0||(int16_t)other>=count||u16(labels+2*other)||!u16(weight+2*other))continue;
                const unsigned char *candidate=ctx+0xf450+40*other;
                if(absdiff(b,s16(candidate+8))>=threshold||absdiff(r,s16(candidate))>=threshold)continue;
                w16(stack+2*(++top),other);w16(labels+2*other,group);w16(sizes+2*group,(uint16_t)(u16(sizes+2*group)+1));
            }
        }
    }
    for(int i=0;i<count;++i)if(u16(weight+2*i)&&s16(sizes+2*s16(labels+2*i))<=3)w16(weight+2*i,0);
    return 0;
}
