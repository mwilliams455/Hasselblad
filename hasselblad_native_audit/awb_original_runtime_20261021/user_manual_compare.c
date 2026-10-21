/* SPDX-License-Identifier: MIT */
#include "hb_user_manual.h"
#include "hb_user_e_nd.h"
#include "hb_stat_prepare.h"
#include "user_manual_fixtures.h"
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
uint32_t hb_original_user_remainder(uintptr_t);
static unsigned checks,failures,leaves,updates,users,stateful,guards,selected,empty;
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;printf("{\"manual_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);}
typedef struct{unsigned char*c,*k,*r,*pre,*ref,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;uint32_t(*original[4])(int);hb_temperature_model model;const char*dir;} state;
static void compare(state*s,unsigned kind,unsigned t,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    uint32_t a=s->original[kind](0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
    memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    uint32_t b=kind==0?hb_e_nd_update_temperature(s->c,s->k):kind==1?hb_e_nd_update_unit(s->c):kind==2?hb_e_nd_update_golden(s->c,s->k):hb_user_prepare_calibration(s->c,s->k);
    if(kind==3&&!b){b=hb_user_manual_samples(s->c,s->k,&s->model);selected+=s->c[0xb0ff0]==1;empty+=s->c[0xb0ff0]==0;
        if(capture)dump(s->dir,"manual_owned_boundary",t,s->c,C);if(!b)b=hb_original_user_remainder(s->bias+0x4b16a8);}
    same("status",t,&a,&b,4);same("context",t,s->ref,s->c,C);same("config",t,s->kr,s->k,K);same("reawb",t,s->rr,s->r,R);
    if(kind==3)++users;else ++updates;
    if(capture){dump(s->dir,"manual_input",t,s->pre,C);dump(s->dir,"manual_config",t,s->ki,K);dump(s->dir,"manual_original",t,s->ref,C);dump(s->dir,"manual_owned",t,s->c,C);}
}
int hb_run_user_manual_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rb[R];
    state s={.c=c,.k=k,.r=reawb,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    s.original[0]=sym(h,"scene_awb_stat_update_e_nd_temp_calib_gain");s.original[1]=sym(h,"scene_awb_stat_update_e_nd_unit_calib_gain");s.original[2]=sym(h,"scene_awb_stat_update_e_nd_golden_calib_gain");s.original[3]=sym(h,"scene_awb_user_proc");
    float table[124];memcpy(table,(void*)(s.bias+0x6ce418),sizeof table);s.model.isotemperature_31x4=table;dump(dir,"manual_isotemperature",0,table,sizeof table);
    uint32_t(*ct)(const void*,uint32_t,uint32_t*,uint32_t*)=sym(h,"scene_awb_stat_e_nd_get_golden_ct_calib_gain");
    uint32_t(*amount)(const void*,uint32_t,float,uint32_t*,uint32_t*)=sym(h,"scene_awb_stat_e_nd_get_golden_e_nd_val_calib_gain");
    static const float values[]={-INFINITY,-1,0,1,2,3.5f,15,100,INFINITY,NAN};
    for(unsigned kind=0;kind<2;++kind)for(unsigned t=0;t<160;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_manual_tables(c,k,t);unsigned char*p=k+0x16e64c+(kind?0:4);memcpy(s.ki,k,K);
        uint32_t ao[4]={11,22,33,44},bo[4];memcpy(bo,ao,sizeof bo);unsigned bi=t%3==0?1:2;uint32_t wanted=t%4==0?UINT32_MAX:t%4==1?0:1500+t*43;
        if(t%7==0){hb_manual_w32(k+0x16e658,UINT32_MAX);hb_manual_w32(k+0x16e65c,0x80000000);memcpy(s.ki,k,K);}
        uint32_t a=kind?amount(p,wanted,values[t%10],ao+1,ao+bi):ct(p,wanted,ao+1,ao+bi),b=kind?hb_e_nd_golden_amount_gain(p,wanted,values[t%10],bo+1,bo+bi):hb_e_nd_golden_ct_gain(p,wanted,bo+1,bo+bi);
        same("leaf_status",t,&a,&b,4);same("leaf_outputs_canaries",t,ao,bo,sizeof ao);same("leaf_immutable",t,k,s.ki,K);++leaves;
    }
    for(unsigned kind=0;kind<3;++kind)for(unsigned t=0;t<160;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_manual_tables(c,k,t);
        if(t>=128){hb_manual_wf(c+0x990d8,values[t%10]);hb_manual_wf(c+0x990e0,values[(t/3)%10]);hb_manual_wf(c+0x990d4,values[(t/7)%10]);}
        compare(&s,kind,1000+kind*200+t,t<3);
    }
    for(unsigned t=0;t<192;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);hb_test_manual_request(c,k,t);
        if(t>=176){hb_manual_wf(c+0x990d8,values[t%10]);hb_manual_wf(c+0x990e0,values[(t/3)%10]);}
        if(t>=168&&t<176){k[0x1332bc]=1;memset(k+0x1332c4,0,36);}
        compare(&s,3,2000+t,t<16||t>=168);
    }
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);
    for(unsigned t=0;t<32;++t){if(t%2==0)hb_test_manual_request(c,k,t);compare(&s,3,3000+t,t<4);++stateful;}
    for(unsigned t=0;t<12;++t){memcpy(c,base,C);memcpy(k,cfg,K);hb_test_manual_request(c,k,7);c[0x24c]=c[0x278]=c[0x2f4]=1;
        if(t==0)hb_manual_w16(c+0xb14f4,65);if(t==1)hb_manual_w32(c+0x28,1025);if(t==2)c[0x1a0]=3;
        if(t==3)k[0x16e940]=0;if(t==4)k[0x16e940]=9;if(t==5)k[0x16e944]=0;if(t==6)c[0x27a]=0;if(t==7)c[0x27e]=9;
        if(t==8)k[0x16e649]=0;if(t==9)k[0x16e64d]=9;if(t==10)k[0x16e654]=0;
        memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t b=hb_user_manual_samples(c,k,t==11?NULL:&s.model),want=HB_PREP_UNSUPPORTED;
        same("guard_status",t,&b,&want,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guards+=3;
    }
    same("original_config_preserved",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rb,R);
    printf("{\"event\":\"owned_user_manual\",\"checks\":%u,\"mismatches\":%u,\"golden_leaf_calls\":%u,\"e_nd_update_calls\":%u,\"full_user_comparisons\":%u,\"stateful_calls\":%u,\"selected_sample_results\":%u,\"empty_sample_results\":%u,\"owned_only_guard_checks\":%u,\"full_user_owned\":false,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,leaves,updates,users,stateful,selected,empty,guards,failures?"false":"true");return failures?1:0;
}
