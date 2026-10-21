/* SPDX-License-Identifier: MIT
 * Same-process comparisons against unmodified original white-LUT routines. */
#include "hb_white_lut.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000,T=81*16,G=32};
static unsigned checks,failures,expand_calls,prepare_calls,stateful_calls,guard_checks;
static unsigned status30,status33,active_changes,restores;
static uint32_t rng=0x20261022;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){
    ++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;
        printf("{\"white_lut_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}
}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){
    char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);
}
static void points(unsigned char*p,unsigned n,unsigned t,unsigned axis){
    for(unsigned j=0;j<n;++j){
        unsigned start=t%3==0?0:5,end=t%3==0?80:70;
        unsigned ix=n>1?start+(end-start)*j/(n-1):start;
        if(t%11==0&&j==1)ix=start;
        if(t%13==0&&j==2)ix=start;
        uint32_t r=7000+axis*350+j*71,b=16000-axis*200-j*97,dist=500+axis*100+j*19;
        if(t%7==0){r=next();b=next();dist=next();}
        if(t%17==0){r=100+j*1000;b=8000-j*31;}
        if(t%19==0){r=8000+j*31;b=100+j*1000;}
        if(t%23==0){r=12000-j*2000;b=14000-j*1900;dist=100;}
        w32(p+16*j,2000+100*ix+(t%5==0&&ix<80?39:0));
        w32(p+16*j+4,r);w32(p+16*j+8,b);w32(p+16*j+12,dist);
    }
}
static void configuration(unsigned char*k,unsigned t){
    unsigned n=t%16,axes=1+(t/16)%6;k[0xc88]=(unsigned char)n;points(k+0xc8c,n,t,0);k[0xd7c]=(unsigned char)axes;
    for(unsigned i=0;i<axes;++i){unsigned char*p=k+0xd80+248*i;wf(p,(float)i*0.75f);p[4]=(unsigned char)n;points(p+8,n,t,i);}
}
typedef struct{unsigned char*c,*k,*pre,*ref,*cfg_before;uint32_t(*prepare)(int);const char*dir;} prep_state;
static void compare_prepare(prep_state*s,unsigned t,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->cfg_before,s->k,K);
    uint32_t a=s->prepare(0);memcpy(s->ref,s->c,C);
    same("original_config_immutable",t,s->k,s->cfg_before,K);memcpy(s->c,s->pre,C);
    uint32_t b=hb_white_lut_prepare(s->c,s->k);
    same("prepare_status",t,&a,&b,4);same("prepare_context",t,s->ref,s->c,C);same("owned_config_immutable",t,s->k,s->cfg_before,K);
    status30+=a==30;status33+=a==33;++prepare_calls;
    if(!a&&memcmp(s->pre+0x344,s->c+0x344,T)){if(s->pre[0x990dc]==1)++active_changes;else ++restores;}
    if(capture){dump(s->dir,"white_prepare_input",t,s->pre,C);dump(s->dir,"white_prepare_config",t,s->k,K);dump(s->dir,"white_prepare_original",t,s->ref,C);dump(s->dir,"white_prepare_owned",t,s->c,C);}
}
int hb_run_white_lut_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;
    unsigned char *base=malloc(C),*pre=malloc(C),*ref=malloc(C),*cfg=malloc(K),*k=malloc(K),*kb=malloc(K),rb[R];
    if(!base||!pre||!ref||!cfg||!k||!kb)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t(*expand)(int,const void*,unsigned,void*)=(void*)(bias+0x4ab960);
    prep_state s={c,k,pre,ref,kb,sym(h,"scene_awb_stat_e_nd_white_lut_proc"),dir};
    unsigned char p[15*16],pi[sizeof p],original[T+2*G],owned[T+2*G],initial[T+2*G];
    for(unsigned t=0;t<1024;++t){
        unsigned n=t%16;memset(p,0xa6,sizeof p);points(p,n,t,0);memcpy(pi,p,sizeof p);
        memcpy(c,base,C);for(unsigned j=0;j<60;++j)c[0x308+j]=(unsigned char)next();memcpy(pre,c,C);
        for(unsigned j=0;j<sizeof initial;++j)initial[j]=(unsigned char)next();memcpy(original,initial,sizeof initial);memcpy(owned,initial,sizeof initial);
        uint32_t a=expand(0,p,n,original+G);memcpy(ref,c,C);memcpy(c,pre,C);
        uint32_t b=hb_white_lut_expand(c,p,n,owned+G);
        same("expand_status",t,&a,&b,4);same("expand_context",t,ref,c,C);same("expand_output_and_canaries",t,original,owned,sizeof original);same("points_immutable",t,pi,p,sizeof p);
        same("original_prefix_guard",t,original,initial,G);same("original_suffix_guard",t,original+G+T,initial+G+T,G);
        status30+=a==30;status33+=a==33;++expand_calls;
        if(t<4||t==34||t==51||t==69){dump(dir,"white_expand_points",t,p,sizeof p);dump(dir,"white_expand_original",t,original,sizeof original);dump(dir,"white_expand_owned",t,owned,sizeof owned);dump(dir,"white_expand_original_context",t,ref,C);dump(dir,"white_expand_owned_context",t,c,C);}
    }
    /* Gate flags, baseline restoration, interpolation endpoints/interiors,
     * above-range fallback, non-1 flags, empty tables and numerical extremes. */
    static const float values[]={-1,0,0.0001f,0.375f,0.75f,1.125f,1.5f,3.75f,4,INFINITY,-INFINITY,NAN};
    for(unsigned t=0;t<1024;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);configuration(k,t);
        for(unsigned j=0;j<60+2*T;++j)c[0x308+j]=(unsigned char)next();
        unsigned group=(t/16)%8;c[0x990dc]=group==0?0:group==1?2:1;c[0xd4c2]=group==2?0:group==3?2:1;c[0xd4c0]=group==1?2:0;wf(c+0xd4bc,2.5f);wf(c+0x990d8,values[(t/3)%12]);
        if(group==4)k[0xd7c]=0;
        compare_prepare(&s,t,t<8||t==82||t==83||t==1023);
    }
    /* Carry both tables/cache flags across active -> inactive transitions. */
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);configuration(k,67);k[0xd7c]=4;
    for(unsigned i=0;i<4;++i){unsigned char*q=k+0xd80+248*i;wf(q,(float)i);q[4]=3;points(q+8,3,67,i);}
    for(unsigned t=0;t<256;++t){c[0x990dc]=t%5?1:0;c[0xd4c2]=t%7?1:0;wf(c+0x990d8,(float)(t%19)*0.25f);compare_prepare(&s,2000+t,t<4);++stateful_calls;}
    /* Guard checks are owned-only, deliberately excluded from equivalence. */
    for(unsigned t=0;t<9;++t){
        memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);configuration(k,67);c[0x990dc]=0;c[0xd4c0]=0;
        memset(p,0,sizeof p);points(p,3,67,0);memcpy(owned,initial,sizeof initial);unsigned n=3;
        if(t==0)n=16;else if(t==1)w32(p,1999);else if(t==2)w32(p+32,10001);
        else if(t==3)k[0xc88]=16;else if(t==4)w32(k+0xc8c,1999);
        else{c[0x990dc]=1;c[0xd4c2]=1;wf(c+0x990d8,0.375f);k[0xd7c]=2;
            if(t==5)k[0xd84]=16;else if(t==6)k[0xd84+248]=2;else if(t==7)wf(k+0xd80+248,INFINITY);else k[0xc88]=8;}
        memcpy(pre,c,C);memcpy(kb,k,K);uint32_t status=t<3?hb_white_lut_expand(c,p,n,owned+G):hb_white_lut_prepare(c,k),unsupported=HB_PREP_UNSUPPORTED;
        same("guard_status",t,&status,&unsupported,4);same("guard_context",t,pre,c,C);same("guard_config",t,kb,k,K);same("guard_output",t,initial,owned,sizeof owned);guard_checks+=4;
    }
    same("original_config_preserved",0,config,cfg,K);same("reawb_preserved",0,reawb,rb,R);memcpy(c,base,C);
    printf("{\"event\":\"owned_white_lut\",\"checks\":%u,\"mismatches\":%u,\"expand_calls\":%u,\"prepare_calls\":%u,\"stateful_calls\":%u,\"status_30_calls\":%u,\"status_33_calls\":%u,\"successful_active_table_changes\":%u,\"successful_baseline_restores\":%u,\"owned_only_guard_checks\":%u,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,expand_calls,prepare_calls,stateful_calls,status30,status33,active_changes,restores,guard_checks,failures?"false":"true");
    return failures?1:0;
}
