/* SPDX-License-Identifier: MIT */
#include "hb_stat_difference.h"
#include "hb_stat_prepare.h"
#include "stat_difference_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,calls,forced,cleared,missing,stateful,guards,counter_changes;
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"difference_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*r,*pre,*ref,*ki,*kr;unsigned char ri[R],rr[R];void**global;uint32_t(*original)(int);const char*dir;} state;
static void compare(state*s,unsigned t,unsigned null_handle,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    if(null_handle)*s->global=NULL;
    uint32_t a=s->original(0);*s->global=s->r;
    memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
    forced+=s->c[0xd328]==1;cleared+=s->c[0xd328]==0;missing+=a==UINT32_MAX;
    counter_changes+=memcmp(s->pre+0xb6964,s->c+0xb6964,4)!=0;
    memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    uint32_t b=hb_stat_difference(s->c,s->k,null_handle?NULL:s->r);
    same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);same("reawb",t,s->rr,s->r,R);++calls;
    if(capture){dump(s->dir,"difference_input",t,s->pre,C);dump(s->dir,"difference_config",t,s->ki,K);dump(s->dir,"difference_reawb",t,s->ri,R);dump(s->dir,"difference_original",t,s->ref,C);dump(s->dir,"difference_owned",t,s->c,C);}
}
int hb_run_stat_difference_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rb[R];state s={.c=c,.k=k,.r=reawb,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;s.global=(void**)(bias+0x791450);s.original=sym(h,"scene_awb_stat_diff_chk");
    for(unsigned t=0;t<480;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_difference(c,k,reawb,t);compare(&s,t,0,t<80);}
    /* All rate boundaries crossed with every previous flag, including NaN. */
    for(unsigned t=0;t<64;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_difference(c,k,reawb,56+t%8);c[0xd329]=(unsigned char)((t/8)%4);c[0xd328]=t<32?1:255;compare(&s,1000+t,0,t<8);}
    for(unsigned t=0;t<16;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_difference(c,k,reawb,t<8?t%4:72+t%8);hb_diff_w16(c+0xb6962,1);compare(&s,2000+t,1,1);}
    /* ROI refresh holds for30 subsequent calls, then releases into difference;
     * the second run checks alternating updates at/above30 frames/sec. */
    for(unsigned sequence=0;sequence<2;++sequence){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_difference(c,k,reawb,sequence?58:8);if(!sequence)hb_diff_w32(c+0x28,1);
        hb_diff_w16(c+0xb6962,2);for(unsigned t=0;t<40;++t){if(!sequence&&t)memset(c+0x98f48,0,0x180);hb_diff_w32(c+0x9c1a0,t);compare(&s,3000+sequence*100+t,0,t==0||t==30||t==31||t==39);++stateful;}
    }
    for(unsigned t=0;t<4;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(reawb,rb,R);hb_test_difference(c,k,reawb,72);hb_diff_w16(c+0xb6962,1);
        if(t==0)hb_diff_w32(c+0x28,0);if(t==1)hb_diff_w32(c+0x28,1025);if(t==2)hb_diff_w32(c+0x2c,13);if(t==3)hb_diff_w32(c+0x28,UINT32_MAX);
        memcpy(s.pre,c,C);uint32_t a=hb_stat_difference(c,k,reawb),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_context",t,c,s.pre,C);guards+=2;
    }
    same("original_config_preserved",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rb,R);*s.global=reawb;
    printf("{\"event\":\"owned_statistics_difference\",\"checks\":%u,\"mismatches\":%u,\"original_calls\":%u,\"refresh_results\":%u,\"reuse_results\":%u,\"missing_handle_disabled_returns\":%u,\"diagnostic_counter_changes\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"statistics_difference_owned\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls,forced,cleared,missing,counter_changes,stateful,guards,failures?"false":"true");return failures?1:0;
}
