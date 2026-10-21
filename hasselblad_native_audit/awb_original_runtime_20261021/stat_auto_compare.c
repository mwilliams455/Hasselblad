/* SPDX-License-Identifier: MIT */
#include "hb_stat_prepare.h"
#include "user_manual_fixtures.h"
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls,unit,temp,both,stateful,guards;
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
 if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"stat_auto_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki,*kr;uint32_t(*original)(int);const char*dir;} state;
static void fixture(unsigned char*c,unsigned char*k,unsigned t){
 hb_test_manual_request(c,k,t);c[0x278]=(t%4)&1;c[0x2f4]=((t%4)>>1)&1;c[0x19c]=t%3;c[0x1a0]=t%3;
 for(unsigned j=0;j<2;++j){hb_manual_w32(c+0x1a4+12*j,2000+6000*j);hb_manual_w32(c+0x1a8+12*j,4096+211*j);hb_manual_w32(c+0x1ac+12*j,4096-177*j);}
 unsigned n=(unsigned[]){0,1,16,64,1024}[t%5],rois=t%9;hb_manual_w32(c+0x28,n);hb_manual_w32(c+0x2c,rois);
 memset(c+0xf450,0x37,40*n);
 for(unsigned i=0;i<n;++i){unsigned char*d=c+0x84f48+20*i;hb_manual_w32(d,t%13==0?UINT32_MAX:3000+13*i);hb_manual_w32(d+4,4096);hb_manual_w32(d+8,t%11==0?0x80000000:7000-3*i);hb_manual_w32(d+12,137*i);hb_manual_w32(d+16,i%7);}
 for(unsigned i=0;i<rois;++i){unsigned char*d=c+0x98f48+32*i;d[0]=(i+t)%3;hb_manual_w32(d+4,t%13==0?UINT32_MAX:3500+71*i);hb_manual_w32(d+12,4500+29*i);}
 hb_manual_wf(c+0x990d4,(float)(t%40)-10.5f);hb_manual_w32(c+0x990e4,t%9);hb_manual_wf(c+0x990e8,t%7==0?0:37.5f);for(unsigned i=0;i<8;++i)hb_manual_wf(c+0x990ec+4*i,0.25f*i);
 if(t%16==0){c[0x278]=255;c[0x2f4]=3;}
 if(t%16==1)hb_manual_wf(c+0x990d8,NAN);
 if(t%16==2)hb_manual_wf(c+0x990e0,INFINITY);
 if(t%16==3){for(unsigned i=0;i<2;++i)for(unsigned j=0;j<8;++j){hb_manual_w16(c+0x282+52*i+6*j,65535);hb_manual_w16(c+0x284+52*i+6*j,0);}}
}
static void compare(state*s,unsigned t,unsigned capture){
 memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=s->original(0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);
 memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);uint32_t b=hb_stat_auto_complete(s->c,s->k);
 same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);++calls;unit+=s->pre[0x278]!=0;temp+=s->pre[0x2f4]!=0;both+=s->pre[0x278]&&s->pre[0x2f4];
 if(capture||a!=b||memcmp(s->ref,s->c,C)){dump(s->dir,"stat_auto_input",t,s->pre,C);dump(s->dir,"stat_auto_config",t,s->ki,K);dump(s->dir,"stat_auto_original",t,s->ref,C);dump(s->dir,"stat_auto_owned",t,s->c,C);}
}
int hb_run_stat_auto_tests(void*h,unsigned char*c,void*config,const char*dir){
 unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
 if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;memcpy(base,c,C);memcpy(cfg,config,K);s.original=dlsym(h,"scene_awb_stat_auto_proc");if(!s.original)return 3;
 for(unsigned t=0;t<160;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);fixture(c,k,t);compare(&s,t,t<64||t>=152);}
 for(unsigned t=0;t<48;++t){if(!t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);fixture(c,k,43);}hb_manual_w32(c+0x1bc,1800+173*t);hb_manual_wf(c+0x990d8,(float)(t%19));hb_manual_wf(c+0x990e0,(float)t-20.5f);compare(&s,2000+t,t<4||t==47);++stateful;}
 memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);compare(&s,3000,1);
 for(unsigned t=0;t<11;++t){memcpy(c,base,C);memcpy(k,cfg,K);fixture(c,k,43);
  switch(t){case 0:hb_manual_w32(c+0x28,1025);break;case 1:hb_manual_w32(c+0x2c,9);break;case 2:c[0x1a0]=3;break;case 3:k[0xc88]=0;break;case 4:k[0xc88]=16;break;case 5:hb_manual_w32(c+0x308,81);break;case 6:c[0x27a]=0;break;case 7:c[0x27e]=9;break;case 8:k[0x16e940]=0;break;case 9:k[0x16e944]=9;break;case 10:k[0x139e2c]=k[0x139e2e]=1;hb_manual_w32(c+0x990e4,1025);break;}
  memcpy(s.pre,c,C);uint32_t a=hb_stat_auto_complete(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_context",t,c,s.pre,C);guards+=2;}
 same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
 printf("{\"event\":\"owned_complete_automatic_statistics\",\"checks\":%u,\"mismatches\":%u,\"original_calls\":%u,\"unit_enabled\":%u,\"temperature_enabled\":%u,\"both_enabled\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"automatic_statistics_owned\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls,unit,temp,both,stateful,guards,failures?"false":"true");return failures?1:0;
}
