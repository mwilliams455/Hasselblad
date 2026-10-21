/* SPDX-License-Identifier: MIT
 * Differential checks using initialized, same-process clones. Firmware stays
 * unmodified; synthetic state and raw dumps stay outside the public repository. */
#include "hb_completion.h"
#include "hb_post_controller.h"
#include "hb_scene_controller.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum { C=920560,K=1502800,R=1000 };
uint32_t hb_original_prepared_completion(uintptr_t,unsigned char*,uint32_t,uintptr_t);
static unsigned checks,failures,passive_routes[3],save_cases,recovery_cases;
static uint32_t rng=0xc0212026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void randomize(void*p,size_t n){unsigned char*b=p;for(size_t i=0;i<n;++i)b[i]=(unsigned char)next();}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void same(const char*s,unsigned t,const void*a,const void*b,size_t n){++checks;if(!memcmp(a,b,n))return;++failures;if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;printf("{\"completion_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}}
static void dump(const char*dir,const char*stage,unsigned t,const void*p,size_t n){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",dir,stage,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);}
static void results(unsigned char*c){randomize(c+0xb0c40,0x280);randomize(c+0xd3d0,0xac);}
int hb_run_completion_tests(void*h,unsigned char*c,void*config,void*handle,const char*dir){
    if(!handle)return 71;
    unsigned char*r=handle,*base=malloc(C),*owned=malloc(C),*input=malloc(C),*cfg=malloc(K),*k=malloc(K),rbase[R],ro[R],ri[R];
    if(!base||!owned||!input||!cfg||!k)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(k,config,K);memcpy(rbase,r,R);
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    const char*names[]={"scene_awb_copy_result_to_confirm_result","scene_awb_copy_confirm_result_to_result","scene_awb_copy_ref_result_to_result","scene_awb_copy_ref_result_to_confirm_result"};
    uint32_t(*copy[4])(int);for(unsigned i=0;i<4;++i)copy[i]=sym(h,names[i]);
    uint32_t(*shading)(int)=sym(h,"scene_awb_calc_shading_ct_proc"),(*passive)(int)=sym(h,"scene_awb_reawb_proc");
    for(unsigned kind=0;kind<4;++kind)for(unsigned t=0;t<128;++t){memcpy(c,base,C);results(c);memcpy(owned,c,C);uint32_t a=copy[kind](0),b=hb_result_copy(owned,(enum hb_result_copy)kind);same("copy_status",t,&a,&b,4);same("copy_context",t,c,owned,C);}
    for(unsigned t=0;t<1024;++t){memcpy(c,base,C);c[0xb0b10]=t<768?1:(unsigned char)(t-768);for(unsigned i=0;i<7;++i)w16(c+0x3da42+2*i,t%4==0?100:t%4==1?(i==t%7?65535:0):(uint16_t)next());
        w32(c+0xeff8,0xaabbcc00u+(t%3==0?3:7));w32(c+0xeffc,t%4==0?59:t%4==1?60:next());w32(c+0xf008,next());w32(c+0xb0b6c,next());w32(c+0xb2164,next());memcpy(owned,c,C);
        uint32_t a=shading(0),b=hb_shading_temperature(owned);same("shading_status",t,&a,&b,4);same("shading_context",t,c,owned,C);if(t<4){dump(dir,"shading_original",t,c,C);dump(dir,"shading_owned",t,owned,C);}}
    for(unsigned t=0;t<768;++t){memcpy(c,base,C);memcpy(r,rbase,R);unsigned route=t%3;
        r[0x1c]=route?1:(t%2?0:2);r[0x1d]=t%4==0?1:t%4==1?2:0;r[0x1e]=0xa5;r[0x22]=route==2?(t%2?0:2):1;
        w32(c+0x194,route==1?1+t%12:0);w32(c+0x28,t%5==0?0:t%5==1?1:4096);w16(c+0xb142c,t%5==1?16:(uint16_t)(t%123));
        randomize(c+0xb6968,40);c[0xb6968]=(unsigned char)((t/3)%3);randomize(c+0xa86d0,64);w32(r+0x3b4,t%7==0?UINT32_MAX:next());memcpy(input,c,C);memcpy(owned,c,C);memcpy(ri,r,R);memcpy(ro,r,R);
        uint32_t a=passive(0),b=hb_reawb_passive(owned,ro);same("passive_status",t,&a,&b,4);same("passive_context",t,c,owned,C);same("passive_handle",t,r,ro,R);++passive_routes[route];save_cases+=ri[0x1d]==1;
        if(t<12){dump(dir,"passive_input",t,input,C);dump(dir,"passive_original",t,c,C);dump(dir,"passive_owned",t,owned,C);dump(dir,"passive_handle_input",t,ri,R);dump(dir,"passive_handle_original",t,r,R);dump(dir,"passive_handle_owned",t,ro,R);}}
    static const uint32_t statuses[]={0,40,151,UINT32_MAX};static const unsigned char requests[]={0,1,2,255};
    for(unsigned t=0;t<512;++t){memcpy(c,base,C);results(c);w32(c+0x174,next());c[0xd338]=requests[(t/4)%4];memcpy(input,c,C);memcpy(owned,c,C);uint32_t status=statuses[t%4];hb_completion_record info;
        uint32_t a=hb_original_prepared_completion(bias+0x4722b0,c,status,bias+0x791348),b=hb_outer_complete(owned,status,&info);same("outer_status",t,&a,&b,4);same("outer_context",t,c,owned,C);
        unsigned expected=c[0xd338]==0&&input[0xd338]==1?HB_REFERENCE_PUBLISHED:status?HB_CONFIRMED_RESTORED:HB_LIVE_PUBLISHED;unsigned actual=info.origin;same("outer_origin",t,&expected,&actual,4);
        if(t<16){dump(dir,"outer_input",t,input,C);dump(dir,"outer_original",t,c,C);dump(dir,"outer_owned",t,owned,C);}}
    /* Stateful publication and recovery reuse the preceding confirmed record. */
    memcpy(c,base,C);results(c);
    for(unsigned t=0;t<192;++t){randomize(c+0xb0c48,312);w32(c+0x174,2);c[0xd338]=t%11==0?1:0;memcpy(owned,c,C);uint32_t status=statuses[t%4];uint32_t a=hb_original_prepared_completion(bias+0x4722b0,c,status,bias+0x791348),b=hb_outer_complete(owned,status,NULL);same("stateful_outer_status",t,&a,&b,4);same("stateful_outer_context",t,c,owned,C);memcpy(c,owned,C);}
    float table[124];memcpy(table,(void*)(bias+0x6ce418),sizeof table);hb_temperature_model model={table};
    /* Execute real post/scene failure -> branch -> cleanup -> return in the
     * original controller, starting at the documented prepared stage entry.
     * No patched functions, forced returns, or mocked status callbacks. */
    for(unsigned kind=0;kind<2;++kind){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(r,rbase,R);results(c);w32(c+0x194,0);w32(c+0x174,2);c[0xd338]=0;c[0xd47c]=0;w32(c+0xb0c4c,0);
        memset(c+0xb0bac,0,156);memset(c+0x84164,0,4*0x74);memset(c+0x3da50,0,8);w32(c+0x28,0);
        if(kind){w16(c+0x3da50,1);k[0x139e2c]=0;k[0x1540]=1;w32(k+0x154c,100);w32(k+0x1550,101);c[0x3761c]=0;}
        memcpy(input,c,C);memcpy(owned,c,C);memcpy(ro,r,R);uint32_t inner=kind?hb_scene_process(owned,k,&model,0):hb_post_process(owned,k,&model,ro),expected=kind?40:151;
        same("real_failure_inner_status",kind,&inner,&expected,4);if(inner!=expected)return 1;
        uint32_t b=hb_outer_complete(owned,inner,NULL),a=hb_original_prepared_completion(bias+(kind?0x471f80:0x471fb0),c,0,bias+0x791348);
        same("real_failure_outer_status",kind,&a,&b,4);same("real_failure_context",kind,c,owned,C);same("real_failure_reawb_skipped",kind,r,ro,R);++recovery_cases;
        dump(dir,"failure_input",kind,input,C);dump(dir,"failure_config",kind,k,K);dump(dir,"failure_original",kind,c,C);dump(dir,"failure_owned",kind,owned,C);dump(dir,"failure_reawb",kind,r,R);}
    /* Unsupported ownership guards are not original equivalence claims. */
    for(unsigned kind=0;kind<2;++kind){memcpy(c,base,C);memcpy(r,rbase,R);r[0x1c]=kind?0:1;r[0x1d]=kind?1:0;r[0x22]=1;w32(c+0x194,0);w32(c+0x28,4096);w16(c+0xb142c,123);memcpy(owned,c,C);memcpy(ro,r,R);uint32_t a=hb_reawb_passive(c,r),b=HB_PREP_UNSUPPORTED;same("unsupported_guard",kind,&a,&b,4);same("unsupported_context_immutable",kind,c,owned,C);same("unsupported_handle_immutable",kind,r,ro,R);}
    same("original_config_immutable",0,config,cfg,K);memcpy(c,base,C);memcpy(r,rbase,R);
    printf("{\"event\":\"owned_completion_and_passive_reawb\",\"checks\":%u,\"mismatches\":%u,\"copy_cases\":512,\"shading_cases\":1024,\"passive_routes\":[%u,%u,%u],\"save_without_linked_storage_cases\":%u,\"outer_cases\":512,\"stateful_completion_calls\":192,\"original_prepared_failure_paths\":%u,\"owned_only_guard_checks\":6,\"all_passed\":%s,\"full_controller_owned\":false,\"active_reawb_owned\":false,\"synthetic_inputs\":true}\n",checks,failures,passive_routes[0],passive_routes[1],passive_routes[2],save_cases,recovery_cases,failures?"false":"true");return failures?1:0;
}
