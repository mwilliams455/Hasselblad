/* SPDX-License-Identifier: MIT */
#include "hb_user_finish.h"
#include "hb_stat_prepare.h"
#include "user_controls_fixtures.h"
#include "user_finish_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
uint32_t hb_original_user_remainder(uintptr_t);
static unsigned checks,failures,helpers,tails,users,stateful,guards,accepted_fixed,rejected_fixed,accepted_override,rejected_override,early_errors;
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"finish_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*r,*pre,*ref,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;uint32_t(*original)(int);hb_temperature_model model;const char*dir;} state;
static void compare(state*s,unsigned full,unsigned t,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    uint32_t a=full?s->original(0):hb_original_user_remainder(s->bias+0x4b16d4);
    memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
    if(s->pre[0xb1cf8]==1&&s->c[0xb1cf8]==0){accepted_fixed+=s->c[0xd338]==1;rejected_fixed+=s->c[0xd338]==0;}
    if(s->pre[0xb1ff8]==1&&s->c[0xb1ff8]==0){accepted_override+=s->c[0xd324]==1;rejected_override+=s->c[0xd324]==0;}
    early_errors+=full&&a!=0;
    memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    uint32_t b=full?hb_user_process(s->c,s->k,&s->model):hb_user_finish(s->c);
    same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);same("reawb",t,s->rr,s->r,R);
    if(full)++users;else ++tails;
    if(capture){dump(s->dir,"finish_input",t,s->pre,C);dump(s->dir,"finish_config",t,s->ki,K);dump(s->dir,"finish_original",t,s->ref,C);dump(s->dir,"finish_owned",t,s->c,C);}
}
int hb_run_user_finish_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rb[R];state s={.c=c,.k=k,.r=reawb,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;s.original=sym(h,"scene_awb_user_proc");
    float table[124];memcpy(table,(void*)(s.bias+0x6ce418),sizeof table);s.model.isotemperature_31x4=table;dump(dir,"finish_isotemperature",0,table,sizeof table);
    uint32_t(*valid)(const unsigned char*)=sym(h,"scene_awb_post_check_gain_valid");
    for(unsigned t=0;t<64;++t){unsigned char p[36],before[36];for(unsigned i=0;i<36;++i)p[i]=(unsigned char)(i*13+t*37);
        for(unsigned i=1;i<=6;++i)hb_finish_w32(p+4+4*i,t%3?0xffffffff:0x80000000);
        if(t%8<6)hb_finish_w32(p+8+4*(t%8),0);memcpy(before,p,sizeof p);
        uint32_t a=valid(p+4),b=hb_user_gain_record_valid(p+4),want=t%8<6?247:246;
        same("gain_valid_status",t,&a,&b,4);same("gain_valid_expected",t,&a,&want,4);same("gain_valid_immutable",t,p,before,sizeof p);++helpers;
    }
    for(unsigned full=0;full<2;++full)for(unsigned t=0;t<256;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);
        if(full)hb_test_control_request(c,k,t);
        hb_test_finish_request(c,t);
        if(!full){ /* sentinel previous results verify rejection preservation */
            for(unsigned i=0xd33c;i<0xd474;++i)c[i]=(unsigned char)(i*7+t*19);
            c[0xd338]=c[0xd324]=79;hb_finish_w32(c+0xc5a0,0xdeadbeef);hb_finish_w32(c+0xc6d4,0x7fc54321);hb_finish_w32(c+0xc6e4,0xcafebabe);
        }
        compare(&s,full,1000+full*1000+t,t<64);
    }
    for(unsigned t=0;t<8;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_control_failure(c,k,t);hb_test_finish_request(c,53);compare(&s,1,3000+t,1);}
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);
    for(unsigned t=0;t<64;++t){if(t%2==0){hb_test_control_request(c,k,t/2);hb_test_finish_request(c,t/2);}compare(&s,1,4000+t,t<4);++stateful;}
    for(unsigned t=0;t<4;++t){memcpy(c,base,C);hb_test_finish_request(c,53);c[0x1a0]=(unsigned char)(3+t*84);memcpy(s.pre,c,C);
        uint32_t a=hb_user_finish(c),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_immutable",t,c,s.pre,C);guards+=2;
        /* Rejected fixed record never accesses the oversized base table. */
        memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_finish_w32(c+0xb1d54,1999);compare(&s,0,5000+t,1);
    }
    same("original_config_preserved",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rb,R);
    printf("{\"event\":\"owned_complete_user_stage\",\"checks\":%u,\"mismatches\":%u,\"gain_record_helper_calls\":%u,\"tail_comparisons\":%u,\"full_user_comparisons\":%u,\"stateful_calls\":%u,\"fixed_requests_accepted\":%u,\"fixed_requests_rejected\":%u,\"override_requests_accepted\":%u,\"override_requests_rejected\":%u,\"early_user_errors\":%u,\"owned_only_guard_checks\":%u,\"full_user_owned\":true,\"original_user_calls_in_owned_path\":0,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,helpers,tails,users,stateful,accepted_fixed,rejected_fixed,accepted_override,rejected_override,early_errors,guards,failures?"false":"true");return failures?1:0;
}
