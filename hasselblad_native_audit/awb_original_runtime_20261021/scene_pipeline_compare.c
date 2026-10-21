/* SPDX-License-Identifier: MIT
 * Original-prepared boundary test: compare each owned normal-scene stage,
 * then independently compare the complete owned normal-slot scene body.
 * Surrounding preparation stages still use original firmware functions.
 */
#include "hb_stat_prepare.h"
#include "hb_scene_filter.h"
#include "hb_scene_optimizer.h"
#include "hb_scene_candidates.h"
#include "hb_scene_controller.h"
#ifdef HB_ATMOSPHERE_PIPELINE
#include "hb_atmosphere.h"
static unsigned atmosphere_calls;
#endif
#ifdef HB_HISTORY_PIPELINE
#include "hb_history.h"
static unsigned history_calls;
#endif
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,E=0x1ce90,K=1502800,R=1000,P=0x20200,M=0x100};
static uint32_t u32(const void *p){uint32_t v;memcpy(&v,p,4);return v;}
static uint16_t u16(const void *p){uint16_t v;memcpy(&v,p,2);return v;}
static void w32(void *p,uint32_t v){memcpy(p,&v,4);}
static void w16(void *p,uint16_t v){memcpy(p,&v,2);}
static void wf(void *p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static unsigned mismatches,comparisons,filter_calls,optimizer_calls,weighted_candidates,filter_removed,accumulation_calls,spectral_calls,owned_scene_calls,full_scene_calls;
#ifdef HB_ORIGINAL_TAIL
static unsigned tail_calls,tail_errors;
#endif
static void same(const char *s,unsigned t,const void*a,const void*b,size_t n){
    ++comparisons;if(!memcmp(a,b,n))return;++mismatches;
    if(mismatches<=12){const unsigned char *x=a,*y=b;size_t k=0;while(k<n&&x[k]==y[k])++k;
        printf("{\"pipeline_mismatch\":\"%s\",\"frame\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,k,x[k],y[k]);}
}
static void capture(const char *dir,unsigned frame,const char *stage,const void *p,size_t n){
    char path[4096];if(snprintf(path,sizeof path,"%s/frame_%02u_%s.bin",dir,frame,stage)>=(int)sizeof path)_exit(64);
    FILE *f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
static uint32_t (*spec)(int,int),(*weight)(int,const void*,int,int),(*accum)(int,int,int,const void*,const void*,uint32_t,int);
static uint32_t (*filter)(int,int,int,int),(*opt)(int,int,int,const void*);
static unsigned char *scratch;
static uint32_t hybrid_normal(unsigned char *ctx,unsigned char *cfg,unsigned frame){
    if(u16(ctx+0x3da54)||u16(ctx+0x3da56))return HB_PREP_UNSUPPORTED;
    uint32_t maximum=0;
    for(unsigned slot=0;slot<2;++slot){
        if(u16(ctx+0x3da50+2*slot)){
            memcpy(scratch,ctx,C);uint32_t st=spec(0,(int)slot),ost=hb_scene_spec_weight(scratch,cfg,slot);++spectral_calls;
            same("spec_status",frame,&st,&ost,4);same("spec_context",frame,ctx,scratch,C);memcpy(ctx,scratch,C);if(ost)return ost;
            unsigned n=cfg[0x1540+slot*0xa278],eligible=0,metric=0;
            unsigned char *params=cfg+0x154c+slot*0xa278;
            for(unsigned scene=0;scene<n;++scene){
                unsigned char *p=params+508*scene;uint32_t ev=ctx[0x3761c];
                if(u32(p)>ev||u32(p+4)<ev)continue;
                eligible=1;size_t off=slot*0x10188+scene*0x2020;ctx[0x3dacc+off]=1;
                memcpy(scratch,ctx,C);st=weight(0,p,(int)scene,(int)slot);ost=hb_candidate_weight(scratch,cfg,p,scene,slot);++weighted_candidates;
                same("weight_status",frame,&st,&ost,4);same("weight_context",frame,ctx,scratch,C);memcpy(ctx,scratch,C);if(ost)return ost;
                unsigned before=0,after=0;
                for(unsigned i=0;i<u32(ctx+0x28);++i)before+=u16(ctx+0x3dace +off+2*i)!=0;
                memcpy(scratch,ctx,C);uint32_t a=filter(0,(int)scene,(int)slot,cfg[0x1548+slot*0xa278]);
                /* Save original output, restore same input, and execute owned. */
                unsigned char *reference=malloc(C);if(!reference)_exit(71);memcpy(reference,ctx,C);memcpy(ctx,scratch,C);
                uint32_t b=hb_scene_filter(ctx,scene,slot,cfg[0x1548+slot*0xa278]);++filter_calls;
                same("filter_status",frame,&a,&b,4);same("filter_context",frame,reference,ctx,C);free(reference);
                if(b)return b;
                for(unsigned i=0;i<u32(ctx+0x28);++i)after+=u16(ctx+0x3dace +off+2*i)!=0;
                filter_removed+=before-after;
                memcpy(scratch,ctx,C);st=accum(0,(int)scene,(int)slot,p,cfg+slot*0xa278+0xa594,u32(cfg+slot*0xa278+0x1544),cfg[slot*0xa278+0x154a]);
                ost=hb_candidate_accumulate(scratch,p,cfg+slot*0xa278+0xa594,scene,slot,u32(cfg+slot*0xa278+0x1544),cfg[slot*0xa278+0x154a]);++accumulation_calls;
                same("accum_status",frame,&st,&ost,4);same("accum_context",frame,ctx,scratch,C);memcpy(ctx,scratch,C);if(ost)return ost;
                uint32_t m=u32(ctx+0x3fae4+off);if(m>metric)metric=m;
            }
            if(n){
                if(!eligible)return 40;
                memcpy(scratch,ctx,C);uint32_t a=opt(0,(int)slot,(int)n,params);
                unsigned char *reference=malloc(C);if(!reference)_exit(71);memcpy(reference,ctx,C);memcpy(ctx,scratch,C);
                uint32_t b=hb_scene_optimizer(ctx,slot,n,params);++optimizer_calls;
                same("prepared_optimizer_status",frame,&a,&b,4);same("prepared_optimizer_context",frame,reference,ctx,C);free(reference);
                if(b)return b;
            }
            unsigned char *m=ctx+0x841cc+slot*0x74;if(u32(m)<metric)w32(m,metric);
        }
        uint32_t m=u32(ctx+0x841cc+slot*0x74);maximum=m>(maximum&65535)?m:(maximum&65535);
    }
    for(unsigned slot=2;slot<4;++slot){uint32_t m=u32(ctx+0x841cc+slot*0x74);maximum=m>(maximum&65535)?m:(maximum&65535);}
    w16(ctx+0xb142c,(uint16_t)maximum);return 0;
}
int hb_run_scene_pipeline(void *h,unsigned char *ctx,unsigned char *e2,void *config,void *reawb,const char *dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    spec=sym(h,"scene_awb_scene_compute_spec_ct_weight");weight=(void*)(bias+0x4a7d00);accum=(void*)(bias+0x4a88a0);
    filter=(void*)(bias+0x4a8548);opt=(void*)(bias+0x4a8c48);
    uint32_t (*set)(int,void*)=sym(h,"awb_e2_main_set_stat"),(*parse)(int,void*,void*)=sym(h,"awb_e2_main_get_stat_parse");
    uint32_t (*import)(int,void*,void*)=sym(h,"scene_awb_set_stat"),(*auto_proc)(int)=sym(h,"scene_awb_stat_auto_proc");
    uint32_t (*scene_proc)(int)=sym(h,"scene_awb_scene_proc");
    const char *before_names[]={"scene_awb_user_proc","scene_awb_sync_roi_proc","scene_awb_roi_proc"};
    const char *after_names[]={"scene_awb_spec_sensor_proc","scene_awb_parsing_proc","scene_awb_detect_proc","scene_awb_face_proc"};
    uint32_t (*before[3])(int),(*after[4])(int);
    for(unsigned i=0;i<3;++i)before[i]=sym(h,before_names[i]);for(unsigned i=0;i<4;++i)after[i]=sym(h,after_names[i]);
    unsigned char *input=calloc(1,0x4118),*parsed=calloc(1,P),*meta=calloc(1,M),*start=malloc(C),*reference=malloc(C),*owned=malloc(C),*cfgcopy=malloc(K),*rr=malloc(R);
    scratch=malloc(C);if(!input||!parsed||!meta||!start||!reference||!owned||!cfgcopy||!rr||!scratch)return 71;
    memcpy(cfgcopy,config,K);if(reawb)memcpy(rr,reawb,R);
    const unsigned rows[7]={15,25,35,45,55,35,20};unsigned states[7]={0},frames=0,active_slots=0;
    for(unsigned t=0;t<7;++t){
        memset(input,0,0x4118);w32(input,u32(e2+0x4120));w32(input+4,0x4118);w32(input+8,t+1);w32(input+12,u32(e2+0x412c));
        for(unsigned i=0;i<1024;++i){
            unsigned row=(i%17==0)?(rows[t]+12)%81:rows[t];uint32_t r=u32(ctx+0x348+row*16),b=u32(ctx+0x34c+row*16),g=2048+(i%7)*64;
            unsigned char *s=input+16+16*i;w16(s,(uint16_t)((g<<12)/r));w16(s+2,(uint16_t)g);w16(s+4,(uint16_t)g);w16(s+6,(uint16_t)((g<<12)/b));s[8]=t==5?9:255;
        }
        capture(dir,t,"native_input",input,0x4118);
        uint32_t st=set(0,input);if(st){printf("{\"pipeline_blocked\":\"set\",\"status\":%u}\n",st);return 2;}
        st=parse(0,parsed,meta);if(!st)st=import(0,parsed,meta);
        if(st){printf("{\"pipeline_blocked\":\"parse_import\",\"status\":%u}\n",st);return 2;}
        capture(dir,t,"e2_after_parse",e2,E);capture(dir,t,"parsed_input",parsed,P);capture(dir,t,"metadata",meta,M);
        wf(ctx+0x990d4,8.0f+(float)(t%3));w32(ctx+0x990e4,16);wf(ctx+0x990e8,1024);
        for(unsigned j=0;j<16;++j)wf(ctx+0x990ec+4*j,64);
        st=before[0](0);if(st){printf("{\"pipeline_blocked\":\"user\",\"status\":%u}\n",st);return 2;}
        memset(ctx+0xa8510,0,0x34c);memset(ctx+0xf450,0,0x75af8);
        for(unsigned j=1;j<3;++j){st=before[j](0);if(st){printf("{\"pipeline_blocked\":\"%s\",\"status\":%u}\n",before_names[j],st);return 2;}}
        capture(dir,t,"before_auto",ctx,C);
        memcpy(owned,ctx,C);uint32_t a=auto_proc(0),b=hb_stat_auto(owned,config);
        same("chain_auto_status",t,&a,&b,4);same("chain_auto_context",t,ctx,owned,C);
        capture(dir,t,"after_auto_original",ctx,C);capture(dir,t,"after_auto_owned",owned,C);
        if(a)return 2;
        for(unsigned j=0;j<4;++j){st=after[j](0);if(st){printf("{\"pipeline_blocked\":\"%s\",\"status\":%u}\n",after_names[j],st);return 2;}}
        printf("{\"pipeline_frame\":%u,\"gates\":[%u,%u,%u,%u]}\n",t,u16(ctx+0x3da50),u16(ctx+0x3da52),u16(ctx+0x3da54),u16(ctx+0x3da56));
        active_slots+=(u16(ctx+0x3da50)!=0)+(u16(ctx+0x3da52)!=0);
        capture(dir,t,"before_scene",ctx,C);
        memcpy(start,ctx,C);a=scene_proc(0);memcpy(reference,ctx,C);memcpy(ctx,start,C);
        b=hybrid_normal(ctx,config,t);same("hybrid_controller_status",t,&a,&b,4);same("hybrid_controller_context",t,reference,ctx,C);
        capture(dir,t,"after_scene_original",reference,C);capture(dir,t,"after_scene_hybrid",ctx,C);
        memcpy(ctx,start,C);b=hb_normal_scene(ctx,config);++owned_scene_calls;
        same("owned_normal_scene_status",t,&a,&b,4);same("owned_normal_scene_context",t,reference,ctx,C);
        capture(dir,t,"after_scene_owned",ctx,C);
        memcpy(ctx,start,C);b=hb_scene_process(ctx,config,NULL,0);++full_scene_calls;
        same("owned_full_scene_status",t,&a,&b,4);same("owned_full_scene_context",t,reference,ctx,C);
        capture(dir,t,"after_scene_full_owned",ctx,C);
#ifdef HB_ORIGINAL_TAIL
        /* Original downstream baseline; optional history boundary replacement. */
        const char *tail_names[]={"scene_awb_hist_proc","scene_awb_atmos_proc","scene_awb_post_proc","scene_awb_reawb_proc"};
        for(unsigned j=0;j<4;++j){
#ifdef HB_HISTORY_PIPELINE
            if(j==0)memcpy(owned,ctx,C);
#ifdef HB_ATMOSPHERE_PIPELINE
            if(j==1)memcpy(owned,ctx,C);
#endif
#endif
            uint32_t (*tail)(int)=sym(h,tail_names[j]);uint32_t ts=tail(0);++tail_calls;tail_errors+=ts!=0;
            printf("{\"original_tail_frame\":%u,\"stage\":\"%s\",\"status\":%u}\n",t,tail_names[j],ts);
            char name[128];snprintf(name,sizeof name,"after_original_%s",tail_names[j]);capture(dir,t,name,ctx,C);
#ifdef HB_HISTORY_PIPELINE
            if(j==0){uint32_t hs=hb_history_process(owned,config);++history_calls;
                same("owned_history_status",t,&ts,&hs,4);same("owned_history_context",t,ctx,owned,C);
                capture(dir,t,"after_history_owned",owned,C);memcpy(ctx,owned,C);if(hs)break;}
#endif
#ifdef HB_ATMOSPHERE_PIPELINE
            if(j==1){uint32_t as=hb_atmosphere_process(owned,config,NULL);++atmosphere_calls;
                same("owned_atmosphere_status",t,&ts,&as,4);same("owned_atmosphere_context",t,ctx,owned,C);
                capture(dir,t,"after_atmosphere_owned",owned,C);memcpy(ctx,owned,C);if(as)break;}
#endif
            if(ts)break;
        }
        if(reawb)capture(dir,t,"after_tail_reawb_handle",reawb,R);
#endif
        states[t]=a;++frames;
    }
    same("pipeline_config_immutable",0,config,cfgcopy,K);
#ifndef HB_ORIGINAL_TAIL
    if(reawb)same("pipeline_passive_reawb_immutable",0,reawb,rr,R);
#endif
    if(reawb)capture(dir,7,"passive_reawb_after",reawb,R);
    unsigned ok=!mismatches&&frames==7&&active_slots&&optimizer_calls&&filter_calls&&full_scene_calls==7;
#ifdef HB_ORIGINAL_TAIL
    ok=ok&&tail_calls==28&&!tail_errors;
#ifdef HB_HISTORY_PIPELINE
    ok=ok&&history_calls==7;
#ifdef HB_ATMOSPHERE_PIPELINE
    ok=ok&&atmosphere_calls==7;
#endif
#endif
#endif
    printf("{\"event\":\"original_prepared_owned_scene_stage\",\"all_passed\":%s,\"mismatches\":%u,\"comparisons\":%u,\"frames\":%u,"
           "\"active_normal_slots\":%u,\"weighted_candidates\":%u,\"filter_calls\":%u,\"filter_removed\":%u,\"optimizer_calls\":%u,"
           "\"accumulation_calls\":%u,\"spectral_calls\":%u,\"owned_scene_calls\":%u,\"normal_scene_body_owned\":true,"
           "\"full_scene_calls\":%u,\"scene_stage_owned\":true,\"all_scene_slots_implemented\":true,"
#ifdef HB_ATMOSPHERE_PIPELINE
           "\"atmosphere_stage_owned\":true,\"atmosphere_calls\":7,"
#endif
#ifdef HB_HISTORY_PIPELINE
           "\"history_stage_owned\":true,\"history_calls\":7,\"original_tail_baseline\":false,\"downstream_stages_owned\":false,\"passive_reawb_immutability_checked\":false,"
#elif defined(HB_ORIGINAL_TAIL)
           "\"original_tail_baseline\":true,\"downstream_stages_owned\":false,\"passive_reawb_immutability_checked\":false,"
#else
           "\"original_tail_baseline\":false,\"passive_reawb_immutability_checked\":true,"
#endif
           "\"statuses\":[%u,%u,%u,%u,%u,%u,%u],\"synthetic_frames\":true,\"historical_frames\":false,\"wholly_owned_controller\":false}\n",
           ok?"true":"false",mismatches,comparisons,frames,active_slots,weighted_candidates,filter_calls,filter_removed,optimizer_calls,
           accumulation_calls,spectral_calls,owned_scene_calls,full_scene_calls,states[0],states[1],states[2],states[3],states[4],states[5],states[6]);
    return ok?0:1;
}
