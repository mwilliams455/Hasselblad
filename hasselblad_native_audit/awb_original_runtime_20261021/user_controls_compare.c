/* SPDX-License-Identifier: MIT */
#include "hb_user_controls.h"
#include "hb_user_manual.h"
#include "hb_user_e_nd.h"
#include "hb_stat_prepare.h"
#include "user_controls_fixtures.h"
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
uint32_t hb_original_user_remainder(uintptr_t);
static unsigned checks,failures,conversions,helpers,handlers,users,stateful,guards,statuses[256];
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"controls_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*r,*pre,*ref,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;uint32_t(*original[4])(int);hb_temperature_model model;const char*dir;} state;
static void compare(state*s,unsigned kind,unsigned t,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    uint32_t a=s->original[kind](0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);if(a<256)++statuses[a];
    memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    uint32_t b=kind==0?hb_user_update_ct(s->c,s->k,&s->model):kind==1?hb_user_update_ct_tint(s->c,s->k,&s->model):kind==2?hb_user_update_gain(s->c,s->k,&s->model):hb_user_prepare_calibration(s->c,s->k);
    if(kind==3&&!b)b=hb_user_manual_samples(s->c,s->k,&s->model);
    if(kind==3&&!b){b=hb_user_controls(s->c,s->k,&s->model);if(capture)dump(s->dir,"controls_owned_boundary",t,s->c,C);if(!b)b=hb_original_user_remainder(s->bias+0x4b16d4);}
    same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);same("reawb",t,s->rr,s->r,R);
    if(kind==3)++users;else ++handlers;
    if(capture){dump(s->dir,"controls_input",t,s->pre,C);dump(s->dir,"controls_config",t,s->ki,K);dump(s->dir,"controls_original",t,s->ref,C);dump(s->dir,"controls_owned",t,s->c,C);}
}
int hb_run_user_controls_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rb[R];state s={.c=c,.k=k,.r=reawb,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    s.original[0]=sym(h,"scene_awb_user_update_ct");s.original[1]=sym(h,"scene_awb_user_update_ct_tint");s.original[2]=sym(h,"scene_awb_user_update_gain");s.original[3]=sym(h,"scene_awb_user_proc");
    float table[124];memcpy(table,(void*)(s.bias+0x6ce418),sizeof table);s.model.isotemperature_31x4=table;dump(dir,"controls_isotemperature",0,table,sizeof table);
    uint32_t(*convert)(int,uint32_t,float,uint32_t,uint32_t*,uint32_t*,uint32_t*)=sym(h,"scene_awb_ct_tint_to_gain");
    static const float tints[]={-INFINITY,-10000,-99,-1,0,0.25f,1,99,10000,INFINITY,NAN};
    static const uint32_t temperatures[]={0,1,1000,1999,2000,2800,4000,6500,10000,25000,UINT32_MAX};
    for(unsigned t=0;t<384;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);c[0x990dc]=(unsigned char)(t%3);hb_manual_wf(c+0x990d8,(float)(t%20)/2);
        if(t%13==0){k[0x1332bc]=1;memset(k+0x1332c4,0,36);}memcpy(s.pre,c,C);memcpy(s.ki,k,K);
        uint32_t ao[5]={11,22,33,44,55},bo[5];memcpy(bo,ao,sizeof bo);unsigned gi=t%5==0?1:2,bi=t%5==1?gi:t%5==2?1:3;uint32_t ct=temperatures[(t/11)%11],scale=t%5==0?0:t%5==1?UINT32_MAX:4096;
        uint32_t a=convert(0,ct,tints[t%11],scale,ao+1,ao+gi,ao+bi),b=hb_user_ct_tint_to_gain(c,k,&s.model,ct,tints[t%11],scale,bo+1,bo+gi,bo+bi);
        same("conversion_status",t,&a,&b,4);same("conversion_outputs",t,ao,bo,sizeof ao);same("conversion_context",t,c,s.pre,C);same("conversion_config",t,k,s.ki,K);++conversions;
    }
    uint32_t(*publish)(int,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,float,uint32_t,uint8_t)=sym(h,"scene_awb_result_update_manual");
    uint32_t(*snapshot)(int)=sym(h,"scene_awb_result_update_golden_gain_manual");uint32_t(*recal[4])(int)={sym(h,"scene_awb_result_recalib_manual"),sym(h,"scene_awb_result_e_nd_temp_recalib_manual"),sym(h,"scene_awb_result_e_nd_unit_recalib_manual"),sym(h,"scene_awb_result_e_nd_golden_recalib_manual")};
    for(unsigned kind=0;kind<6;++kind)for(unsigned t=0;t<96;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);for(unsigned i=0xb0eb8;i<0xb0ff0;++i)c[i]=(unsigned char)(i*17+t*31);
        uint32_t raw[3]={t?UINT32_MAX-t:0,t*137,0x80000000+t},golden[3]={t*911,UINT32_MAX,0};unsigned cal=kind>=2?(unsigned[]){0x1c0,0x300,0x2ec,0x270}[kind-2]:0;
        if(kind>=2){hb_manual_w32(c+cal,t%7==0?0:1+t*41);hb_manual_w32(c+cal+4,t%7==1?0:1+t*17);}memcpy(s.pre,c,C);
        uint32_t a=kind==0?publish(0,raw[0],raw[1],raw[2],golden[0],golden[1],golden[2],t*311,tints[t%11],t%9,(uint8_t)t):kind==1?snapshot(0):recal[kind-2](0);memcpy(s.ref,c,C);memcpy(c,s.pre,C);
        uint32_t b=kind==0?hb_user_result_manual(c,raw,golden,t*311,tints[t%11],t%9,(uint8_t)t):kind==1?hb_user_result_golden_snapshot(c):hb_user_result_recalibrate(c,kind-2);
        same("helper_status",t,&a,&b,4);same("helper_context",t,s.ref,c,C);++helpers;
    }
    for(unsigned kind=0;kind<4;++kind)for(unsigned t=0;t<192;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_control_request(c,k,t);
        if(t>=176)hb_manual_wf(c+0xb14d4,tints[t%11]);compare(&s,kind,1000+kind*200+t,t<12);
    }
    for(unsigned kind=0;kind<4;++kind)if(kind!=2)for(unsigned t=0;t<8;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_control_failure(c,k,t);compare(&s,kind,4000+kind*10+t,1);}
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);
    for(unsigned t=0;t<48;++t){if(t%2==0)hb_test_control_request(c,k,t/2);compare(&s,3,2000+t,t<4);++stateful;}
    for(unsigned t=0;t<8;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_control_request(c,k,1);c[0xb14c4]=1;c[0xb14cc]=1;c[0x2f4]=c[0x278]=c[0x24c]=1;hb_manual_w32(k+0x18,1);hb_manual_w32(k+0x1c,0);
        if(t==0)c[0x1a0]=3;if(t==1)k[0x16e940]=0;if(t==2)c[0x27a]=0;if(t==3)k[0x16e649]=0;if(t==4)k[0x16e654]=3;if(t==5)hb_manual_w32(c+0xb14d0,1999);if(t==6)hb_manual_w32(c+0xb14d0,10100);
        memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t a=t>=5&&t<=6?hb_user_update_ct_tint(c,k,&s.model):hb_user_update_ct(c,k,t==7?NULL:&s.model),b=HB_PREP_UNSUPPORTED;
        same("guard_status",t,&a,&b,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guards+=3;
    }
    same("original_config_preserved",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rb,R);
    printf("{\"event\":\"owned_user_controls\",\"checks\":%u,\"mismatches\":%u,\"ct_tint_conversion_calls\":%u,\"result_helper_calls\":%u,\"control_handler_calls\":%u,\"full_user_comparisons\":%u,\"stateful_calls\":%u,\"status_81\":%u,\"status_89\":%u,\"status_91\":%u,\"status_92\":%u,\"status_157\":%u,\"owned_only_guard_checks\":%u,\"full_user_owned\":false,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,conversions,helpers,handlers,users,stateful,statuses[81],statuses[89],statuses[91],statuses[92],statuses[157],guards,failures?"false":"true");return failures?1:0;
}
