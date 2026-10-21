/* SPDX-License-Identifier: MIT */
#include "hb_sensor.h"
#include "hb_stat_prepare.h"
#include "sensor_fixtures.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800};
static unsigned checks,failures,calls[3],stateful,guards;
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
 if(failures<=24){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"sensor_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*pre,*ref,*ki,*kr;uint32_t(*proc)(int),(*pass)(int),(*gain)(int,uint32_t,void*);const char*dir;} state;
static void compare(state*s,unsigned t,unsigned kind,unsigned capture){
 unsigned char aout[40],bout[40];memset(aout,0x91,40);memset(bout,0x91,40);
 memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);uint32_t a=kind==0?s->gain(0,t%12*1000,aout):kind==1?s->pass(0):s->proc(0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);
 memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);uint32_t b=kind==0?hb_sensor_calibration(s->c,t%12*1000,bout):kind==1?hb_sensor_parameter_pass(s->c):hb_sensor_process(s->c,s->k);
 same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);same("gains",t,aout,bout,40);++calls[kind];
 if(capture||a!=b||memcmp(s->ref,s->c,C)){dump(s->dir,"sensor_input",t,s->pre,C);dump(s->dir,"sensor_config",t,s->ki,K);dump(s->dir,"sensor_original",t,s->ref,C);dump(s->dir,"sensor_owned",t,s->c,C);if(kind==0){dump(s->dir,"sensor_original_gains",t,aout,40);dump(s->dir,"sensor_owned_gains",t,bout,40);}}
}
int hb_run_sensor_tests(void*h,unsigned char*c,void*config,const char*dir){
 unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K);state s={.c=c,.k=k,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
 if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;memcpy(base,c,C);memcpy(cfg,config,K);
 s.proc=dlsym(h,"scene_awb_spec_sensor_proc");s.pass=dlsym(h,"scene_awb_spec_sensor_param_pass_for_reawb");s.gain=dlsym(h,"scene_awb_spec_sensor_calib_gain_calc");if(!s.proc||!s.pass||!s.gain)return 3;
 for(unsigned t=0;t<96;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_sensor(c,k,t%61);
  if(t>=61){unsigned seed=0x640301+t;hb_test_sensor(c,k,50);unsigned sv=t==61?256:3+t%17;hs_w16(k+0x13bdf8,sv);
   for(unsigned z=0;z<sv;++z){unsigned char*r=k+0x13be10+140*z;for(unsigned j=0;j<3;++j){seed=1664525*seed+1013904223;hs_wf(r+4*j,((int)(seed%2001)-1000)/137.0f);}r[12]=t==61?15:t%16;
    for(unsigned j=0;j<r[12];++j){r[16+8*j]=j+1;seed=1664525*seed+1013904223;hs_wf(r+20+8*j,(seed%2001)/997.0f);}}
   hs_w16(k+0x13be0c,sv/3);hs_w16(k+0x13be0e,sv/3);hs_w16(k+0x13be10,sv-2*(sv/3));
   for(unsigned i=0;i<3;++i){seed=1664525*seed+1013904223;hs_wf(k+0x13bde0+4*i,((int)(seed%401)-200)/31.0f);hs_wf(k+0x13bdec+4*i,((int)(seed%101)-50)/13.0f);}
   if(t>=90){unsigned count=t==90?1:8;k[0x144a14]=3;
    for(unsigned i=0;i<3;++i){unsigned char*r=k+0x144a18+0x1248*i;r[0]=i;r[4]=count;
     for(unsigned j=0;j<count;++j){unsigned char*a=r+8+0x248*j;hs_w32(a,100*j);a[4]=count;
      for(unsigned z=0;z<count;++z){unsigned char*b=a+8+0x48*z;hs_w32(b,2000+1000*z);b[4]=count;
       for(unsigned y=0;y<count;++y){hs_w32(b+8+8*y,20*y);hs_w16(b+12+8*y,15*i+21*j+5*z+7*y);}}}}
    hs_wf(c+0x37618,t==92?700:t==93?NAN:550);}
  }
  compare(&s,t,2,1);}
 for(unsigned kind=0;kind<2;++kind)for(unsigned t=0;t<48;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_sensor(c,k,10);c[0xc5a8]=t%3;
  if(t>=36){hs_w32(c+0xc5ac,6000);hs_w32(c+0xc5d8,3000);}for(unsigned i=0;i<22;++i)c[0xb200a+i]=(unsigned char)(i*7+t);compare(&s,1000+kind*100+t,kind,t<12);}
 for(unsigned t=0;t<48;++t){if(!t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_sensor(c,k,50);}k[0x139e38]=1;c[0x9c1bd]=t%9!=0;hs_w32(c+0x9c1a0,60+t);hs_w32(c+0x9c1b8,59+t);for(unsigned i=0;i<10;++i)hs_w16(c+0x9c1cc+2*i,100+23*t+31*i);compare(&s,2000+t,2,t<5||t==47);++stateful;}
 memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);compare(&s,3000,2,1);
 for(unsigned t=0;t<13;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_sensor(c,k,50);
  switch(t){case 0:c[0xc5a8]=3;break;case 1:k[0x13bdd8]=4;break;case 2:hs_w16(k+0x13bdf8,257);break;case 3:k[0x13be1c]=16;break;case 4:hs_w16(k+0x13be0c,257);break;case 5:k[0x1480f4]=2;break;case 6:k[0x144a14]=4;break;case 7:k[0x144a18]=3;break;case 8:k[0x144a1c]=0;break;case 9:k[0x144a24]=9;break;case 10:k[0x144a2c]=0;break;case 11:k[0x144a2c]=9;break;case 12:k[0x144a1c]=9;break;}
  memcpy(s.pre,c,C);uint32_t a=hb_sensor_process(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&a,&want,4);same("guard_context",t,c,s.pre,C);guards+=2;}
 uint32_t a=s.gain(0,0,NULL),b=hb_sensor_calibration(c,0,NULL);same("null_gain_output",0,&a,&b,4);++calls[0];
 same("initial_config_immutable",0,config,cfg,K);memcpy(c,base,C);
 printf("{\"event\":\"owned_spectral_sensor\",\"checks\":%u,\"mismatches\":%u,\"gain_calls\":%u,\"parameter_pass_calls\":%u,\"processing_calls\":%u,\"stateful_calls\":%u,\"owned_only_guard_checks\":%u,\"sensor_adaptation_owned\":true,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,calls[0],calls[1],calls[2],stateful,guards,failures?"false":"true");return failures?1:0;
}
