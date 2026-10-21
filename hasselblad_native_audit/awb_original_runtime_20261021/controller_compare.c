/* SPDX-License-Identifier: MIT
 * Full original/owned scene-stage tests. Gates/config variations are synthetic;
 * no generated test is presented as a recovered camera frame. */
#include "hb_scene_controller.h"
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,interp_calls,gate_calls,ct_calls,spec_calls,scene_calls,scene_ok,sequence_calls,sequence_ok,authentic_config_calls,dense_scene_calls,errors[256];
static uint32_t rng=0x4a756026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=24){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;
        printf("{\"controller_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}
}
static void status(const char*s,unsigned t,uint32_t x,uint32_t y){equal(s,t,&x,&y,4);if(x<256)++errors[x];}
static void dump(const char *dir,const char *name,const void*p,size_t n){char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
static void make_post(unsigned char *p,unsigned variant){
    memset(p,0,196);p[0]=(unsigned char)(variant*10);p[1]=4;
    for(unsigned i=0;i<4;++i){unsigned char*q=p+4+24*i;w32(q,2000+2500*i);q[4]=4;
        for(unsigned j=0;j<4;++j){q[5+2*j]=(unsigned char)(j*80);q[6+2*j]=(unsigned char)(15+variant*17+i*19+j*13);}}
}
static void make_spectral(unsigned char *p){
    memset(p,0,164);p[0]=4;for(unsigned i=0;i<4;++i){unsigned char*q=p+4+40*i;w32(q,i*1000000);q[4]=4;
        for(unsigned j=0;j<4;++j){w16(q+6+4*j,(uint16_t)(j==3?8000:j*2500));w16(q+8+4*j,(uint16_t)(15+i*43+j*17));}}
}
static void setup(unsigned char *ctx,unsigned char *cfg,const unsigned char *base,const unsigned char *original,unsigned t){
    memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);
    unsigned count=t>=128&&t<144?4096:t%23==0?0:1024,width=count==4096?64:32;w32(ctx+0x18,width);w32(ctx+0x1c,count/width);w32(ctx+0x28,count);
    unsigned ev=4+t%32;ctx[0x3761c]=(unsigned char)ev;wf(ctx+0x37618,(float)ev+0.25f);
    for(unsigned slot=0;slot<4;++slot){
        w16(ctx+0x3da50+slot*2,(uint16_t)((t&(1u<<slot))?1+t%256:0));
        w32(ctx+0x841bc+slot*0x74,2000+100*(t%81));w32(ctx+0x841cc+slot*0x74,t%19==0?0xffff0000u+slot:slot*7);
        for(unsigned scene=0;scene<8;++scene)for(unsigned row=0;row<81;++row)ctx[0x1734+slot*0xa71+scene*81+row]=(unsigned char)(64+row);
        if(slot<2){unsigned n=cfg[0x1540+slot*0xa278];for(unsigned i=0;i<n;++i){unsigned char*p=cfg+0x154c+slot*0xa278+508*i;w32(p,0);w32(p+4,40);}continue;}
        size_t o=(slot-2)*0x2bd0;cfg[0x15a30+o]=(unsigned char)(t%17==0?2:t%11==0?0:1);w32(cfg+0x15a34+o,t%3);
        cfg[0x15c88+o]=(unsigned char)(t%19==0?0:t%16==15?8:2);cfg[0x15c89+o]=(unsigned char)(t%29==0?0:64);cfg[0x15c8a+o]=(unsigned char)(t%31==0?255:4);
        memcpy(cfg+0x15c8c+o,original+0x154c,8*508);memcpy(cfg+0x16db8+o,original+0xa594,4644);
        for(unsigned i=0;i<8;++i){unsigned char*p=cfg+0x15c8c+o+508*i;w32(p,t%13==0?100:0);w32(p+4,t%13==0?110:40);}
        cfg[0x17fdc+o]=(unsigned char)(t%7==0?0:3);for(unsigned j=0;j<3;++j)make_post(cfg+0x17fe0+o+196*j,j);
        cfg[0x16c6c+o]=(unsigned char)(t%2);w32(cfg+0x16c70+o,t%20);make_spectral(cfg+0x16c74+o);
        if(t%37==0)cfg[0x16db8+o]=0;
        if(t%41==0)w32(cfg+0x15a34+o,3);
    }
    cfg[0x139e2c]=(unsigned char)(t%2);cfg[0x139e2e]=1;w32(ctx+0xc5a0,t%3!=0);w16(ctx+0x3761e,16);
    for(unsigned i=0;i<16;++i)w32(ctx+0x37620+4*i,10000+i*1000);
    for(unsigned i=0;i<count;++i){unsigned row=(10+t+i/128)%81;unsigned char*d=ctx+0xf450+40*i;
        w32(d,u32(ctx+0x348+16*row));w32(d+8,u32(ctx+0x34c+16*row));w32(d+12,2000+100*row);w32(d+16,row);d[24]=1;wf(d+28,1);w32(d+36,2048);}
}
int hb_run_controller_tests(void*h,unsigned char*ctx,void*config,void*reawb,const char*dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t(*interp)(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t*,float)=sym(h,"scene_awb_interp2");
    uint32_t(*gate)(int,int,const void*,uint32_t*)=(void*)(bias+0x4a97a8);
    uint32_t(*ctcurve)(int,int,const void*,uint32_t*)=(void*)(bias+0x4a9640);
    uint32_t(*spectral)(int,int)=sym(h,"scene_awb_scene_compute_spec_ct_sp_weight");
    uint32_t(*scene)(int)=sym(h,"scene_awb_scene_proc");
    float table[124];memcpy(table,(void*)(bias+0x6ce418),sizeof table);hb_temperature_model model={table};dump(dir,"isotemperature_table.bin",table,sizeof table);
    unsigned char *base=malloc(C),*owned=malloc(C),*cfg=malloc(K),*original=malloc(K),*rr=malloc(R);
    if(!base||!owned||!cfg||!original||!rr)return 71;memcpy(base,ctx,C);memcpy(original,config,K);if(reawb)memcpy(rr,reawb,R);
    for(unsigned t=0;t<4096;++t){uint32_t x0=next(),x1=t%11==0?x0:next(),y0=next(),y1=next();float v=t%7==0?NAN:t%3==0?(float)x0:(float)next();
        uint32_t a=0x12345678,b=a,x=interp(x0,x1,y0,y1,&a,v),y=0;b=hb_scene_interpolate(x0,x1,y0,y1,v);++interp_calls;
        status("interpolate_status",t,x,y);equal("interpolate_value",t,&a,&b,4);}
    unsigned char post[196];
    for(unsigned t=0;t<2048;++t){memcpy(ctx,base,C);make_post(post,t%3);unsigned slot=t%4;
        unsigned char*p=post+4+24*(t%4);p[4]=(unsigned char)(t%13==0?0:4);w16(ctx+0x3da50+2*slot,(uint16_t)(t<512?t%512:next()));
        uint32_t a=0x12345678,b=a,x=gate(0,(int)slot,p,&a),y=hb_special_gate_curve(ctx,0,slot,p,&b);++gate_calls;
        status("gate_status",t,x,y);equal("gate_value",t,&a,&b,4);
    }
    for(unsigned t=0;t<1024;++t){memcpy(ctx,base,C);make_post(post,t%3);unsigned slot=t%4;
        if(t%17==0)post[1]=0;else if(t%13==0)for(unsigned j=0;j<4;++j)post[8+24*j]=0;
        w16(ctx+0x3da50+slot*2,(uint16_t)(t%300));w32(ctx+0x841bc+slot*0x74,t<256?t*50:next());
        uint32_t a=0x12345678,b=a,x=ctcurve(0,(int)slot,post,&a),y=hb_special_ct_curve(ctx,0,slot,post,&b);++ct_calls;
        status("ct_curve_status",t,x,y);equal("ct_curve_value",t,&a,&b,4);
    }
    for(unsigned t=0;t<128;++t){memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);unsigned slot=2+t%2;size_t o=(slot-2)*0x2bd0;
        cfg[0x139e2c]=(unsigned char)(t%11!=0);cfg[0x139e2e]=(unsigned char)(t%13!=0);cfg[0x16c6c+o]=1;
        w32(ctx+0xc5a0,t%7!=0);unsigned n=t%9==0?1024:t%9;w16(ctx+0x3761e,(uint16_t)n);w32(cfg+0x16c70+o,t%5==0?0:t%5==1?n+3:t%5);
        for(unsigned i=0;i<n;++i)w32(ctx+0x37620+4*i,next());make_spectral(cfg+0x16c74+o);
        if(t%17==0)for(unsigned j=0;j<4;++j)w16(cfg+0x16c74+o+14+40*j,0);
        memcpy(owned,ctx,C);uint32_t x=spectral(0,(int)slot),y=hb_special_spectral_weight(owned,cfg,slot);++spec_calls;
        status("special_spectral_status",t,x,y);equal("special_spectral_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<256;++t){setup(ctx,cfg,base,original,t);
        if(t==14||t==15)wf(ctx+0x37618,NAN);
        if(t==42)for(unsigned i=0;i<cfg[0x1540+0xa278];++i){w32(cfg+0x154c+0xa278+i*508,100);w32(cfg+0x1550+0xa278+i*508,110);}
        memcpy(owned,ctx,C);uint32_t x=scene(0),y=hb_scene_process(owned,cfg,&model,0);++scene_calls;scene_ok+=x==0;
        dense_scene_calls+=t>=128&&t<144;
        status("full_scene_status",t,x,y);equal("full_scene_context",t,ctx,owned,C);
        if(t>=4&&t<=7){char name[96];snprintf(name,sizeof name,"scene_%u_original.bin",t);dump(dir,name,ctx,C);snprintf(name,sizeof name,"scene_%u_owned.bin",t);dump(dir,name,owned,C);}
    }
    for(unsigned t=0;t<16;++t){memcpy(ctx,base,C);for(unsigned slot=0;slot<4;++slot)w16(ctx+0x3da50+slot*2,(uint16_t)((t>>slot)&1));
        memcpy(owned,ctx,C);uint32_t x=scene(0),y=hb_scene_process(owned,original,&model,0);++authentic_config_calls;
        status("authentic_config_gates_status",t,x,y);equal("authentic_config_gates_context",t,ctx,owned,C);
    }
    setup(ctx,cfg,base,original,15);memcpy(owned,ctx,C);
    for(unsigned t=0;t<12;++t){for(unsigned slot=0;slot<4;++slot){w16(ctx+0x3da50+slot*2,(uint16_t)(10+t*17));w16(owned+0x3da50+slot*2,(uint16_t)(10+t*17));}
        ctx[0x3761c]=owned[0x3761c]=(unsigned char)(6+t);wf(ctx+0x37618,6.25f+(float)t);wf(owned+0x37618,6.25f+(float)t);
        uint32_t x=scene(0),y=hb_scene_process(owned,cfg,&model,0);++sequence_calls;sequence_ok+=x==0;status("stateful_scene_status",t,x,y);equal("stateful_scene_context",t,ctx,owned,C);
    }
    dump(dir,"stateful_scene_original.bin",ctx,C);dump(dir,"stateful_scene_owned.bin",owned,C);
    equal("original_config_unchanged",0,config,original,K);if(reawb)equal("passive_reawb_unchanged",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_scene_controller\",\"all_passed\":%s,\"checks\":%u,\"failures\":%u,\"interpolation_calls\":%u,\"gate_curve_calls\":%u,\"ct_curve_calls\":%u,"
           "\"spectral_calls\":%u,\"scene_calls\":%u,\"scene_successes\":%u,\"stateful_scene_calls\":%u,\"stateful_successes\":%u,\"authentic_config_gate_calls\":%u,\"dense_scene_calls\":%u,"
           "\"status_38\":%u,\"status_40\":%u,\"status_45\":%u,\"status_57\":%u,\"status_73\":%u,\"status_91\":%u,\"status_94\":%u,"
           "\"synthetic_fixtures\":true,\"real_device_calibration_recovered\":false}\n",failures?"false":"true",checks,failures,interp_calls,gate_calls,ct_calls,spec_calls,scene_calls,scene_ok,sequence_calls,sequence_ok,authentic_config_calls,dense_scene_calls,errors[38],errors[40],errors[45],errors[57],errors[73],errors[91],errors[94]);
    return failures?1:0;
}
