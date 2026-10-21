/* SPDX-License-Identifier: MIT */
#include "hb_detect.h"
#include "hb_stat_prepare.h"
#include "detect_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls,errors106,errors131,errors177,errors247,stateful,guards;
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
 if(failures<=30){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"detect_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki;uint32_t(*original)(int);const char*dir;} state;
static void compare(state*s,unsigned t,unsigned capture){
 memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=s->original(0);memcpy(s->ref,s->c,C);
 same("original_config",t,s->ki,s->k,K);memcpy(s->c,s->pre,C);uint32_t b=hb_detect_process(s->c,s->k);
 same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("owned_config",t,s->ki,s->k,K);++calls;errors106+=a==106;errors131+=a==131;errors177+=a==177;errors247+=a==247;
 if(capture||a!=b||memcmp(s->ref,s->c,C)){dump(s->dir,"detect_input",t,s->pre,C);dump(s->dir,"detect_config",t,s->ki,K);dump(s->dir,"detect_original",t,s->ref,C);dump(s->dir,"detect_owned",t,s->c,C);}
}
int hb_run_detect_tests(void*h,unsigned char*c,void*config,const char*dir){
 unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.dir=dir};
 if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki)return 71;memcpy(base,c,C);memcpy(cfg,config,K);s.original=dlsym(h,"scene_awb_detect_proc");if(!s.original)return 3;
 for(unsigned t=0;t<112;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_detect(c,k,t,0);compare(&s,t,1);}
 for(unsigned t=0;t<64;++t){if(!t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_detect(c,k,47,0);}hd_wf(c+0x37618,(float)(t%27));hd_w32(c+0xb0c04,2000+t*123);for(unsigned i=0;i<6;++i)hd_w16(c+0x9c1ac+2*i,(i*23+t*17)%257);compare(&s,2000+t,t<4||t==63);++stateful;}
 memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);compare(&s,3000,1);
 for(unsigned t=0;t<12;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_detect(c,k,47,0);
  switch(t){case 0:hd_w32(c+0x28,1025);break;case 1:hd_w32(c+0x18,1025);break;case 2:k[0x1348f9]=5;break;case 3:k[0x134b6c]=9;break;case 4:k[0x134b74]=9;break;case 5:k[0x13994c]=9;break;case 6:k[0x136549]=2;break;case 7:k[0x1366f2]=3;break;case 8:k[0x1366f4]=2;break;case 9:hd_w32(c+0xc454,15);break;case 10:k[0x138600]=9;break;case 11:c[0xc4cc]=4;break;}
  memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t a=hb_detect_process(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guards+=3;}
 same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
 printf("{\"event\":\"owned_detection\",\"checks\":%u,\"mismatches\":%u,\"original_calls\":%u,\"empty_region_status106\":%u,\"history_reset_status131\":%u,\"semantic_empty_status177\":%u,\"hysteresis_empty_status247\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"detection_owned\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls,errors106,errors131,errors177,errors247,stateful,guards,failures?"false":"true");return failures?1:0;
}
