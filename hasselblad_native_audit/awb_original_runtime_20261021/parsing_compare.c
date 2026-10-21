/* SPDX-License-Identifier: MIT */
#include "hb_parsing.h"
#include "hb_stat_prepare.h"
#include "parsing_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls,empty_errors,disabled_grids,stateful,guards;
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
 if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"parsing_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki,*kr;uint32_t(*original)(int);const char*dir;} state;
static void compare(state*s,unsigned t,unsigned capture){
 memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=s->original(0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);
 memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);uint32_t b=hb_parsing_process(s->c,s->k);
 same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);++calls;empty_errors+=a==177;disabled_grids+=s->ki[0x138748]==1&&!s->kr[0x138748];
 if(capture||a!=b||memcmp(s->ref,s->c,C)||memcmp(s->kr,s->k,K)){dump(s->dir,"parsing_input",t,s->pre,C);dump(s->dir,"parsing_config",t,s->ki,K);dump(s->dir,"parsing_original",t,s->ref,C);dump(s->dir,"parsing_owned",t,s->c,C);dump(s->dir,"parsing_original_config",t,s->kr,K);dump(s->dir,"parsing_owned_config",t,s->k,K);}
}
int hb_run_parsing_tests(void*h,unsigned char*c,void*config,const char*dir){
 unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
 if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;memcpy(base,c,C);memcpy(cfg,config,K);s.original=dlsym(h,"scene_awb_parsing_proc");if(!s.original)return 3;
 for(unsigned t=0;t<104;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_parsing(c,k,t%40,0);
  if(t>=40){unsigned seed=0x985421+t;unsigned w=1+t%13,hg=1+(t/13)%9,n=w*hg;hp_w32(c+0x18,w);hp_w32(c+0x1c,hg);hp_w32(c+0x28,n);k[0x138748]=1;
   for(unsigned i=0;i<7168;++i){seed=1664525*seed+1013904223;hp_w16(c+0x9c20a+2*i,seed%513);}for(unsigned i=0;i<6144;++i){seed=1664525*seed+1013904223;c[0x3c242+i]=seed%256;}
  }compare(&s,t,1);}
 for(unsigned t=0;t<48;++t){if(!t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_parsing(c,k,35,0);}hp_wf(c+0x37618,(float)(t%25));for(unsigned i=0;i<448;++i)hp_w16(c+0x9c20a+2*i,(13*i+11*t)%257);compare(&s,2000+t,t<4||t==47);++stateful;}
 memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);compare(&s,3000,1);
 for(unsigned t=0;t<8;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_parsing(c,k,35,0);
  switch(t){case 0:hp_w32(c+0x28,1025);break;case 1:hp_w32(c+0x18,65536);hp_w32(c+0x1c,65536);break;case 2:k[0x138779]=5;break;case 3:k[0x13884c]=9;break;case 4:k[0x13884f]=9;break;case 5:k[0x1394d0]=0;break;case 6:k[0x1394d0]=9;break;case 7:hp_w32(c+0x18,0);hp_w32(c+0x1c,UINT32_MAX);break;}
  memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t a=hb_parsing_process(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guards+=3;}
 same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
 printf("{\"event\":\"owned_parsing\",\"checks\":%u,\"mismatches\":%u,\"original_calls\":%u,\"empty_table_status177\":%u,\"disabled_large_grids\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"parsing_owned\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls,empty_errors,disabled_grids,stateful,guards,failures?"false":"true");return failures?1:0;
}
