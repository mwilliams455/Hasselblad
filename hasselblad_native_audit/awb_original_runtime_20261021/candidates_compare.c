/* SPDX-License-Identifier: MIT
 * Direct original/owned candidate-stage comparisons with generated boundary
 * fixtures. Actual firmware config remains unchanged; edited tables are private
 * test copies. No fixtures are described as captured camera frames.
 */
#include "hb_scene_candidates.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static uint32_t rng=0x4a7d2026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static unsigned checks,failures,weights,accumulations,temperatures,curves,interpolations,controllers,errors[256];
static unsigned spectral_distributions,spectral_ratios,spectral_states;
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=16){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;
        printf("{\"candidate_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}
}
static void status(const char*s,unsigned t,uint32_t a,uint32_t b){equal(s,t,&a,&b,4);if(a<256)++errors[a];}
static void make_curve(unsigned char *p,int tint){
    memset(p,0,580);p[1]=4;
    const uint32_t cts[]={2000,3500,6000,10000};const int32_t ts[]={-700,-100,200,900};
    for(unsigned i=0;i<4;++i){unsigned char *q=p+4+72*i;w32(q,cts[i]);q[4]=4;
        for(unsigned j=0;j<4;++j){if(tint){w32(q+8+8*j,(uint32_t)ts[j]);q[12+8*j]=(unsigned char)(16+i*13+j*31);}
            else{w16(q+8+8*j,(uint16_t)(j*80));w32(q+12+8*j,16+i*57+j*71);}}
    }
}
static void make_spectral(unsigned char *p){
    memset(p,0,4+4*40);p[0]=4;
    for(unsigned i=0;i<4;++i){unsigned char *q=p+4+40*i;w32(q,i*1000000);q[4]=4;
        for(unsigned j=0;j<4;++j){w16(q+6+4*j,(uint16_t)(j==3?8000:j*2500));w16(q+8+4*j,(uint16_t)(10+(i*61+j*37)%245));}}
}
int hb_run_candidate_tests(void*h,unsigned char*ctx,void*config,void*reawb,const char*dir){
    (void)dir;uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t(*ip)(uint32_t,uint32_t,uint32_t,uint32_t,float)=sym(h,"scene_awb_interp2_opt");
    uint32_t(*temp)(int,uint32_t,uint32_t,uint32_t,uint32_t,float*,float*)=sym(h,"scene_awb_color_temperature_compute");
    uint32_t(*cw[2])(const void*,uint32_t,uint32_t,uint32_t*)={(void*)(bias+0x4a91f8),(void*)(bias+0x4a9420)};
    uint32_t(*weight)(int,const void*,int,int)=(void*)(bias+0x4a7d00);
    uint32_t(*accum)(int,int,int,const void*,const void*,uint32_t,int)=(void*)(bias+0x4a88a0);
    uint32_t(*scene)(int)=sym(h,"scene_awb_scene_proc");
    uint32_t(*specdist)(int,const void*,void*)=sym(h,"scene_awb_scene_spec_ct_weight_ct_dis");
    uint32_t(*specratio)(int,const void*,uint32_t,void*)=sym(h,"scene_awb_scene_spec_ct_weight_ratio");
    uint32_t(*specstate)(int,int)=sym(h,"scene_awb_scene_compute_spec_ct_weight");
    unsigned char *base=malloc(C),*owned=malloc(C),*cfg=malloc(K),*originalcfg=malloc(K),*rr=malloc(R);
    if(!base||!owned||!cfg||!originalcfg||!rr)return 71;
    memcpy(base,ctx,C);memcpy(originalcfg,config,K);if(reawb)memcpy(rr,reawb,R);
    const uint32_t edge[]={0,1,2,4095,4096,65535,65536,0x7fffffff,0x80000000,0xffffffff};
    for(unsigned t=0;t<2048;++t){uint32_t a=t<100?edge[t%10]:next(),b=t<100?edge[t/10]:next(),y=next(),z=next();float x=(float)(t%2?next():a);
        uint32_t p=ip(a,b,y,z,x),q=hb_interp_opt(a,b,y,z,x);++interpolations;equal("interpolation",t,&p,&q,4);}
    for(unsigned t=0;t<2048;++t){
        memcpy(ctx,base,C);uint32_t r,b;
        if(t<81){r=u32(ctx+0x348+16*t);b=u32(ctx+0x34c+16*t);}
        else if(t<181){r=edge[(t-81)%10];b=edge[(t-81)/10];}
        else{r=next();b=next();}
        if(t%97==0)for(unsigned i=0;i<81;++i){w32(ctx+0x348+16*i,4096);w32(ctx+0x34c+16*i,4096);}
        float x[2]={123,456},y[2]={123,456};uint32_t a=temp(0,0,r,4096,b,&x[0],&x[1]),c=hb_candidate_temperature(ctx,0,r,4096,b,&y[0],&y[1]);++temperatures;
        status("temperature_status",t,a,c);equal("temperature_values",t,x,y,sizeof x);
    }
    unsigned char curve[580],evcurves[4+3*580],params[508];
    for(unsigned t=0;t<1024;++t){unsigned tint=t%2;make_curve(curve,(int)tint);if(t%13==0)curve[1]=0;else if(t%11==0)for(unsigned j=0;j<4;++j)curve[8+72*j]=0;
        uint32_t temperature=t<81?2000+100*t:next()%14000,value=tint?(uint32_t)((int32_t)(next()%2001)-1000):next()%65536;
        uint32_t x=0x98765432,y=x,a=cw[tint](curve,temperature,value,&x),b=hb_candidate_curve(curve,temperature,value,&y,(int)tint);++curves;
        status("curve_status",t,a,b);equal("curve_value",t,&x,&y,4);
    }
    unsigned char spectral[164],sa[81],sb[81];
    for(unsigned t=0;t<256;++t){make_spectral(spectral);unsigned char *p=spectral+4+40*(t%4);
        if(t%17==0)p[4]=0;else if(t%13==0)p[4]=1;else if(t%11==0)w16(p+10,u32(p+6)&65535);
        for(unsigned i=0;i<4;++i)w16(p+8+4*i,(uint16_t)(next()%65536));
        memset(sa,0xa5,81);memcpy(sb,sa,81);uint32_t a=specdist(0,p,sa),b=hb_spectral_distribution(p,sb);++spectral_distributions;
        status("spectral_distribution_status",t,a,b);equal("spectral_distribution_values",t,sa,sb,81);
    }
    for(unsigned t=0;t<256;++t){make_spectral(spectral);if(t%13==0)spectral[0]=0;
        else if(t%17==0)for(unsigned j=0;j<4;++j)w16(spectral+14+40*j,0);
        uint32_t ratio=t<64?t*100000:next();memset(sa,0xa5,81);memcpy(sb,sa,81);
        uint32_t a=specratio(0,spectral,ratio,sa),b=hb_spectral_ratio(spectral,ratio,sb);++spectral_ratios;
        status("spectral_ratio_status",t,a,b);equal("spectral_ratio_values",t,sa,sb,81);
    }
    for(unsigned t=0;t<64;++t){
        memcpy(ctx,base,C);memcpy(cfg,originalcfg,K);memcpy(ctx+0xb2028,&cfg,8);unsigned slot=t%2;
        cfg[0x139e2c]=(unsigned char)(t%11!=0);cfg[0x139e2e]=(unsigned char)(t%13!=0);cfg[0x252c+slot*0xa278]=1;
        w32(ctx+0xc5a0,t%7!=0);unsigned n=t%9==0?1024:t%9;w16(ctx+0x3761e,(uint16_t)n);
        w32(cfg+0x2530+slot*0xa278,t%5==0?0:t%5==1?n+3:t%5);
        for(unsigned i=0;i<n;++i)w32(ctx+0x37620+4*i,next());make_spectral(cfg+0x2534+slot*0xa278);
        memcpy(owned,ctx,C);uint32_t a=specstate(0,(int)slot),b=hb_scene_spec_weight(owned,cfg,slot);++spectral_states;
        status("spectral_state_status",t,a,b);equal("spectral_state_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<96;++t){
        memcpy(ctx,base,C);memcpy(cfg,originalcfg,K);memcpy(ctx+0xb2028,&cfg,8);
        unsigned slot=t%4,sceneid=t%8,count=t%17==0?0:1024;size_t off=slot*0x10188+sceneid*0x2020;
        w32(ctx+0x18,32);w32(ctx+0x1c,count/32);w32(ctx+0x28,count);ctx[0x990dc]=(unsigned char)(t%3==0);
        wf(ctx+0x37618,(float)(t%31));memset(params,0,sizeof params);params[0x58]=(unsigned char)(t%3);
        for(unsigned j=0;j<params[0x58];++j){unsigned char*z=params+0x5c+j*52;
            w32(z,1000);w32(z+4,16000);w32(z+8,1000);w32(z+12,16000);
            w32(z+20,1800);w32(z+28,11000);w32(z+36,2200);w32(z+44,14000);z[48]=(unsigned char)(70+j*40);}
        cfg[0x138748]=(unsigned char)(t%2);cfg[0x2678+slot*0xa278]=1;cfg[0x16edcc]=(unsigned char)(t%4!=0);cfg[0x16edcd]=(unsigned char)(t%40);
        for(unsigned j=0;j<64;++j)w16(cfg+0x16edce +2*j,(uint16_t)(j%8==0?0:next()));
        for(unsigned j=1;j<=6;++j){unsigned char*z=cfg+slot*0xa278+(j-1)*0x1228+0x267c;
            w32(z,t%23==0?j+1:j);z[4]=(unsigned char)(t%7!=0);z[5]=(unsigned char)(t%19==0?0:3);
            for(unsigned k=0;k<3;++k){make_curve(z+8+580*k,0);z[8+580*k]=(unsigned char)(k*12);}}
        for(unsigned i=0;i<count;++i){unsigned row=i%81;unsigned char*d=ctx+0xf450+40*i;
            w32(d,t%5==0?next():u32(ctx+0x348+16*row));w32(d+8,t%5==0?next():u32(ctx+0x34c+16*row));w32(d+12,2000+100*row);w32(d+16,row);
            d[24]=(unsigned char)(i%3!=0);wf(d+28,(float)(i%9)/8);w32(d+36,next());
            ctx[0x1734+slot*0xa71+sceneid*81+row]=(unsigned char)(row%9==0?0:64+row);
            ctx[0x3be2c+i]=(unsigned char)(i%8);w16(ctx+0x3862c+2*(count*(i%8)+i),(uint16_t)(i%300));
            w16(ctx+0x3dace +off+2*i,(uint16_t)(i%13));
        }
        memcpy(owned,ctx,C);uint32_t a=weight(0,t==0?NULL:params,(int)sceneid,(int)slot),b=hb_candidate_weight(owned,cfg,t==0?NULL:params,sceneid,slot);++weights;
        status("weight_status",t,a,b);equal("weight_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<128;++t){
        memcpy(ctx,base,C);unsigned slot=t%4,sceneid=t%8,count=t%17==0?0:1024;size_t off=slot*0x10188+sceneid*0x2020;
        w32(ctx+0x18,32);w32(ctx+0x1c,count/32);w32(ctx+0x28,count);ctx[0x3761c]=(unsigned char)(t%25);
        memset(params,0,sizeof params);w32(params,3);w32(params+4,t%13==0?3:19);params[10]=7;params[11]=99;
        memset(evcurves,0,sizeof evcurves);evcurves[0]=(unsigned char)(t%17==0?0:3);
        for(unsigned j=0;j<3;++j){make_curve(evcurves+4+580*j,1);evcurves[4+580*j]=(unsigned char)(j*12);
            if(t%19==0)evcurves[5+580*j]=0;else if(t%23==0)for(unsigned k=0;k<4;++k)evcurves[12+580*j+72*k]=0;}
        for(unsigned i=0;i<count;++i){unsigned char*d=ctx+0xf450+40*i;unsigned row=(t+i)%81;
            w32(d,t%7==0?next():u32(ctx+0x348+16*row));w32(d+8,t%7==0?next():u32(ctx+0x34c+16*row));w32(d+20,next());
            w16(ctx+0x3dace +off+2*i,(uint16_t)(t%5==0?0:i%5?1+next()%65535:0));}
        memcpy(owned,ctx,C);unsigned fraction=t%3==0?0:t%3==1?4:255;
        uint32_t a=accum(0,(int)sceneid,(int)slot,params,evcurves,0,(int)fraction),b=hb_candidate_accumulate(owned,params,evcurves,sceneid,slot,0,fraction);++accumulations;
        status("accum_status",t,a,b);equal("accum_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<32;++t){
        memcpy(ctx,base,C);unsigned count=t%7==0?0:1024;w32(ctx+0x18,32);w32(ctx+0x1c,count/32);w32(ctx+0x28,count);
        w16(ctx+0x3da50,(uint16_t)(t&1));w16(ctx+0x3da52,(uint16_t)((t>>1)&1));ctx[0x3761c]=(unsigned char)(t%25);
        for(unsigned i=0;i<count;++i){unsigned row=(t*3+i/256)%81;unsigned char*d=ctx+0xf450+40*i;
            w32(d,u32(ctx+0x348+16*row));w32(d+8,u32(ctx+0x34c+16*row));w32(d+12,2000+100*row);w32(d+16,row);d[24]=1;wf(d+28,1);w32(d+36,2048);}
        memcpy(owned,ctx,C);uint32_t a=scene(0),b=hb_normal_scene(owned,originalcfg);++controllers;
        status("normal_scene_status",t,a,b);equal("normal_scene_context",t,ctx,owned,C);
    }
    equal("config_unchanged",0,config,originalcfg,K);if(reawb)equal("reawb_handle_unchanged",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_candidates\",\"all_passed\":%s,\"failures\":%u,\"checks\":%u,\"interpolation_calls\":%u,"
           "\"temperature_calls\":%u,\"curve_calls\":%u,\"weight_calls\":%u,\"accumulation_calls\":%u,\"normal_controller_calls\":%u,"
           "\"spectral_distribution_calls\":%u,\"spectral_ratio_calls\":%u,\"spectral_state_calls\":%u,\"status_45\":%u,"
           "\"status_40\":%u,\"status_53\":%u,\"status_54\":%u,\"status_55\":%u,\"status_56\":%u,\"status_57\":%u,\"status_59\":%u,\"status_61\":%u,"
           "\"synthetic_fixtures\":true,\"real_device_calibration_recovered\":false}\n",
           failures?"false":"true",failures,checks,interpolations,temperatures,curves,weights,accumulations,controllers,
           spectral_distributions,spectral_ratios,spectral_states,errors[45],errors[40],errors[53],errors[54],errors[55],errors[56],errors[57],errors[59],errors[61]);
    return failures?1:0;
}
