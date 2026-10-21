/* SPDX-License-Identifier: MIT
 * Compare full original entry against owned entry + unmodified original
 * remainder. Early-return cases are wholly owned; continuation is explicit. */
#include "hb_run_entry.h"
#include "hb_stat_prepare.h"
#ifdef HB_WHITE_LUT_ENTRY
#include "hb_white_lut.h"
#endif
#ifdef HB_USER_PREPARE_ENTRY
#include "hb_user_prepare.h"
uint32_t hb_original_user_remainder(uintptr_t);
#endif
#ifdef HB_USER_E_ND_ENTRY
#include "hb_user_e_nd.h"
#include "user_e_nd_fixtures.h"
#endif
#ifdef HB_USER_MANUAL_ENTRY
#include "hb_user_manual.h"
#include "user_manual_fixtures.h"
static hb_temperature_model manual_model;
#endif
#ifdef HB_USER_CONTROLS_ENTRY
#include "hb_user_controls.h"
#include "user_controls_fixtures.h"
#endif
#ifdef HB_USER_FINISH_ENTRY
#include "hb_user_finish.h"
#include "user_finish_fixtures.h"
#endif
#ifdef HB_STAT_DIFFERENCE_ENTRY
#include "hb_run_dispatch.h"
static unsigned dispatch_counts[6];
#endif
#ifdef HB_ROI_ENTRY
#include "hb_roi.h"
#include "roi_fixtures.h"
static unsigned roi_calls,roi_errors;
#endif
#ifdef HB_ROI_SYNC_ENTRY
#include "hb_roi_sync.h"
#include "roi_sync_fixtures.h"
static hb_roi_sync_model sync_model;
static unsigned sync_calls;
#endif
#ifdef HB_SENSOR_ENTRY
#include "hb_sensor.h"
#include "sensor_fixtures.h"
static unsigned sensor_calls,sensor_active_calls,original_statistics_calls;
#ifdef HB_STAT_AUTO_ENTRY
static unsigned owned_statistics_calls,statistics_unit,statistics_temperature;
#else
static uint32_t(*original_auto_statistics)(int);
#endif
#endif
#ifdef HB_PARSING_ENTRY
#include "hb_parsing.h"
#include "parsing_fixtures.h"
static unsigned parsing_calls,parsing_active_calls,parsing_errors;
#endif
#ifdef HB_AUTOMATIC_ENTRY
#include "hb_automatic.h"
#include "hb_diagnostics.h"
static unsigned char automatic_workspace[HB_DEBUG_WORKSPACE_BYTES];
static unsigned owned_tails,composed_calls,composed_guards,composed_recoveries,composed_early_nonzero,automatic_sequence,unsupported_checks,sequence_refresh,sequence_reuse;
static unsigned automatic_stages[HB_AUTO_STAGE_COUNT];
#endif
#ifdef HB_FACE_ENTRY
#include "hb_face.h"
#include "face_fixtures.h"
static unsigned face_calls,face_active,face_errors;
#endif
#ifdef HB_DETECT_ENTRY
#include "hb_detect.h"
#include "detect_fixtures.h"
static unsigned detect_calls,detect_errors,detect106,detect131,detect177,detect247;
#endif
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000,P=0x20200,M=0x100};
uint32_t hb_original_prepared_completion(uintptr_t,unsigned char*,uint32_t,uintptr_t);
static unsigned checks,failures,reasons[6],continued,early,native_calls,stateful_calls;
static unsigned white_errors,active_native,user_prefix_calls,user_errors,user_remainders,user_errors83,user_errors84,unit_accepted,unit_rejected;
static uint32_t rng=0xe0212026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
#ifdef HB_WHITE_LUT_ENTRY
static void synthetic_white_axes(unsigned char*k){
    /* The later statistics search uses the BASE count, so E-ND tables must
     * use the same count; fewer points leave stale segment indices. */
    unsigned n=k[0xc88];if(n>15)_exit(1);
    k[0xd7c]=3;
    for(unsigned axis=0;axis<3;++axis){unsigned char*p=k+0xd80+248*axis;wf(p,(float)axis*2);p[4]=(unsigned char)n;
        for(unsigned j=0;j<n;++j){const unsigned char*q=k+0xc8c+16*j;memcpy(p+8+16*j,q,16);w32(p+12+16*j,u32(q+4)+axis*250);w32(p+16+16*j,u32(q+8)+axis*200);}}
}
#endif
#ifdef HB_USER_PREPARE_ENTRY
static void synthetic_user_requests(unsigned char*c,unsigned t,unsigned faults){
    c[0xb1430]=1;c[0xb1434]=2;w16(c+0xb14c0,(uint16_t)(t%3));
    for(unsigned group=0;group<3;++group){unsigned char*p=c+(group==0?0xb1430:0xb1460+48*(group-1));p[0]=1;p[4]=2;
        for(unsigned j=0;j<2;++j){unsigned char*q=p+8+20*j;w32(q,j?2000:8000);w32(q+4,4096+group*64);w32(q+8,4096+group*32);w32(q+12,4096);w32(q+16,4096);}}
    c[0xb1d98]=1;w32(c+0xb1d9c,2);
    for(unsigned j=0;j<2;++j){unsigned char*p=c+0xb1da0+84*j;w32(p,j?2000:8000);for(unsigned v=0;v<10;++v){w32(p+4+4*v,4096+16*j);w32(p+44+4*v,4096);}}
    if(faults){if(t%4==0)w32(c+0xb143c,0);else if(t%4==1){w16(c+0xb14c0,2);w32(c+0xb146c+48,0);}else if(t%4==2)w32(c+0xb1dcc+84+4*9,0);}
}
#endif
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void same(const char*s,unsigned t,const void*a,const void*b,size_t n){++checks;if(!memcmp(a,b,n))return;++failures;if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;printf("{\"entry_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}}
static void dump(const char*dir,const char*kind,unsigned t,const void*p,size_t n){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",dir,kind,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*r,*input,*reference,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;unsigned missing_reawb;uint32_t(*run)(int);const char*dir;} test_state;
static hb_run_entry_result compare(test_state*s,unsigned t,int expected,unsigned capture){
    memcpy(s->input,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
#ifdef HB_STAT_DIFFERENCE_ENTRY
    void**reawb_global=(void**)(s->bias+0x791450);if(s->missing_reawb)*reawb_global=NULL;
#endif
    uint32_t a=s->run(0);
#ifdef HB_STAT_DIFFERENCE_ENTRY
    *reawb_global=s->r;
#endif
    memcpy(s->reference,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
    memcpy(s->c,s->input,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    hb_run_entry_result result;uint32_t api=hb_run_entry(s->c,s->k,&result),zero=0;same("entry_supported",t,&api,&zero,4);if(api)_exit(1);
    if(capture)dump(s->dir,"owned_entry_boundary",t,s->c,C);
    uint32_t b=result.status;if(result.action==HB_RUN_PREPARE){
#ifdef HB_WHITE_LUT_ENTRY
        b=hb_white_lut_prepare(s->c,s->k);
        if(capture)dump(s->dir,"owned_white_lut_boundary",t,s->c,C);
        if(!b){
#ifdef HB_USER_PREPARE_ENTRY
            ++user_prefix_calls;
#ifdef HB_USER_E_ND_ENTRY
#ifdef HB_USER_FINISH_ENTRY
            b=hb_user_process(s->c,s->k,&manual_model);
#else
            b=hb_user_prepare_calibration(s->c,s->k);
#ifdef HB_USER_MANUAL_ENTRY
            if(!b)b=hb_user_manual_samples(s->c,s->k,&manual_model);
#ifdef HB_USER_CONTROLS_ENTRY
            if(!b)b=hb_user_controls(s->c,s->k,&manual_model);
#endif
#endif
#endif
            if(s->input[0xb1f86]==1&&s->c[0xb1f86]==0){unit_accepted+=s->c[0x279]==1;unit_rejected+=s->c[0x279]==0;}
#else
            b=hb_user_prepare_prefix(s->c,s->k);
#endif
            if(capture)dump(s->dir,"owned_user_prefix_boundary",t,s->c,C);
#ifndef HB_USER_FINISH_ENTRY
            if(!b){++user_remainders;
#ifdef HB_USER_CONTROLS_ENTRY
                b=hb_original_user_remainder(s->bias+0x4b16d4);
#elif defined(HB_USER_MANUAL_ENTRY)
                b=hb_original_user_remainder(s->bias+0x4b16a8);
#elif defined(HB_USER_E_ND_ENTRY)
                b=hb_original_user_remainder(s->bias+0x4b162c);
#else
                b=hb_original_user_remainder(s->bias+0x4b1624);
#endif
            }
#endif
            if(!b){
#ifdef HB_STAT_DIFFERENCE_ENTRY
                hb_dispatch_result dispatch;uint32_t supported=hb_run_dispatch(s->c,s->k,s->missing_reawb?NULL:s->r,&dispatch);
                same("dispatch_supported",t,&supported,&zero,4);if(supported)_exit(1);
                if((unsigned)dispatch.action>=6)_exit(1);++dispatch_counts[dispatch.action];
                b=dispatch.status;if(capture)dump(s->dir,"owned_dispatch_boundary",t,s->c,C);
                if(dispatch.action!=HB_DISPATCH_RETURN){
                    static const uintptr_t entries[]={0,0x471f10,0x472274,0x471ff0,0x472100,0x4722b0};
                    uintptr_t entry=entries[dispatch.action];
#ifdef HB_ROI_ENTRY
                    if(dispatch.action==HB_DISPATCH_AUTO_REFRESH||dispatch.action==HB_DISPATCH_AUTO_REUSE){
#ifdef HB_ROI_SYNC_ENTRY
                        b=hb_roi_sync_process(s->c,s->k,&sync_model);++sync_calls;
#else
                        /* Earlier --roi-entry mode retains this explicit oracle
                         * dependency; --roi-sync-entry replaces it above. */
                        uint32_t(*sync)(int)=(void*)(s->bias+0x551920);b=sync(0);
#endif
                        if(!b){b=hb_roi_process(s->c,s->k);++roi_calls;roi_errors+=b!=0;}
                        entry=b?0x4722b0:dispatch.action==HB_DISPATCH_AUTO_REFRESH?0x471f30:0x472294;
                        if(capture)dump(s->dir,"owned_roi_boundary",t,s->c,C);
#ifdef HB_SENSOR_ENTRY
                        if(!b&&dispatch.action==HB_DISPATCH_AUTO_REFRESH){
#ifdef HB_STAT_AUTO_ENTRY
                            statistics_unit+=s->c[0x278]!=0;statistics_temperature+=s->c[0x2f4]!=0;
                            b=hb_stat_auto_complete(s->c,s->k);++owned_statistics_calls;
#else
                            b=original_auto_statistics(0);++original_statistics_calls;
#endif
                            if(!b){b=hb_sensor_process(s->c,s->k);++sensor_calls;sensor_active_calls+=s->k[0x139e2c]!=0;}
                            entry=b?0x4722b0:0x471f50;
                            if(capture)dump(s->dir,"owned_sensor_boundary",t,s->c,C);
#ifdef HB_PARSING_ENTRY
                            if(!b){parsing_active_calls+=s->k[0x138748]==1;b=hb_parsing_process(s->c,s->k);++parsing_calls;parsing_errors+=b!=0;}
                            entry=b?0x4722b0:0x471f60;
                            if(capture)dump(s->dir,"owned_parsing_boundary",t,s->c,C);
#ifdef HB_DETECT_ENTRY
                            if(!b){b=hb_detect_process(s->c,s->k);++detect_calls;detect_errors+=b!=0;detect106+=b==106;detect131+=b==131;detect177+=b==177;detect247+=b==247;if(b==HB_PREP_UNSUPPORTED){printf("{\"detect_guard_rejection\":%u}\n",t);_exit(1);}}
                            entry=b?0x4722b0:0x471f70;
                            if(capture)dump(s->dir,"owned_detection_boundary",t,s->c,C);
#ifdef HB_FACE_ENTRY
                            if(!b){face_active+=s->k[0x16446c]&&(s->c[0xdb50]||s->c[0xe0bb0]==1);b=hb_face_process(s->c,s->k);++face_calls;face_errors+=b!=0;if(b==HB_PREP_UNSUPPORTED){printf("{\"face_guard_rejection\":%u}\n",t);_exit(1);}}
                            entry=b?0x4722b0:0x471f80;
                            if(capture)dump(s->dir,"owned_face_boundary",t,s->c,C);
#endif
#endif
#endif
                        }
#endif
                    }
#endif
#ifdef HB_AUTOMATIC_ENTRY
                    if(dispatch.action==HB_DISPATCH_AUTO_REFRESH||dispatch.action==HB_DISPATCH_AUTO_REUSE||dispatch.action==HB_DISPATCH_COMPLETE_ERROR){
                        hb_automatic_inputs inputs={&manual_model,&sync_model,automatic_workspace,sizeof automatic_workspace};
                        hb_automatic_trace trace={.failed_stage=HB_AUTO_STAGE_COUNT};
                        b=hb_automatic_tail(s->c,s->k,s->missing_reawb?NULL:s->r,&inputs,
                            dispatch.action==HB_DISPATCH_AUTO_REFRESH?HB_AUTO_REFRESH_TAIL:dispatch.action==HB_DISPATCH_AUTO_REUSE?HB_AUTO_REUSE_TAIL:HB_AUTO_ERROR_TAIL,b,&trace);++owned_tails;
                        if(b==HB_PREP_UNSUPPORTED){printf("{\"automatic_tail_guard\":%u,\"stage\":%u}\n",t,trace.failed_stage);_exit(1);}
                    }else
#endif
                    {++continued;b=hb_original_prepared_completion(s->bias+entry,s->c,b,s->bias+0x791348);}
                }
#else
                ++continued;b=hb_original_prepared_completion(s->bias+0x471e78,s->c,0,s->bias+0x791348);
#endif
            }else{++user_errors;user_errors83+=b==83;user_errors84+=b==84;}
#else
            ++continued;b=hb_original_prepared_completion(s->bias+0x471e64,s->c,0,s->bias+0x791348);
#endif
        }else ++white_errors;
#else
        ++continued;b=hb_original_prepared_completion(s->bias+0x471e50,s->c,0,s->bias+0x791348);
#endif
    }else ++early;
    if((unsigned)result.reason>=6)_exit(1);++reasons[result.reason];
    same("run_status",t,&a,&b,4);same("run_context",t,s->reference,s->c,C);same("run_config",t,s->kr,s->k,K);same("run_reawb",t,s->rr,s->r,R);
    if(expected>=0){unsigned want=(unsigned)expected,actual=result.reason;same("entry_reason",t,&actual,&want,4);}
    if(capture){dump(s->dir,"run_input",t,s->input,C);dump(s->dir,"run_original",t,s->reference,C);dump(s->dir,"run_owned_entry_original_remainder",t,s->c,C);dump(s->dir,"run_config_input",t,s->ki,K);}
#ifdef HB_AUTOMATIC_ENTRY
    memcpy(s->c,s->input,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    hb_automatic_inputs inputs={&manual_model,&sync_model,automatic_workspace,sizeof automatic_workspace};hb_automatic_trace trace;
    if(u32(s->input+0x194)<2){
        uint32_t full=hb_run_automatic(s->c,s->k,s->missing_reawb?NULL:s->r,&inputs,&trace);++composed_calls;
        if(full==HB_PREP_UNSUPPORTED){printf("{\"automatic_guard\":%u,\"stage\":%u}\n",t,trace.failed_stage);_exit(1);}
        same("composed_status",t,&a,&full,4);same("composed_context",t,s->reference,s->c,C);same("composed_config",t,s->kr,s->k,K);same("composed_reawb",t,s->rr,s->r,R);same("composed_entry_reason",t,&result.reason,&trace.entry.reason,sizeof result.reason);
        for(unsigned j=0;j<HB_AUTO_STAGE_COUNT;++j)automatic_stages[j]+=(trace.stages>>j)&1;
        if(t>=11000&&t<11096){sequence_refresh+=trace.dispatch.action==HB_DISPATCH_AUTO_REFRESH;sequence_reuse+=trace.dispatch.action==HB_DISPATCH_AUTO_REUSE;}
        composed_recoveries+=trace.completed&&trace.completion.preceding_status!=0;composed_early_nonzero+=!trace.completed&&full!=0;
        if(capture){dump(s->dir,"run_owned_composed",t,s->c,C);dump(s->dir,"run_trace",t,&trace,sizeof trace);}
    }else{
        memset(&trace,0xa5,sizeof trace);hb_automatic_trace before=trace;uint32_t full=hb_run_automatic(s->c,s->k,s->r,&inputs,&trace),want=HB_PREP_UNSUPPORTED;
        same("mode_guard_status",t,&full,&want,4);same("mode_guard_context",t,s->input,s->c,C);same("mode_guard_config",t,s->ki,s->k,K);same("mode_guard_reawb",t,s->ri,s->r,R);same("mode_guard_trace",t,&before,&trace,sizeof trace);composed_guards+=5;
        memcpy(s->c,s->reference,C);memcpy(s->k,s->kr,K);memcpy(s->r,s->rr,R);
    }
#endif
    return result;
}
int hb_run_entry_tests(void*h,unsigned char*c,unsigned char*e2,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;
    unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rbase[R];
    test_state s={.c=c,.k=k,.r=reawb,.input=malloc(C),.reference=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.input||!s.reference||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rbase,reawb,R);s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;s.run=sym(h,"scene_awb_lib_run");
#if defined(HB_SENSOR_ENTRY) && !defined(HB_STAT_AUTO_ENTRY)
    original_auto_statistics=sym(h,"scene_awb_stat_auto_proc");
#endif
#ifdef HB_ROI_SYNC_ENTRY
    hb_test_sync_model(&sync_model,s.bias);dump(dir,"sync_model",0,&sync_model,sizeof sync_model);
#endif
#ifdef HB_USER_MANUAL_ENTRY
    float manual_table[124];memcpy(manual_table,(void*)(s.bias+0x6ce418),sizeof manual_table);manual_model.isotemperature_31x4=manual_table;dump(dir,"manual_isotemperature",0,manual_table,sizeof manual_table);
#endif
    for(unsigned kind=0;kind<6;++kind)for(unsigned t=0;t<(kind==5?256:128);++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        w32(c+0x170,1);w32(c+0x174,0);k[0x24]=1;c[0xb2150]=(unsigned char)t;c[0xd338]=1;w32(c+0x17c,0);w32(c+0x184,2+t%7);w32(c+0x180,t%3==0?UINT32_MAX:t);w32(k+0x70,t%3==0?UINT32_MAX:t%3==1?t:t-1);
        if(kind<5)for(unsigned i=0xb0b10;i<0xb0ff0;++i)c[i]=(unsigned char)next();
        if(kind==0)w32(c+0x170,t%3==0?0:t%3==1?2:UINT32_MAX);
        if(kind==1)w32(c+0x174,t%3==0?1:t%3==1?2:UINT32_MAX);
        if(kind==2){k[0x24]=t%3==0?0:t%3==1?2:255;for(unsigned i=0;i<5;++i)w32(k+0x28+4*i,next());w32(k+0x80,t%7==0?0:next());w16(c+0xa84dc,(uint16_t)next());}
        if(kind==3)w32(c+0x17c,t%2?1:UINT32_MAX);
        if(kind==4){w32(k+0x78,1);c[0xe0bb0]=0;w32(c+0x188,t%2?11:9);w32(c+0x9c1a0,10);wf(c+0x9c1a4,10000);w32(k+0x7c,100);}
        if(kind==5){w32(k+0x78,0);w32(c+0xb2020,2);c[0xd338]=0;c[0x990dc]=t%4;c[0xd4c1]=(t/4)%4;c[0xe0bb0]=(t/16)%3;c[0x279]=(t/8)%2;k[0x16e648]=(t/2)%2;k[0x16e940]=(t/3)%2;
            static const float v[]={0,0.009f,0.01f,0.010001f,0.5f,1,2,4};wf(c+0x990d8,v[t%8]);wf(c+0xd4bc,v[(t/8)%8]);
#ifdef HB_WHITE_LUT_ENTRY
            synthetic_white_axes(k);
#endif
        }
        compare(&s,kind*1000+t,(int)kind,t<2);
    }
    /* Numeric scheduling boundaries: zero/negative/NaN/infinite durations,
     * exact rate equality, uint32 conversion saturation and timestamp clamp. */
    static const float durations[]={0,-1,NAN,INFINITY,-INFINITY,99.999f,100,100.001f,4294967296.0f};
    for(unsigned t=0;t<144;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);k[0x24]=1;w32(c+0x174,0);w32(c+0x17c,0);w32(k+0x78,1);w32(k+0x7c,t%4==0?UINT32_MAX:100);c[0xe0bb0]=t%7==0?1:0;w32(c+0xb2020,2);w32(c+0x9c1a0,t%3==0?0:100);w32(c+0x188,t%3==1?99:101);wf(c+0x9c1a4,durations[t%9]);compare(&s,6000+t,-1,t<2);}
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);k[0x24]=1;w32(k+0x78,0);w32(c+0x184,3);w32(c+0x17c,0);w32(c+0xb2020,2);
    for(unsigned t=0;t<256;++t){w32(c+0x9c1a0,t+1);compare(&s,7000+t,-1,t<2);++stateful_calls;}
#ifdef HB_WHITE_LUT_ENTRY
    /* White-LUT failures return directly from the original controller,
     * without entering user processing or the shared completion suffix. */
    for(unsigned t=0;t<32;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        k[0x24]=1;k[0xc88]=3;w32(k+0x78,0);w32(c+0x17c,0);c[0x990dc]=0;c[0xd4c0]=0;c[0xd338]=1;
        for(unsigned j=0;j<3;++j){unsigned char*p=k+0xc8c+16*j;w32(p,t%3==2?(j==0?2000:j==1?6000:5000):2500+3000*j);
            w32(p+4,t%3==0?100+15000*j:8000+1000*j);w32(p+8,t%3==1?100+15000*j:9000+1000*j);w32(p+12,1400);}
        compare(&s,7500+t,HB_RUN_READY,t<2);
    }
#endif
#ifdef HB_USER_PREPARE_ENTRY
    for(unsigned t=0;t<96;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0xb2020,2);c[0xd338]=1;
        synthetic_user_requests(c,t,1);compare(&s,7600+t,HB_RUN_READY,t<4);
    }
#endif
#ifdef HB_USER_E_ND_ENTRY
    for(unsigned t=0;t<64;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0xb2020,2);c[0xd338]=1;
        hb_test_e_nd_request(c,k,t);c[0x990dc]=(unsigned char)(t%3);
        if(t%8==0)w16(c+0xb1f88,99);else if(t%8==1)w16(c+0xb1f8a,3);else if(t%8==2)w16(c+0xb1f92,0);else if(t%8==3)w16(c+0xb1f94,0);else if(t%8==4)c[0xb1f86]=2;
        compare(&s,7800+t,HB_RUN_READY,t<8);
    }
#endif
#ifdef HB_USER_MANUAL_ENTRY
    for(unsigned t=0;t<64;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0xb2020,2);c[0xd338]=1;
        hb_test_manual_request(c,k,t);compare(&s,7900+t,HB_RUN_READY,t<8);
    }
#endif
#ifdef HB_USER_CONTROLS_ENTRY
    for(unsigned t=0;t<72;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0xb2020,2);c[0xd338]=1;
        if(t<64)hb_test_control_request(c,k,t);else hb_test_control_failure(c,k,t-64);compare(&s,8200+t,HB_RUN_READY,t<8);
    }
#endif
#ifdef HB_USER_FINISH_ENTRY
    for(unsigned t=0;t<64;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
        k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0xb2020,2);c[0xd338]=1;
        hb_test_finish_request(c,t);compare(&s,8400+t,HB_RUN_READY,t<16);
    }
#endif
    /* Seven native E2 synthetic frames exercise full original dispatch after
     * the new owned entry. Downstream ownership is validated separately. */
    uint32_t(*set)(int,void*)=sym(h,"awb_e2_main_set_stat"),(*parse)(int,void*,void*)=sym(h,"awb_e2_main_get_stat_parse"),(*import)(int,void*,void*)=sym(h,"scene_awb_set_stat");
    unsigned char*input=calloc(1,0x4118),*parsed=calloc(1,P),*meta=calloc(1,M);if(!input||!parsed||!meta)return 71;
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0x184,0);w32(c+0xb2020,0);
#ifdef HB_WHITE_LUT_ENTRY
    synthetic_white_axes(k);
#endif
    const unsigned rows[]={15,25,35,45,55,35,20};
    for(unsigned t=0;t<7;++t){memset(input,0,0x4118);w32(input,u32(e2+0x4120));w32(input+4,0x4118);w32(input+8,t+1);w32(input+12,u32(e2+0x412c));
        for(unsigned i=0;i<1024;++i){unsigned row=i%17==0?(rows[t]+12)%81:rows[t];uint32_t r=u32(c+0x348+16*row),b=u32(c+0x34c+16*row),g=2048+(i%7)*64;unsigned char*p=input+16+16*i;w16(p,(uint16_t)((g<<12)/r));w16(p+2,(uint16_t)g);w16(p+4,(uint16_t)g);w16(p+6,(uint16_t)((g<<12)/b));p[8]=t==5?9:255;}
        uint32_t st=set(0,input);if(!st)st=parse(0,parsed,meta);if(!st)st=import(0,parsed,meta);if(st)return 2;
        wf(c+0x990d4,8.0f+(float)(t%3));w32(c+0x990e4,16);wf(c+0x990e8,1024);for(unsigned i=0;i<16;++i)wf(c+0x990ec+4*i,64);
#ifdef HB_WHITE_LUT_ENTRY
        c[0x990dc]=(t>=2&&t<=4)?1:0;wf(c+0x990d8,(float)t*1.125f);
        active_native+=c[0x990dc]==1;
#endif
#ifdef HB_USER_PREPARE_ENTRY
        if(t==0||t==3)synthetic_user_requests(c,t,0);
#endif
#ifdef HB_USER_E_ND_ENTRY
        if(t==0||t==3)hb_test_e_nd_request(c,k,t);
#endif
#ifdef HB_USER_MANUAL_ENTRY
        if(t==1||t==4){w16(c+0xb14f4,4);for(unsigned i=0;i<4;++i)w16(c+0xb14f6+2*i,(uint16_t)(i*3));}
#endif
#ifdef HB_USER_CONTROLS_ENTRY
        if(t==2){c[0xb14c4]=1;w32(c+0xb14c8,4300);}
        if(t==4){c[0xb14cc]=1;w32(c+0xb14d0,5500);wf(c+0xb14d4,-3.5f);}
        if(t==6){c[0xb14d8]=1;w32(c+0xb14dc,5100);w32(c+0xb14e0,4096);w32(c+0xb14e4,6200);}
#endif
#ifdef HB_USER_FINISH_ENTRY
        if(t==1||t==5){hb_test_finish_request(c,53);c[0xb1f85]=0;c[0xb14f1]=0;c[0xb1ff6]=0;}
        if(t==2){c[0xb1cf8]=1;w32(c+0xb1d54,1999);} /* release fixed result */
#endif
        dump(dir,"native_input",t,input,0x4118);hb_run_entry_result result=compare(&s,8000+t,HB_RUN_READY,1);if(result.action!=HB_RUN_PREPARE)return 2;++native_calls;
    }
#ifdef HB_STAT_DIFFERENCE_ENTRY
    unsigned char*dispatch_base=malloc(C),*dispatch_cfg=malloc(K),dispatch_r[R];if(!dispatch_base||!dispatch_cfg)return 71;
    memcpy(dispatch_base,c,C);memcpy(dispatch_cfg,k,K);memcpy(dispatch_r,reawb,R);
    for(unsigned t=0;t<48;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        /* Preserve the imported1024-sample geometry and calibrated gains. */
        w32(c+0xb2020,0);w32(c+0x194,t<32?t%2:t<40?2:3);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,0xffffffff);w32(c+0x2c,0);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=(unsigned char)(t%4==0);((unsigned char*)reawb)[0x1c]=0;
        w16(c+0xb6962,(uint16_t)(t%3));c[0xb6960]=0;w32(c+0xb6964,0xffffffff);
        if(t%4==1)w16(c+0xef3e,2);if(t%4==2){k[0x1531ad]=3;w32(c+0x9c1a0,4);}
        /* fixture arithmetic already compared directly; this set tests the
         * caller's mode selection, refresh/reuse and scratch-clearing edges. */
        compare(&s,9000+t,HB_RUN_READY,t<8||t==32||t==40);
    }
    /* Missing REAWB + disabled difference returns UINT32_MAX, which must
     * reach the normal error completion/recovery path in the outer caller. */
    for(unsigned t=0;t<4;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=t%2;
        k[0x1531a8]=t<2?0:1;k[0x1531ac]=t<2?1:0;w32(c+0x28,0);
        w16(c+0xb6962,1);c[0xb6960]=0;s.missing_reawb=1;
        compare(&s,9100+t,HB_RUN_READY,1);
    }
    s.missing_reawb=0;
#ifdef HB_ROI_ENTRY
    for(unsigned t=0;t<48;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w32(c+0x2c,0);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=(unsigned char)((t/6+t)%2);((unsigned char*)reawb)[0x1c]=0;
        /* Six kinds x both automatic paths, empty/stale input and zoom errors. */
        static const unsigned variants[]={0,0,1,4,11,12,56,6};
        hb_test_roi(c,k,t%6,variants[t/6]);k[0x16eae4]=0;
        compare(&s,9200+t,HB_RUN_READY,1);
    }
#ifdef HB_ROI_SYNC_ENTRY
    for(unsigned t=0;t<40;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w32(c+0x2c,0);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=(unsigned char)(t%2);((unsigned char*)reawb)[0x1c]=0;
        static const unsigned variants[]={0,1,2,10,11,36,39,40,44,46,52,54,55,58,59,61};
        hb_test_sync(c,k,&sync_model,variants[(t/2)%16]);c[0xd900]=0;
        if(t>=32)hb_test_roi(c,k,t%6,t<36?0:4);
        compare(&s,9400+t,HB_RUN_READY,1);
    }
#ifdef HB_SENSOR_ENTRY
    for(unsigned t=0;t<48;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        static const unsigned variants[]={0,3,6,8,10,15,20,23,24,25,26,29,30,31,32,37,38,40,41,43,44,50,57,60};
        hb_test_sensor(c,k,variants[t/2]);
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w32(c+0x2c,0);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=1;((unsigned char*)reawb)[0x1c]=0;
        compare(&s,9600+t,HB_RUN_READY,1);
    }
#ifdef HB_PARSING_ENTRY
    for(unsigned t=0;t<40;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        static const unsigned variants[]={0,10,11,12,13,14,15,16,18,19,21,22,24,28,29,30,33,34,35,36};
        hb_test_parsing(c,k,variants[t/2],1);
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w32(c+0x2c,0);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=1;((unsigned char*)reawb)[0x1c]=0;
        compare(&s,9800+t,HB_RUN_READY,1);
    }
#ifdef HB_STAT_AUTO_ENTRY
    for(unsigned t=0;t<32;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        hb_test_manual_tables(c,k,t);c[0x278]=(t%4)&1;c[0x2f4]=((t%4)>>1)&1;
        if(t==31){c[0x278]=255;c[0x2f4]=3;}
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w32(c+0x2c,t%9);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=1;((unsigned char*)reawb)[0x1c]=0;
        compare(&s,10000+t,HB_RUN_READY,1);
    }
#ifdef HB_DETECT_ENTRY
    for(unsigned t=0;t<48;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        hb_test_parsing(c,k,35,1);hb_test_detect(c,k,t,1);
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w32(c+0x2c,0);w16(c+0xef3e,0);c[0xdb60]=0;w32(c+0xeeac,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=1;((unsigned char*)reawb)[0x1c]=0;
        compare(&s,10200+t,HB_RUN_READY,1);
    }
#ifdef HB_FACE_ENTRY
    for(unsigned t=0;t<32;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);
        hb_test_face(c,k,16+t%8);c[0xd900]=0;
        w32(c+0xb2020,0);w32(c+0x194,t%2);w32(c+0x174,0);w32(c+0x17c,0);w32(c+0x184,0);c[0xd338]=0;
        k[0x1531a8]=k[0x1531ac]=1;k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w16(c+0xef3e,0);
        c[0xd328]=c[0xd329]=0;c[0xd32a]=1;((unsigned char*)reawb)[0x1c]=0;
        compare(&s,10400+t,HB_RUN_READY,1);
    }
#ifdef HB_AUTOMATIC_ENTRY
    /* Consecutive imported frames exercise the composed controller, with
     * alternating refresh/reuse requests and passive REAWB enabled. */
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rbase,R);
    k[0x24]=1;w32(k+0x78,0);w32(c+0x17c,0);w32(c+0x184,0);w32(c+0xb2020,0);synthetic_white_axes(k);
    k[0x1531a8]=k[0x1531ac]=k[0x1531ad]=1;w32(k+0x1531b0,UINT32_MAX);w16(c+0xef3e,0);
    ((unsigned char*)reawb)[0x1c]=1;((unsigned char*)reawb)[0x1d]=0;((unsigned char*)reawb)[0x20]=1;((unsigned char*)reawb)[0x22]=0;
    for(unsigned t=0;t<96;++t){
        memset(input,0,0x4118);w32(input,u32(e2+0x4120));w32(input+4,0x4118);w32(input+8,100+t);w32(input+12,u32(e2+0x412c));
        for(unsigned j=0;j<1024;++j){unsigned row=20+(t/8)%7*5+(j%23==0?5:0);uint32_t red=u32(c+0x348+16*row),blue=u32(c+0x34c+16*row),green=1800+(j%11)*64;unsigned char*p=input+16+16*j;
            w16(p,(green<<12)/red);w16(p+2,green);w16(p+4,green);w16(p+6,(green<<12)/blue);p[8]=255;}
        uint32_t st=set(0,input);if(!st)st=parse(0,parsed,meta);if(!st)st=import(0,parsed,meta);if(st)return 2;
        wf(c+0x990d4,6+(float)(t/16));w32(c+0x990e4,16);wf(c+0x990e8,1024);for(unsigned j=0;j<16;++j)wf(c+0x990ec+4*j,64);
        w32(c+0x194,t/48);c[0x990dc]=(t/24)%2;wf(c+0x990d8,(float)(t%5));c[0xd328]=c[0xd329]=0;c[0xd32a]=t%3==0;
        if(t<3||t==95)dump(dir,"sequence_native_input",t,input,0x4118);
        compare(&s,11000+t,HB_RUN_READY,t<3||t==47||t==48||t==95);++automatic_sequence;
    }
    unsigned want_refresh=32,want_reuse=64;same("sequence_refresh_coverage",0,&sequence_refresh,&want_refresh,4);same("sequence_reuse_coverage",0,&sequence_reuse,&want_reuse,4);
    /* Owned-only unsupported-domain checks: never invoke original file I/O
     * or active/linked REAWB. Unsupported is not native error recovery. */
    for(unsigned t=0;t<2;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);w32(c+0x194,0);w32(c+0x174,2);
        hb_automatic_inputs inputs={&manual_model,&sync_model,automatic_workspace,sizeof automatic_workspace};hb_automatic_trace trace={.failed_stage=HB_AUTO_STAGE_COUNT};
        if(!t){c[0xb1ef8]=1;w16(c+0xb1efa,1);w16(c+0xb1efc,1);w32(c+0xb1f00,0);}
        else{((unsigned char*)reawb)[0x1c]=1;((unsigned char*)reawb)[0x22]=1;((unsigned char*)reawb)[0x1d]=0;}
        uint32_t st=hb_automatic_tail(c,k,reawb,&inputs,t?HB_AUTO_REFRESH_TAIL:HB_AUTO_REUSE_TAIL,0,&trace),want=HB_PREP_UNSUPPORTED;
        unsigned stage=t?HB_AUTO_REAWB:HB_AUTO_DEBUG,actual=trace.failed_stage,zero=0,completed=trace.completed;
        same("unsupported_status",t,&st,&want,4);same("unsupported_stage",t,&actual,&stage,4);same("unsupported_not_completed",t,&completed,&zero,4);same("unsupported_record",t,&trace.stage_status,&want,4);unsupported_checks+=4;
    }
    for(unsigned t=0;t<5;++t){
        memcpy(c,dispatch_base,C);memcpy(k,dispatch_cfg,K);memcpy(reawb,dispatch_r,R);w32(c+0x194,0);
        memcpy(s.input,c,C);memcpy(s.ki,k,K);memcpy(s.ri,reawb,R);hb_automatic_trace trace;memset(&trace,0xa5,sizeof trace);hb_automatic_trace before=trace;
        hb_automatic_inputs inputs={&manual_model,&sync_model,automatic_workspace,sizeof automatic_workspace};
        if(t==0)inputs.temperature=NULL;if(t==1)inputs.roi=NULL;if(t==2)inputs.debug_workspace=NULL;if(t==3)inputs.debug_workspace_bytes=HB_DEBUG_WORKSPACE_BYTES-1;
        uint32_t st=hb_run_automatic(c,k,reawb,t==4?NULL:&inputs,&trace),want=HB_PREP_UNSUPPORTED;
        same("input_guard_status",t,&st,&want,4);same("input_guard_context",t,s.input,c,C);same("input_guard_config",t,s.ki,k,K);same("input_guard_reawb",t,s.ri,reawb,R);same("input_guard_trace",t,&before,&trace,sizeof trace);unsupported_checks+=5;
    }
#endif
    printf("{\"event\":\"owned_face_entry_counts\",\"owned_face_calls\":%u,\"active_face_calls\":%u,\"face_error_completions\":%u,\"original_face_callbacks\":0,\"face_owned\":true}\n",face_calls,face_active,face_errors);
#endif
    printf("{\"event\":\"owned_detection_entry_counts\",\"owned_detection_calls\":%u,\"detection_error_completions\":%u,\"status106\":%u,\"status131\":%u,\"status177\":%u,\"status247\":%u,\"original_detection_callbacks\":0,\"detection_owned\":true}\n",detect_calls,detect_errors,detect106,detect131,detect177,detect247);
#endif
    printf("{\"event\":\"owned_stat_auto_entry_counts\",\"owned_statistics_calls\":%u,\"unit_enabled_calls\":%u,\"temperature_enabled_calls\":%u,\"original_statistics_callbacks\":0,\"automatic_statistics_owned\":true}\n",owned_statistics_calls,statistics_unit,statistics_temperature);
#endif
    printf("{\"event\":\"owned_parsing_entry_counts\",\"owned_parsing_calls\":%u,\"active_parsing_calls\":%u,\"parsing_error_completions\":%u,\"original_parsing_callbacks\":0,\"parsing_owned\":true}\n",parsing_calls,parsing_active_calls,parsing_errors);
#endif
    printf("{\"event\":\"owned_sensor_entry_counts\",\"owned_sensor_calls\":%u,\"active_sensor_calls\":%u,\"original_sensor_callbacks\":0,\"original_statistics_callbacks\":%u,\"sensor_adaptation_owned\":true}\n",sensor_calls,sensor_active_calls,original_statistics_calls);
#endif
    printf("{\"event\":\"owned_roi_sync_entry_counts\",\"owned_sync_calls\":%u,\"original_sync_callbacks\":0,\"roi_synchronization_owned\":true}\n",sync_calls);
    unsigned original_sync_calls=0;
#else
    unsigned original_sync_calls=roi_calls;
#endif
    printf("{\"event\":\"owned_roi_entry_counts\",\"roi_calls\":%u,\"roi_error_completions\":%u,\"original_sync_callbacks\":%u,\"roi_processing_owned\":true,\"roi_synchronization_owned\":%s}\n",roi_calls,roi_errors,original_sync_calls,original_sync_calls?"false":"true");
#endif
    printf("{\"event\":\"owned_dispatch_counts\",\"suspended_returns\":%u,\"automatic_refresh\":%u,\"automatic_reuse\":%u,\"manual_remainders\":%u,\"custom_remainders\":%u,\"error_completions\":%u}\n",dispatch_counts[0],dispatch_counts[1],dispatch_counts[2],dispatch_counts[3],dispatch_counts[4],dispatch_counts[5]);
#endif
#ifdef HB_AUTOMATIC_ENTRY
    printf("{\"event\":\"owned_automatic_composition\",\"full_automatic_calls\":%u,\"owned_suffix_calls\":%u,\"mode_guard_checks\":%u,\"native_error_recoveries\":%u,\"early_nonzero_returns\":%u,\"consecutive_frame_calls\":%u,\"sequence_refresh\":%u,\"sequence_reuse\":%u,\"unsupported_checks\":%u,\"original_automatic_callbacks\":0,\"manual_custom_original_continuations\":%u,\"stage_counts\":[",composed_calls,owned_tails,composed_guards,composed_recoveries,composed_early_nonzero,automatic_sequence,sequence_refresh,sequence_reuse,unsupported_checks,continued);
    for(unsigned j=0;j<HB_AUTO_STAGE_COUNT;++j)printf("%s%u",j?",":"",automatic_stages[j]);printf("],\"bounded_automatic_controller_owned\":true,\"initialization_owned\":false,\"phone_colour_validated\":false}\n");
#endif
    same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rbase,R);
    printf("{\"event\":\"owned_run_entry\",\"checks\":%u,\"mismatches\":%u,\"early_returns\":%u,\"original_remainder_calls\":%u,\"reason_counts\":[%u,%u,%u,%u,%u,%u],\"rate_boundary_cases\":144,\"stateful_calls\":%u,\"native_frames\":%u,\"white_lut_failure_returns\":%u,\"active_e_nd_native_frames\":%u,\"user_prefix_calls\":%u,\"user_failure_returns\":%u,\"original_user_remainders\":%u,\"user_status_83_returns\":%u,\"user_status_84_returns\":%u,\"unit_requests_accepted\":%u,\"unit_requests_rejected\":%u,\"all_passed\":%s,\"whole_controller_owned\":false,\"original_remainder_used\":true,\"synthetic_inputs\":true}\n",checks,failures,early,continued,reasons[0],reasons[1],reasons[2],reasons[3],reasons[4],reasons[5],stateful_calls,native_calls,white_errors,active_native,user_prefix_calls,user_errors,user_remainders,user_errors83,user_errors84,unit_accepted,unit_rejected,failures?"false":"true");return failures?1:0;
}
