/* SPDX-License-Identifier: MIT
 * Synthetic same-process comparisons against the unmodified original.
 * Full user comparison replaces only the calibration import prefix. */
#include "hb_user_prepare.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
uint32_t hb_original_user_remainder(uintptr_t);
static unsigned checks,failures,getter_calls,manual_calls,base_calls,mode_calls,prefix_calls,stateful_calls,guard_checks;
static unsigned errors83,errors84,remainder_calls,base_imports,end_imports,temp_imports;
static uint32_t rng=0x20261023;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void *sym(void*h,const char*n){void*p=dlsym(h,n);if(!p)_exit(3);return p;}
static void same(const char*n,unsigned t,const void*a,const void*b,size_t size){
    ++checks;if(!memcmp(a,b,size))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<size&&x[i]==y[i])++i;
        printf("{\"user_prepare_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",n,t,i,x[i],y[i]);}
}
static void dump(const char*d,const char*n,unsigned t,const void*p,size_t size){
    char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",d,n,t)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,size,f)!=size)_exit(74);fclose(f);
}
static void gains(unsigned char*c,unsigned t){
    w32(c+0x1a0,t%3);w32(c+0x1bc,3500+t);
    for(unsigned j=0;j<2;++j){unsigned char*p=c+0x1a4+12*j;
        w32(p,t%7==0?UINT32_MAX-100+j*50:2000+6000*j);
        w32(p+4,t%5==0?next():t%11==0?0:3000+900*j+t);
        w32(p+8,t%5==0?next():t%13==0?0:8000-900*j+t);}
}
static void manual(unsigned char*k,unsigned t){
    k[0x139cbc]=(unsigned char)(t%16);
    for(unsigned j=0;j<15;++j){unsigned char*p=k+0x139cc0+16*j;w32(p,1500+700*j);
        w32(p+4,t%5?4000+71*j:next());w32(p+8,t%5?7000-97*j:next());w32(p+12,next());}
}
static void rows(unsigned char*p,unsigned t){
    for(unsigned j=0;j<2;++j){unsigned char*q=p+20*j;
        w32(q,t%5==0?UINT32_MAX-40*j:t%5==1?4500:7500-5000*j);
        for(unsigned v=0;v<4;++v)w32(q+4+4*v,t%7==0?(next()|1u):3000+59*t+73*j+113*v);}
}
static void requests(unsigned char*c,unsigned char*k,unsigned t){
    static const unsigned char flags[]={0,1,2,255};
    c[0xb1430]=t%8<6?1:flags[t%4];c[0xb1434]=(unsigned char)(t%3);rows(c+0xb1438,t);manual(k,t);
    unsigned groups=(t/3)%3;w16(c+0xb14c0,(uint16_t)groups);
    for(unsigned g=0;g<2;++g){unsigned char*p=c+0xb1460+48*g;p[0]=t%11==g?flags[(t/11)%4]:1;p[4]=(unsigned char)((t+g)%3);rows(p+8,t+g+1);}
    c[0xb1d98]=t%9<7?1:flags[t%4];unsigned n=1+t%2;w32(c+0xb1d9c,n|(t%5==0?0xfedcba00u:0));
    for(unsigned j=0;j<2;++j){unsigned char*p=c+0xb1da0+84*j;w32(p,t%3==0?UINT32_MAX-17*j:t%3==1?5000:8000-6000*j);
        for(unsigned v=0;v<10;++v){w32(p+4+4*v,t%7?4096+37*v+13*j:(next()|1u));w32(p+44+4*v,t%7?4096+17*v+23*j:(next()|1u));}}
    /* Error at every input channel, both rows, each stage, and after earlier
     * stages publish. Other cases include duplicate/reversed unsigned keys. */
    unsigned fault=t%16;
    if(fault<4&&c[0xb1434])w32(c+0xb1438+20*(c[0xb1434]-1)+4+4*fault,0);
    if(fault>=4&&fault<8&&groups){unsigned char*p=c+0xb1460+48*(groups-1);if(p[4])w32(p+8+20*(p[4]-1)+4+4*(fault-4),0);}
    if(fault==8||fault==9)w32(c+0xb1da0+84*(n-1)+(fault==8?4:44)+4*((t/16)%10),0);
}
typedef struct{unsigned char*c,*k,*r,*pre,*ref,*ki,*kr;unsigned char ri[R],rr[R];uintptr_t bias;uint32_t(*user)(int);const char*dir;} state;
static void compare_prefix(state*s,unsigned t,unsigned capture){
    memcpy(s->pre,s->c,C);memcpy(s->ki,s->k,K);memcpy(s->ri,s->r,R);
    uint32_t a=s->user(0);memcpy(s->ref,s->c,C);memcpy(s->kr,s->k,K);memcpy(s->rr,s->r,R);
    memcpy(s->c,s->pre,C);memcpy(s->k,s->ki,K);memcpy(s->r,s->ri,R);
    uint32_t b=hb_user_prepare_prefix(s->c,s->k);
    if(capture)dump(s->dir,"user_prefix_boundary",t,s->c,C);
    base_imports+=s->pre[0xb1430]==1&&s->c[0xb1430]==0&&memcmp(s->pre+0x19c,s->c+0x19c,32)!=0;
    for(unsigned g=0;g<2;++g)end_imports+=s->pre[0xb1460+48*g]==1&&s->c[0xb1460+48*g]==0&&memcmp(s->pre+0x1f4+44*g,s->c+0x1f4+44*g,44)!=0;
    temp_imports+=s->pre[0xb1d98]==1&&s->c[0xb1d98]==0&&memcmp(s->pre+0xc5a4,s->c+0xc5a4,96)!=0;
    if(!b){++remainder_calls;b=hb_original_user_remainder(s->bias+0x4b1624);}
    same("prefix_status",t,&a,&b,4);same("prefix_context",t,s->ref,s->c,C);same("prefix_config",t,s->kr,s->k,K);same("prefix_reawb",t,s->rr,s->r,R);
    ++prefix_calls;errors83+=a==83;errors84+=a==84;
    if(capture){dump(s->dir,"user_prefix_input",t,s->pre,C);dump(s->dir,"user_prefix_config",t,s->ki,K);dump(s->dir,"user_prefix_original",t,s->ref,C);dump(s->dir,"user_prefix_owned_remainder",t,s->c,C);}
}
int hb_run_user_prepare_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    if(!reawb)return 71;
    unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),rb[R];
    state s={.c=c,.k=k,.r=reawb,.pre=malloc(C),.ref=malloc(C),.ki=malloc(K),.kr=malloc(K),.dir=dir};
    if(!base||!cfg||!k||!s.pre||!s.ref||!s.ki||!s.kr)return 71;
    memcpy(base,c,C);memcpy(cfg,config,K);memcpy(rb,reawb,R);
    s.bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;s.user=sym(h,"scene_awb_user_proc");
    uint32_t(*getter)(int,uint32_t,uint32_t*,uint32_t*)=sym(h,"scene_awb_stat_get_calib_gain");
    uint32_t(*refresh)(int)=sym(h,"scene_awb_manual_lut_calib_update"),(*import)(int)=(void*)(s.bias+0x4aed50);
    void(*mode)(int)=(void*)(s.bias+0x4b0780);
    static const uint32_t ct[]={0,1999,2000,2001,3500,7999,8000,8001,10000,UINT32_MAX-100,UINT32_MAX-51,UINT32_MAX};
    for(unsigned t=0;t<384;++t){memcpy(c,base,C);gains(c,t);memcpy(s.pre,c,C);uint32_t aout[4]={17,29,31,43},bout[4];memcpy(bout,aout,sizeof bout);
        unsigned bi=t%4==0?1:2;uint32_t a=getter(0,ct[(t/3)%12],aout+1,aout+bi);memcpy(s.ref,c,C);memcpy(c,s.pre,C);
        uint32_t b=hb_user_calibration_gain(c,ct[(t/3)%12],bout+1,bout+bi);
        same("gain_status",t,&a,&b,4);same("gain_context",t,s.ref,c,C);same("gain_outputs_and_canaries",t,aout,bout,sizeof aout);++getter_calls;
    }
    for(unsigned t=0;t<256;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);gains(c,t);manual(k,t);memcpy(s.pre,c,C);memcpy(s.ki,k,K);
        uint32_t a=refresh(0);memcpy(s.ref,c,C);same("manual_original_config",t,k,s.ki,K);memcpy(c,s.pre,C);
        uint32_t b=hb_user_manual_lut_refresh(c,k);same("manual_status",t,&a,&b,4);same("manual_context",t,s.ref,c,C);same("manual_owned_config",t,k,s.ki,K);++manual_calls;
        if(t<3){dump(dir,"manual_input",t,s.pre,C);dump(dir,"manual_config",t,k,K);dump(dir,"manual_original",t,s.ref,C);dump(dir,"manual_owned",t,c,C);}
    }
    for(unsigned t=0;t<256;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);requests(c,k,t);memcpy(s.pre,c,C);memcpy(s.ki,k,K);
        uint32_t a=import(0);memcpy(s.ref,c,C);same("base_original_config",t,k,s.ki,K);memcpy(c,s.pre,C);
        uint32_t b=hb_user_base_calibration(c,k);same("base_status",t,&a,&b,4);same("base_context",t,s.ref,c,C);same("base_owned_config",t,k,s.ki,K);++base_calls;errors83+=a==83;
        if(t<3||t==10){dump(dir,"base_input",t,s.pre,C);dump(dir,"base_config",t,k,K);dump(dir,"base_original",t,s.ref,C);dump(dir,"base_owned",t,c,C);}
    }
    static const unsigned char flags[]={0,1,2,255};
    for(unsigned t=0;t<256;++t){memcpy(c,base,C);c[0xb14e8]=flags[t%4];w32(c+0x194,t%7);w32(c+0x198,next());w32(c+0xb14ec,t%3==0?t%7:next());
        c[0xb14c4]=flags[(t/4)%4];c[0xb14cc]=flags[(t/16)%4];c[0xb14d8]=flags[(t/64)%4];c[0xb14c5]=71;c[0xb14cd]=72;c[0xb14d9]=73;memcpy(s.pre,c,C);
        mode(0);memcpy(s.ref,c,C);memcpy(c,s.pre,C);hb_user_mode_switch(c);same("mode_context",t,s.ref,c,C);++mode_calls;
    }
    for(unsigned t=0;t<384;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);requests(c,k,t);compare_prefix(&s,t,t<12||t==383);}
    memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);memcpy(reawb,rb,R);
    for(unsigned t=0;t<128;++t){if(t%2==0)requests(c,k,t+1000);compare_prefix(&s,1000+t,t<4);++stateful_calls;}
    /* Deliberately unsupported shapes: owned-only, no original invocation. */
    for(unsigned t=0;t<8;++t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);requests(c,k,10);
        if(t==0){c[0xb1430]=1;c[0xb1434]=3;}else if(t==1){c[0xb1430]=1;k[0x139cbc]=16;}
        else if(t==2)w16(c+0xb14c0,3);else if(t==3){w16(c+0xb14c0,1);c[0xb1460]=1;c[0xb1464]=3;}
        else if(t==4||t==5){c[0xb1d98]=1;w32(c+0xb1d9c,t==4?0:3);}else w32(c+0x1a0,3);
        memcpy(s.pre,c,C);memcpy(s.ki,k,K);uint32_t ro=19,bo=23,status=t<6?hb_user_prepare_prefix(c,k):t==6?hb_user_calibration_gain(c,5000,&ro,&bo):hb_user_manual_lut_refresh(c,k),want=HB_PREP_UNSUPPORTED;
        same("guard_status",t,&status,&want,4);same("guard_context",t,c,s.pre,C);same("guard_config",t,k,s.ki,K);guard_checks+=3;
    }
    same("initial_config_preserved",0,config,cfg,K);memcpy(c,base,C);memcpy(reawb,rb,R);
    printf("{\"event\":\"owned_user_prepare\",\"checks\":%u,\"mismatches\":%u,\"getter_calls\":%u,\"manual_calls\":%u,\"base_calls\":%u,\"mode_calls\":%u,\"full_user_comparisons\":%u,\"stateful_calls\":%u,\"original_user_remainder_calls\":%u,\"status_83_calls\":%u,\"status_84_calls\":%u,\"changed_base_imports\":%u,\"changed_e_nd_imports\":%u,\"changed_temperature_imports\":%u,\"owned_only_guard_checks\":%u,\"full_user_owned\":false,\"synthetic_inputs\":true,\"all_passed\":%s}\n",checks,failures,getter_calls,manual_calls,base_calls,mode_calls,prefix_calls,stateful_calls,remainder_calls,errors83,errors84,base_imports,end_imports,temp_imports,guard_checks,failures?"false":"true");
    return failures?1:0;
}
