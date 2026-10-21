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
typedef struct{unsigned char*c,*k,*r,*input,*reference,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;uint32_t(*run)(int);const char*dir;} test_state;
static hb_run_entry_result compare(test_state*s,unsigned t,int expected,unsigned capture){
    memcpy(s->input,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    uint32_t a=s->run(0);memcpy(s->reference,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
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
            b=hb_user_prepare_calibration(s->c,s->k);
#ifdef HB_USER_MANUAL_ENTRY
            if(!b)b=hb_user_manual_samples(s->c,s->k,&manual_model);
#endif
            if(s->input[0xb1f86]==1&&s->c[0xb1f86]==0){unit_accepted+=s->c[0x279]==1;unit_rejected+=s->c[0x279]==0;}
#else
            b=hb_user_prepare_prefix(s->c,s->k);
#endif
            if(capture)dump(s->dir,"owned_user_prefix_boundary",t,s->c,C);
            if(!b){++user_remainders;
#ifdef HB_USER_MANUAL_ENTRY
                b=hb_original_user_remainder(s->bias+0x4b16a8);
#elif defined(HB_USER_E_ND_ENTRY)
                b=hb_original_user_remainder(s->bias+0x4b162c);
#else
                b=hb_original_user_remainder(s->bias+0x4b1624);
#endif
            }
            if(!b){++continued;b=hb_original_prepared_completion(s->bias+0x471e78,s->c,0,s->bias+0x791348);}else{++user_errors;user_errors83+=b==83;user_errors84+=b==84;}
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
    return result;
}
int hb_run_entry_tests(void*h,unsigned char*c,unsigned char*e2,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;
    unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rbase[R];
    test_state s={.c=c,.k=k,.r=reawb,.input=malloc(C),.reference=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.input||!s.reference||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rbase,reawb,R);s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;s.run=sym(h,"scene_awb_lib_run");
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
        dump(dir,"native_input",t,input,0x4118);hb_run_entry_result result=compare(&s,8000+t,HB_RUN_READY,1);if(result.action!=HB_RUN_PREPARE)return 2;++native_calls;
    }
    same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rbase,R);
    printf("{\"event\":\"owned_run_entry\",\"checks\":%u,\"mismatches\":%u,\"early_returns\":%u,\"original_remainder_calls\":%u,\"reason_counts\":[%u,%u,%u,%u,%u,%u],\"rate_boundary_cases\":144,\"stateful_calls\":%u,\"native_frames\":%u,\"white_lut_failure_returns\":%u,\"active_e_nd_native_frames\":%u,\"user_prefix_calls\":%u,\"user_failure_returns\":%u,\"original_user_remainders\":%u,\"user_status_83_returns\":%u,\"user_status_84_returns\":%u,\"unit_requests_accepted\":%u,\"unit_requests_rejected\":%u,\"all_passed\":%s,\"whole_controller_owned\":false,\"original_remainder_used\":true,\"synthetic_inputs\":true}\n",checks,failures,early,continued,reasons[0],reasons[1],reasons[2],reasons[3],reasons[4],reasons[5],stateful_calls,native_calls,white_errors,active_native,user_prefix_calls,user_errors,user_remainders,user_errors83,user_errors84,unit_accepted,unit_rejected,failures?"false":"true");return failures?1:0;
}
