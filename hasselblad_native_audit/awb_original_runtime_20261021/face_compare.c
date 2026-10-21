/* SPDX-License-Identifier: MIT */
#include "hb_face.h"
#include "hb_stat_prepare.h"
#include "face_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls,stateful,guards,statuses[256];
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;if(failures<=40){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"face_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki;uint32_t(*original)(int);const char*dir;} state;
static void compare(state*s,unsigned t,unsigned save){memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=s->original(0);memcpy(s->ref,s->c,C);same("original_config",t,s->ki,s->k,K);memcpy(s->c,s->pre,C);uint32_t b=hb_face_process(s->c,s->k);same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("owned_config",t,s->ki,s->k,K);++calls;if(a<256)++statuses[a];if(save||a!=b||memcmp(s->ref,s->c,C)){dump(s->dir,"face_input",t,s->pre,C);dump(s->dir,"face_config",t,s->ki,K);dump(s->dir,"face_original",t,s->ref,C);dump(s->dir,"face_owned",t,s->c,C);}memcpy(s->c,s->ref,C);}
int hb_run_face_tests(void*h,unsigned char*c,void*config,const char*dir){unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.dir=dir};if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki)return 71;memcpy(base,c,C);memcpy(cfg,config,K);s.original=dlsym(h,"scene_awb_face_proc");if(!s.original)return 3;
 for(unsigned t=0;t<117;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_face(c,k,t);compare(&s,t,1);}
 memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_face(c,k,53);
 for(unsigned t=0;t<96;++t){hf_w32(c+0x9c1a0,100+t);if(t==32||t==80)memset(c+0x37450,0,8);if(t==64){c[0x37450]=1;hf_w32(c+0x37458,4100);}compare(&s,1000+t,t<4||t==95);++stateful;}
 memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);compare(&s,3000,1);
 for(unsigned t=0;t<12;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_face(c,k,53);
  switch(t){case 0:hf_w32(c+44,9);break;case 1:hf_w32(c+0xdb5c,9);break;case 2:c[0xdea0]=3;break;case 3:hf_w32(c+40,1025);break;case 4:k[0x1644b0]=17;break;case 5:hf_w32(c+0xdea4,81);break;case 6:k[0x164788]=9;break;case 7:k[0x16ab24]=16;break;case 8:k[0x16aee8]=16;break;case 9:k[0x1647c8]=9;break;case 10:k[0x1647d0]=0;break;case 11:k[0x1647d8]=9;break;}
  memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t actual=hb_face_process(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&actual,&want,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guards+=3;}
 same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
 printf("{\"event\":\"owned_face\",\"checks\":%u,\"mismatches\":%u,\"original_calls\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"status222\":%u,\"status223\":%u,\"status225\":%u,\"status247\":%u,\"face_owned\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls,stateful,guards,statuses[222],statuses[223],statuses[225],statuses[247],failures?"false":"true");return failures?1:0;}
