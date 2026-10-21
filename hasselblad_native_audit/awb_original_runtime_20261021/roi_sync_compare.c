/* SPDX-License-Identifier: MIT */
#include "hb_roi_sync.h"
#include "hb_stat_prepare.h"
#include "roi_sync_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls[3],rejections,stateful,guards;
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
 if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"sync_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki,*kr;uint32_t(*original[3])(int);hb_roi_sync_model model;const char*dir;} state;
static uint32_t owned(state*s,unsigned kind){return kind==0?hb_roi_sync_matrix(s->c,s->k,&s->model):kind==1?hb_roi_sync_calculate(s->c,s->k,&s->model):hb_roi_sync_process(s->c,s->k,&s->model);}
static void compare(state*s,unsigned t,unsigned kind,unsigned capture){
 memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=s->original[kind](0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);
 memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);uint32_t b=owned(s,kind);
 same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);++calls[kind];rejections+=a==UINT32_MAX;
 if(capture||a!=b||memcmp(s->ref,s->c,C)){dump(s->dir,"sync_input",t,s->pre,C);dump(s->dir,"sync_config",t,s->ki,K);dump(s->dir,"sync_original",t,s->ref,C);dump(s->dir,"sync_owned",t,s->c,C);}
}
int hb_run_roi_sync_tests(void*h,unsigned char*c,void*config,const char*dir){
 unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
 if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;memcpy(base,c,C);memcpy(cfg,config,K);
 const char*names[]={"scene_awb_sync_roi_calc_use_h_matrix","scene_awb_sync_roi_calc","scene_awb_sync_roi_proc"};for(unsigned i=0;i<3;++i){s.original[i]=dlsym(h,names[i]);if(!s.original[i])return 3;}
 uintptr_t bias=(uintptr_t)dlsym(h,"get_scene_awb_context")-0x464068;hb_test_sync_model(&s.model,bias);dump(dir,"sync_model",0,&s.model,sizeof s.model);
 for(unsigned kind=0;kind<3;++kind)for(unsigned t=0;t<112;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_sync(c,k,&s.model,t);compare(&s,1000*kind+t,kind,t<64);}
 for(unsigned t=0;t<32;++t){if(!t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_sync(c,k,&s.model,0);}c[0x990dc]=t%4==0;k[0x16eae4]=t%5==0?0:1;hb_sync_w32(c+0x9c19c,t%3==0?0:12);compare(&s,4000+t,2,t<4||t==31);++stateful;}
 for(unsigned t=0;t<9;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_sync(c,k,&s.model,0);if(t<3)k[0x16eaf0]=7;else memset(c+0xda54+84*((t-3)/2)+16*((t-3)%2),'x',16);
  memcpy(s.pre,c,C);uint32_t a=owned(&s,t<3?1+t%2:t%3),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_context",t,c,s.pre,C);guards+=2;}
 same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
 printf("{\"event\":\"owned_roi_synchronization\",\"checks\":%u,\"mismatches\":%u,\"matrix_calls\":%u,\"calculation_calls\":%u,\"processing_calls\":%u,\"matrix_rejections\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"roi_synchronization_owned\":true,\"private_model_supplied\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls[0],calls[1],calls[2],rejections,stateful,guards,failures?"false":"true");return failures?1:0;
}
