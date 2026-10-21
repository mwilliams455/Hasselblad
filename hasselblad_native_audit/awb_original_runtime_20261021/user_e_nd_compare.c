/* SPDX-License-Identifier: MIT */
#include "hb_user_e_nd.h"
#include "hb_stat_prepare.h"
#include "user_e_nd_fixtures.h"
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
uint32_t hb_original_user_remainder(uintptr_t);
static unsigned checks,failures,row_calls,temp_calls,request_calls,user_calls,stateful_calls,guards,accepted,rejected,partial,remainder_calls;
static uint32_t rng=0x20261024;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"user_e_nd_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
static void tables(unsigned char*k,unsigned t){
    unsigned n=t%9;k[0x16e940]=(unsigned char)n;
    for(unsigned i=0;i<8;++i){unsigned char*p=k+0x16e942+52*i;memset(p,0,52);hb_test_w16(p,(uint16_t)(t%7==0?30-10*(int)i:t%11==0?20:-30+10*(int)i));p[2]=(unsigned char)(1+(t/9)%8);p[3]=(unsigned char)t;
        for(unsigned j=0;j<8;++j){hb_test_w16(p+4+6*j,(uint16_t)(t%13==0?15-2*j:t%17==0?3:1+2*j));hb_test_w16(p+6+6*j,(uint16_t)next());hb_test_w16(p+8+6*j,(uint16_t)next());}}
}
static void request_case(unsigned char*c,unsigned char*k,unsigned t){
    hb_test_e_nd_request(c,k,t);c[0x990dc]=(unsigned char)(t%4);c[0x278]=71;c[0x279]=72;
    unsigned char*a=c+0xb1f8c,*p=k+0x16e858+116*(t%2),*z=p+10;
    switch(t%32){
    case 1:c[0xb1f86]=0;break;case 2:c[0xb1f86]=2;break;case 3:c[0xb1f86]=255;break;
    case 4:k[0x16e854]=0;break;case 5:hb_test_w16(c+0xb1f88,99);break;
    case 6:hb_test_w16(c+0xb1f8a,3);break;case 7:hb_test_w16(a,2001);break;case 8:hb_test_w16(a+52,8001);break;
    case 9:hb_test_w16(a+2,9);break;case 10:hb_test_w16(a+54,9);break;
    case 11:hb_test_w16(a+4,2);break;case 12:hb_test_w16(a+4,2);hb_test_w16(z+4,2);break;
    case 13:hb_test_w16(a+10,4);break;
    case 14:hb_test_w16(a+6,0);break;case 15:hb_test_w16(a+12,0);break;case 16:hb_test_w16(z+6,0);break;case 17:hb_test_w16(z+12,0);break;
    case 18:hb_test_w16(a+8,0);break;case 19:hb_test_w16(a+14,0);break;case 20:hb_test_w16(z+8,0);break;case 21:hb_test_w16(z+14,0);break;
    case 22:k[0x16e940]=0;hb_test_w16(a+6,1);hb_test_w16(a+12,65535);hb_test_w16(z+6,1);hb_test_w16(z+12,1);break;
    case 23:k[0x16e940]=0;hb_test_w16(a+8,1);hb_test_w16(a+14,65535);hb_test_w16(z+8,1);hb_test_w16(z+14,1);break;
    case 24:for(unsigned i=0;i<4;++i)for(unsigned j=0;j<8;++j){hb_test_w16(k+0x16e948+52*i+6*j,65535);hb_test_w16(k+0x16e94a+52*i+6*j,65535);}for(unsigned g=0;g<2;++g)for(unsigned j=0;j<2+t%7;++j){hb_test_w16(a+52*g+6+6*j,65535);hb_test_w16(z+52*g+6+6*j,65535);hb_test_w16(a+52*g+8+6*j,65535);hb_test_w16(z+52*g+8+6*j,65535);}break;
    case 25:hb_test_w16(a+2,0);hb_test_w16(z+2,0);break;
    case 26:hb_test_w16(c+0xb1f8a,0);hb_test_w16(p+8,0);break;
    case 27:hb_test_w16(k+0x16e858,78);hb_test_w16(c+0xb1f88,78);break;
    case 28:hb_test_w16(a,8000);hb_test_w16(z,8000);hb_test_w16(a+52,2000);hb_test_w16(z+52,2000);break;
    case 29:hb_test_w16(a+8,1);hb_test_w16(z+8,65535);break;
    case 30:tables(k,t);break;case 31:hb_test_wf(p+4,NAN);break;
    default:break;}
}
typedef struct{unsigned char*c,*k,*r,*pre,*ref,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;void(*request)(int);uint32_t(*user)(int);const char*dir;} state;
static void compare_request(state*s,unsigned t,unsigned capture,unsigned full){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    uint32_t a=0;if(full)a=s->user(0);else s->request(0);
    memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
    if(s->pre[0xb1f86]==1){accepted+=s->c[0x279]==1;rejected+=s->c[0x279]==0;partial+=s->c[0x279]==0&&memcmp(s->pre+0x27a,s->c+0x27a,106)!=0;}
    memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    uint32_t b=full?hb_user_prepare_calibration(s->c,s->k):hb_user_e_nd_unit_request(s->c,s->k);
    if(full&&!b){if(capture)dump(s->dir,"e_nd_owned_user_boundary",t,s->c,C);++remainder_calls;b=hb_original_user_remainder(s->bias+0x4b162c);}
    same(full?"user_status":"request_supported",t,&a,&b,4);same("request_context",t,s->ref,s->c,C);same("request_config",t,s->kr,s->k,K);same("request_reawb",t,s->rr,s->r,R);
    if(full)++user_calls;else ++request_calls;
    if(capture){dump(s->dir,"e_nd_input",t,s->pre,C);dump(s->dir,"e_nd_config",t,s->ki,K);dump(s->dir,"e_nd_original",t,s->ref,C);dump(s->dir,"e_nd_owned",t,s->c,C);}
}
int hb_run_user_e_nd_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rb[R];
    state s={.c=c,.k=k,.r=reawb,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;s.request=(void*)(s.bias+0x4af328);s.user=sym(h,"scene_awb_user_proc");
    uint32_t(*row)(const void*,float,uint32_t*,uint32_t*)=sym(h,"scene_awb_stat_e_nd_get_temp_e_nd_value_calib_gain");
    uint32_t(*calc)(int,float,float,uint32_t*,uint32_t*)=sym(h,"scene_awb_stat_e_nd_temp_calib_gain_calc");
    static const float amounts[]={-INFINITY,-1,0,1,2,3,7.5f,15,100,INFINITY,NAN};
    static const float temperatures[]={-INFINITY,-50,-30,-20,-1,0,15.2f,20,25,30,40,100,INFINITY,NAN};
    for(unsigned t=0;t<512;++t){memcpy(c,base,C);memcpy(k,cfg,K);tables(k,t);unsigned char p[52],pi[52];memcpy(p,k+0x16e942,52);memcpy(pi,p,52);uint32_t ao[4]={11,22,33,44},bo[4];memcpy(bo,ao,sizeof bo);unsigned bi=t%3==0?1:2;
        uint32_t a=row(p,amounts[(t/8)%11],ao+1,ao+bi),b=hb_e_nd_temp_row_gain(p,amounts[(t/8)%11],bo+1,bo+bi);
        same("row_status",t,&a,&b,4);same("row_outputs_canaries",t,ao,bo,sizeof ao);same("row_immutable",t,p,pi,52);same("row_context_immutable",t,c,base,C);++row_calls;
    }
    for(unsigned t=0;t<512;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);tables(k,t);memcpy(s.ki,k,K);memcpy(s.pre,c,C);uint32_t ao[4]={11,22,33,44},bo[4];memcpy(bo,ao,sizeof bo);unsigned bi=t%3==0?1:2;
        uint32_t a=calc(0,amounts[(t/9)%11],temperatures[(t/11)%14],ao+1,ao+bi),b=hb_e_nd_temp_gain(k,amounts[(t/9)%11],temperatures[(t/11)%14],bo+1,bo+bi);
        same("temp_status",t,&a,&b,4);same("temp_outputs_canaries",t,ao,bo,sizeof ao);same("temp_config_immutable",t,k,s.ki,K);same("temp_context_immutable",t,c,s.pre,C);++temp_calls;
    }
    for(unsigned t=0;t<512;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);request_case(c,k,t);compare_request(&s,t,t<32,0);}
    for(unsigned t=0;t<256;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);request_case(c,k,t);compare_request(&s,1000+t,t<8,1);}
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);
    for(unsigned t=0;t<64;++t){if(t%2==0)request_case(c,k,t/2);compare_request(&s,2000+t,t<4,1);++stateful_calls;}
    for(unsigned t=0;t<7;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);hb_test_e_nd_request(c,k,0);c[0xb1430]=1;c[0xb1434]=0;
        if(t==0)k[0x16e854]=3;else if(t==1){hb_test_w16(c+0xb1f8a,3);hb_test_w16(k+0x16e860,3);}else if(t==2){hb_test_w16(c+0xb1f8e,9);hb_test_w16(k+0x16e864,9);}
        else if(t==3)k[0x16e940]=9;else if(t==4)k[0x16e944]=0;else if(t==5)k[0x16e944]=9;else k[0x16e944+52]=0;
        memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t status=hb_user_prepare_calibration(c,k),want=HB_PREP_UNSUPPORTED;same("guard_status",t,&status,&want,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guards+=3;
    }
    same("original_config_preserved",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rb,R);
    printf("{\"event\":\"owned_user_e_nd\",\"checks\":%u,\"mismatches\":%u,\"row_calls\":%u,\"temperature_calls\":%u,\"unit_request_calls\":%u,\"full_user_comparisons\":%u,\"stateful_calls\":%u,\"original_user_remainder_calls\":%u,\"accepted_requests\":%u,\"rejected_requests\":%u,\"rejected_with_partial_table_writes\":%u,\"owned_only_guard_checks\":%u,\"full_user_owned\":false,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,row_calls,temp_calls,request_calls,user_calls,stateful_calls,remainder_calls,accepted,rejected,partial,guards,failures?"false":"true");return failures?1:0;
}
