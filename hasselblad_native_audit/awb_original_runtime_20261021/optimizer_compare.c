/* SPDX-License-Identifier: MIT
 * Same-process original/owned differential checks. Candidate inputs are
 * synthetic, layered onto authentic original-initialized configuration/state.
 * This does not reconstruct E2 frames or assert full estimator parity.
 */
#include "hb_scene_optimizer.h"
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { CTX_BYTES=920560, CFG_BYTES=1502800, MAX_SCENES=8, PARAM_STRIDE=508 };
typedef uint32_t (*opt_fn)(int,uint32_t,uint32_t,const void*);
typedef uint32_t (*ct_fn)(int,uint32_t,uint32_t,uint32_t*);
static uint32_t seed=0x6a202610,cases,failures,ct_calls,ct_failures,status72,no_change;
static uint32_t next_u32(void) {seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
static void put(unsigned char *p,uint32_t v) {memcpy(p,&v,4);}
static uint32_t get(const unsigned char *p) {uint32_t v;memcpy(&v,p,4);return v;}
static unsigned char *baseline,*before,*original_result,*config_copy;
static unsigned char params[MAX_SCENES*PARAM_STRIDE],params_copy[sizeof params];
static uint32_t one_case(opt_fn original,unsigned char *ctx,void *config,unsigned slot,unsigned count) {
    memcpy(before,ctx,CTX_BYTES);memcpy(params_copy,params,sizeof params);
    uint32_t native=original(0,slot,count,params);++cases;status72+=native==72;
    memcpy(original_result,ctx,CTX_BYTES);
    no_change+=memcmp(before,ctx,CTX_BYTES)==0;
    int ok=memcmp(config,config_copy,CFG_BYTES)==0 && memcmp(params,params_copy,sizeof params)==0;
    memcpy(ctx,before,CTX_BYTES);
    uint32_t owned=hb_scene_optimizer(ctx,slot,count,params);
    ok &= owned==native && memcmp(original_result,ctx,CTX_BYTES)==0;
    ok &= memcmp(config,config_copy,CFG_BYTES)==0 && memcmp(params,params_copy,sizeof params)==0;
    if(!ok) {
        if(failures<8) {
            size_t first=0;while(first<CTX_BYTES && original_result[first]==ctx[first])++first;
            fprintf(stderr,"optimizer mismatch case=%u slot=%u count=%u status=%u/%u first_offset=0x%zx\n",
                    cases,slot,count,native,owned,first);
        }
        ++failures;
    }
    /* Preserve the original state for the next sequence step, regardless of
     * comparison outcome. Both implementations always start from the same bytes. */
    memcpy(ctx,original_result,CTX_BYTES);
    return native;
}
static void common(unsigned char *ctx,unsigned slot) {
    memset(params,0,sizeof params);
    ctx[0x178+slot]=0;ctx[0x3761c]=50;put(ctx+0xb0c04,5000);
    put(ctx+0x840ec+slot*4,0);
    for(unsigned i=0;i<MAX_SCENES;++i) {
        unsigned off=slot*0x10188+i*0x2020;
        ctx[off+0x3dacc]=0;ctx[off+0x3fad8]=0;
        unsigned char *p=params+i*PARAM_STRIDE;
        put(p,0);put(p+4,100);p[9]=1;p[10]=10;p[11]=30;
        put(p+12,4000);put(p+16,6000);put(p+20,5000);
    }
}
static void candidate(unsigned char *ctx,unsigned slot,unsigned scene,int eligible,int valid,
                      uint32_t r,uint32_t b,uint32_t metric,uint32_t weight) {
    unsigned off=slot*0x10188+scene*0x2020;
    ctx[off+0x3dacc]=(unsigned char)eligible;ctx[off+0x3fad8]=(unsigned char)valid;
    put(ctx+off+0x3fad0,r);put(ctx+off+0x3fad4,b);
    put(ctx+off+0x3fae4,metric);put(ctx+off+0x3fae8,weight);
}
int hb_run_optimizer_tests(void *h,unsigned char *ctx,void *config,const char *private_dir) {
    (void)private_dir;
    void *leaf=dlsym(h,"scene_awb_result_recalib_unit");
    ct_fn original_ct=(ct_fn)dlsym(h,"scene_awb_compute_color_temperature_no_check");
    if(!leaf||!original_ct)return 3;
    /* ELF-relative address, using an exported symbol as the load-bias anchor. */
    opt_fn original=(opt_fn)((uintptr_t)leaf-0x4a39a0+0x4a8c48);
    baseline=malloc(CTX_BYTES);before=malloc(CTX_BYTES);original_result=malloc(CTX_BYTES);config_copy=malloc(CFG_BYTES);
    if(!baseline||!before||!original_result||!config_copy)return 71;
    memcpy(baseline,ctx,CTX_BYTES);memcpy(config_copy,config,CFG_BYTES);
    for(unsigned i=0;i<1024;++i) {
        uint32_t r=next_u32(),b=next_u32(),temperature=0xfeedface;
        if(i<81) {r=get(ctx+0x348+i*16);b=get(ctx+0x34c+i*16);}
        else if(i&1u) {r=(r&32767)+1;b=(b&32767)+1;}
        memcpy(before,ctx,CTX_BYTES);
        uint32_t status=original_ct(0,r,b,&temperature);++ct_calls;
        if(status || temperature!=hb_scene_temperature(ctx,r,b) || memcmp(before,ctx,CTX_BYTES))++ct_failures;
    }
    for(unsigned metric=0;metric<=400;++metric) {
        memcpy(ctx,baseline,CTX_BYTES);common(ctx,0);
        candidate(ctx,0,0,1,1,4096+metric*3,7000-metric,metric,1+(metric%19));
        if(metric&1u) candidate(ctx,0,1,1,0,0,0,0,0);
        one_case(original,ctx,config,0,2);
    }
    for(unsigned i=0;i<512;++i) {
        memcpy(ctx,baseline,CTX_BYTES);
        unsigned slot=i%4,count=i%9;common(ctx,slot);
        put(ctx+0xb0c04,2000+next_u32()%8001);ctx[0x3761c]=(unsigned char)(next_u32()%101);
        ctx[0x178+slot]=(i%19==0);put(ctx+0x840ec+slot*4,next_u32()%401);
        for(unsigned j=0;j<count;++j) {
            uint32_t r=next_u32(),b=next_u32(),weight=next_u32();
            if(i%4) {r=1000+r%20000;b=1000+b%20000;weight%=1025;}
            candidate(ctx,slot,j,next_u32()%3!=0,next_u32()%3!=0,r,b,next_u32()%450,weight);
            unsigned char *p=params+j*PARAM_STRIDE;
            p[9]=(i%7!=0);p[10]=(unsigned char)(next_u32()%101);p[11]=(unsigned char)(next_u32()%101);
            put(p+12,2000+next_u32()%3001);put(p+16,5000+next_u32()%5001);
            put(p+20,2000+next_u32()%8001);
            if(i%23==0) put(p+4,0); /* ARM UDIV zero denominator behaviour. */
        }
        one_case(original,ctx,config,slot,count);
    }
    /* Seven stateful optimizer calls: synthetic boundary sequence, explicitly
     * not the historical seven authentic E2 frames or full AWB pipeline. */
    uint32_t sequence_status[7];memcpy(ctx,baseline,CTX_BYTES);
    for(unsigned frame=0;frame<7;++frame) {
        common(ctx,0);
        if(frame!=0 && frame!=4) candidate(ctx,0,0,1,1,4800+frame*100,6500-frame*100,100+frame,frame==3?0:10);
        if(frame==2 || frame==3 || frame==6) candidate(ctx,0,1,1,0,0,0,0,0);
        sequence_status[frame]=one_case(original,ctx,config,0,2);
    }
    int ok=failures==0 && ct_failures==0 && sequence_status[3]==72;
    printf("{\"event\":\"same_execution_optimizer_comparison\",\"optimizer_calls\":%u,"
           "\"optimizer_failures\":%u,\"temperature_calls\":%u,\"temperature_failures\":%u,"
           "\"whole_context_bytes_per_comparison\":%d,\"config_bytes_unchanged\":%d,"
           "\"status72_cases\":%u,\"unchanged_context_cases\":%u,"
           "\"seven_synthetic_step_statuses\":[%u,%u,%u,%u,%u,%u,%u],"
           "\"all_passed\":%s,\"authentic_e2_frames\":false,\"reawb_compared\":false,"
           "\"full_awb_validated\":false}\n",cases,failures,ct_calls,ct_failures,CTX_BYTES,CFG_BYTES,
           status72,no_change,sequence_status[0],sequence_status[1],sequence_status[2],sequence_status[3],
           sequence_status[4],sequence_status[5],sequence_status[6],ok?"true":"false");
    return ok?0:1;
}
