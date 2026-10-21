/* SPDX-License-Identifier: MIT
 * Owned numerical reconstruction from pinned original instruction behaviour.
 * All arithmetic below intentionally preserves unsigned 32-bit wraparound.
 */
#include "hb_scene_optimizer.h"
#include <string.h>
static uint32_t get32(const unsigned char *p) {uint32_t v;memcpy(&v,p,4);return v;}
static void put32(unsigned char *p,uint32_t v) {memcpy(p,&v,4);}
static uint32_t udiv32(uint32_t a,uint32_t b) {return b?a/b:0;}
static int signed_byte(uint32_t v) {return (v&255u)<128u?(int)(v&255u):(int)(v&255u)-256;}

uint32_t hb_scene_temperature(const unsigned char *ctx,uint32_t r,uint32_t b) {
    uint32_t best=UINT32_C(0x80000000), temperature=0;
    for(uint32_t i=0;i<81;++i) {
        uint32_t dr=r-get32(ctx+0x348+i*16),db=b-get32(ctx+0x34c+i*16);
        uint32_t distance=dr*dr+db*db;
        if(distance<best) {best=distance;temperature=2000+i*100;}
    }
    return temperature;
}
static uint32_t metric_weight(uint32_t metric) {
    if(metric>=320) return 512;
    if(metric<41) return 16;
    uint32_t d=320-metric;
    uint32_t scaled=(UINT32_C(0x23000)-(d<<9)+(d<<4))>>3;
    return (uint32_t)(((uint64_t)scaled*UINT32_C(0x0ea0ea0f))>>33)&65535u;
}
uint32_t hb_scene_optimizer(unsigned char *ctx,uint32_t slot,uint32_t count,
                            const unsigned char *parameters) {
    slot &= 255u;count &= 255u;
    if(!count) return 0;
    uint32_t slot_offset=slot*UINT32_C(0x10188);
    uint32_t eligible_minus_one=255,valid=0;
    for(uint32_t i=0;i<count;++i) {
        uint32_t off=slot_offset+i*UINT32_C(0x2020);
        if(ctx[off+0x3dacc]) {++eligible_minus_one;valid += ctx[off+0x3fad8]!=0;}
    }
    int use_fallback=signed_byte(eligible_minus_one)>=1 && signed_byte(valid)>=1;
    uint32_t total_weight=0,observed_weight=0,total_r=0,total_b=0,observed_r=0,observed_b=0;
    for(uint32_t i=0;i<count;++i) {
        uint32_t off=slot_offset+i*UINT32_C(0x2020);
        if(!ctx[off+0x3dacc]) continue;
        if(ctx[off+0x3fad8]) {
            uint32_t metric=get32(ctx+off+0x3fae4);
            uint32_t weight=get32(ctx+off+0x3fae8)*metric_weight(metric);
            uint32_t r=get32(ctx+off+0x3fad0)*weight,b=get32(ctx+off+0x3fad4)*weight;
            uint32_t max_metric=get32(ctx+0x840ec+slot*4);
            if(max_metric<metric) put32(ctx+0x840ec+slot*4,metric);
            total_weight+=weight;observed_weight+=weight;
            total_r+=r;observed_r+=r;total_b+=b;observed_b+=b;
        } else if(use_fallback) {
            const unsigned char *p=parameters+i*508;
            uint32_t low=get32(p+12),high=get32(p+16);
            uint32_t lower=low-500,upper=high+500;
            if(lower<=2000) lower=2000;
            if((upper>>4)>=625) upper=10000;
            uint32_t current=get32(ctx+0xb0c04);
            if(p[9]!=1 || current<lower || current>upper || ctx[0x178+slot]) continue;
            uint32_t low_input=get32(p),high_input=get32(p+4);
            uint32_t delta_weight=(uint32_t)p[11]-(uint32_t)p[10];
            uint32_t weight=(uint32_t)p[10]+udiv32(delta_weight*((uint32_t)ctx[0x3761c]-low_input),high_input-low_input);
            if(current<low) {
                if(low!=lower) weight=udiv32(weight*(current-lower),low-lower);
            } else if(upper!=high && current>high) {
                weight=udiv32(weight*(upper-current),upper-high);
            }
            uint32_t shifted_weight=weight<<4;
            uint32_t ct_delta=get32(p+20)-2000;
            uint32_t table_offset=(uint32_t)(((uint64_t)ct_delta*UINT32_C(0x51eb851f))>>33)&UINT32_C(0x3ffffff0);
            total_weight+=shifted_weight;
            total_r+=get32(ctx+0x348+table_offset)*shifted_weight;
            total_b+=get32(ctx+0x34c+table_offset)*shifted_weight;
        }
    }
    if(!total_weight) return 0;
    if(!observed_weight) return 72;
    uint32_t r=total_r/total_weight,b=total_b/total_weight;
    uint32_t measured_r=observed_r/observed_weight,measured_b=observed_b/observed_weight;
    uint32_t out=slot_offset+UINT32_C(0x4dbcc);
    ctx[out]=1;
    put32(ctx+out+4,r);put32(ctx+out+8,4096);put32(ctx+out+12,b);
    put32(ctx+out+16,measured_r);put32(ctx+out+20,4096);put32(ctx+out+24,measured_b);
    put32(ctx+out+88,hb_scene_temperature(ctx,r,b));
    put32(ctx+out+92,hb_scene_temperature(ctx,measured_r,measured_b));
    put32(ctx+0x841cc+slot*0x74,get32(ctx+0x840ec+slot*4));
    /* Caller-side candidate-count updates deliberately remain outside here. */
    return 0;
}
