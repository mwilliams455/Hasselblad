/* SPDX-License-Identifier: MIT */
#include "hb_roi.h"
#include "hb_stat_prepare.h"
#include "roi_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls,reset_calls,errors,stateful,guards,selected[6];
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"roi_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki,*kr;uint32_t(*original)(int);uint32_t(*reset)(int);const char*dir;} state;
static void compare(state*s,unsigned t,unsigned reset,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=(reset?s->reset:s->original)(0);
    memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);
    uint32_t b=reset?hb_roi_reinitialize(s->c):hb_roi_process(s->c,s->k);
    same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);++calls;reset_calls+=reset;errors+=a==225;
    for(unsigned j=0;j<6;++j){uint32_t flag;memcpy(&flag,s->ref+hb_roi_box[j],4);selected[j]+=flag==1;}
    if(capture||a!=b||memcmp(s->ref,s->c,C)){dump(s->dir,"roi_input",t,s->pre,C);dump(s->dir,"roi_config",t,s->ki,K);dump(s->dir,"roi_original",t,s->ref,C);dump(s->dir,"roi_owned",t,s->c,C);}
}
int hb_run_roi_tests(void*h,unsigned char*c,void*config,const char*dir){
    unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);s.original=dlsym(h,"scene_awb_roi_proc");s.reset=dlsym(h,"scene_awb_roi_reinit");if(!s.original||!s.reset)return 3;
    for(unsigned j=0;j<6;++j)for(unsigned t=0;t<64;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_roi(c,k,j,t);compare(&s,j*100+t,0,t<8||t>=56);}
    /* Multiple enabled types, stale higher-priority input, and publication of
     * previously prepared output when no detector configuration is enabled. */
    for(unsigned t=0;t<48;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_roi(c,k,t%6,t%2);
        for(unsigned j=0;j<6;++j){k[0x16e5a0+28*j]=t<36;hb_roi_w32(c+hb_roi_pending[j]-4,j<t%6?0:105);}
        if(t>=36){c[0xd9a4]=(unsigned char)((t-36)%3);c[0xd902]=(unsigned char)((t-36)/3);memset(c+0xd904,0x4f,160);}
        compare(&s,1000+t,0,1);
    }
    for(unsigned t=0;t<8;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_roi(c,k,t%6,t);compare(&s,2000+t,1,1);}
    for(unsigned j=0;j<6;++j){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_roi(c,k,j,0);
        for(unsigned t=0;t<12;++t){hb_roi_w32(c+0x9c1a0,120+5*t);compare(&s,3000+j*100+t,0,t==0||t==11);++stateful;}
    }
    for(unsigned j=0;j<6;++j){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_roi(c,k,j,0);hb_roi_w32(c+hb_roi_pending[j]+4,9);memcpy(s.pre,c,C);
        uint32_t a=hb_roi_process(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",j,&a,&want,4);same("guard_context",j,c,s.pre,C);guards+=2;}
    same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
    printf("{\"event\":\"owned_roi_processing\",\"checks\":%u,\"mismatches\":%u,\"original_calls\":%u,\"direct_reset_calls\":%u,\"zoom_errors\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"selected_by_kind\":[%u,%u,%u,%u,%u,%u],\"roi_processing_owned\":true,\"roi_synchronization_owned\":false,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls,reset_calls,errors,stateful,guards,selected[0],selected[1],selected[2],selected[3],selected[4],selected[5],failures?"false":"true");return failures?1:0;
}
