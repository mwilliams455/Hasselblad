/* SPDX-License-Identifier: MIT
 * Synthetic atmosphere differential tests on original-initialized state. */
#include "hb_atmosphere.h"
#include "hb_history.h"
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,errors[256],stage_calls,stage_successes,authentic_calls,sequence_calls,changed_slots;
static uint32_t rng=0x41202621;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=24){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;
        printf("{\"atmosphere_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}
}
static void status(const char*s,unsigned t,uint32_t a,uint32_t b){equal(s,t,&a,&b,4);}
static void dump(const char*dir,const char*name,const void*p,size_t n){char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
static void ev_row(unsigned char*p,unsigned ev,unsigned variant){
    memset(p,0,1568);w32(p,ev);p[4]=(unsigned char)(variant%13==0?1:4);
    for(unsigned j=0;j<4;++j){unsigned char*q=p+8+104*j;w32(q,2000+j*2500);q[4]=(unsigned char)(variant%17==0?1:4);
        for(unsigned k=0;k<4;++k){w32(q+8+12*k,(uint32_t)(int32_t)((int)k*1000-1500));
            w32(q+12+12*k,3000+variant*7+j*130+k*90);w32(q+16+12*k,5200-variant*3+j*27+k*31);}}
}
static void gain_table(unsigned char*p,unsigned variant,int endvalue){
    memset(p,0,0x3104);p[endvalue?2:0]=3;
    for(unsigned j=0;j<3;++j)ev_row(p+4+1568*j,j*10+(variant%19==0?256:0),variant+j);
}
static void end_table(unsigned char*p,unsigned variant){
    memset(p,0,4+3*0x3104);p[0]=3;
    for(unsigned j=0;j<3;++j){unsigned char*q=p+4+0x3104*j;gain_table(q,variant+j,1);w16(q,(uint16_t)(j*10));}
}
static void confidence_row(unsigned char*p,unsigned confidence,unsigned variant){
    memset(p,0,0x3108);w32(p,confidence);p[4]=3;
    for(unsigned j=0;j<3;++j)ev_row(p+8+1568*j,j*10,variant+j);
}
static void category_table(unsigned char*p,unsigned variant){
    memset(p,0,0x18850);p[0]=1;w32(p+4,variant%7);w32(p+8,1+variant%5);p[12]=3;
    for(unsigned j=0;j<3;++j)confidence_row(p+16+j*0x3108,j*128,variant+j);
}
static void setup(unsigned char*ctx,unsigned char*cfg,const unsigned char*base,const unsigned char*original,unsigned t){
    memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);
    float ev=(float)(t%96)*0.25f-2.0f,end=(float)(t%100)*0.25f-1.0f;if(t==510)ev=NAN;if(t==511)end=NAN;
    wf(ctx+0x37618,ev);ctx[0x3761c]=(unsigned char)(t%24);wf(ctx+0x990d8,end);ctx[0x990dc]=(unsigned char)(t%4);w16(ctx+0x9c1ac,(uint16_t)(t%5==0?256:t%257));
    for(unsigned cat=0;cat<7;++cat)w16(ctx+0x3da42+2*cat,(uint16_t)(t%9==0?0:t*47+cat*19));
    for(unsigned slot=0;slot<4;++slot){size_t m=slot*0x74;unsigned row=(t*3+slot*17)%81;
        ctx[0x84164+m]=(unsigned char)(t%16&(1u<<slot)?(t%2?1:2):0);ctx[0x178+slot]=7;
        uint32_t r=u32(ctx+0x348+16*row),b=u32(ctx+0x34c+16*row);w32(ctx+0x84168+m,r);w32(ctx+0x84170+m,b);
        w32(ctx+0x841bc+m,t%23==0?10100:2000+100*row);wf(ctx+0x841c4+m,t%7==0?1e6f:(float)hb_temperature_distance(ctx,2000+100*row,r,b));
        cfg[0x3c+slot]=(unsigned char)(t%3);if(slot>=2)w32(cfg+0x10294+slot*0x2bd0,t%4);
        gain_table(cfg+0x1b1d0+slot*0x3104,t%100+slot,0);category_table(cfg+0x275e0+slot*0x18850,t%100+slot);
        if(t%11==1)w32(cfg+0x275e4+slot*0x18850,8);
        if(t%11==2){unsigned char*p=cfg+0x275e0+slot*0x18850;
            for(unsigned j=0;j<3;++j)for(unsigned k=0;k<3;++k)for(unsigned l=0;l<4;++l)for(unsigned q=0;q<4;++q)
                w32(p+16+0x3108*j+8+1568*k+8+104*l+12+12*q,(uint32_t)-100);}
        if(t%11==3)cfg[0x275e0+slot*0x18850]=0;
    }
    end_table(cfg+0x89720,t%100);if(t%13==0)cfg[0x89720]=0;
}
int hb_run_atmosphere_tests(void*h,unsigned char*ctx,void*config,void*reawb,const char*dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t(*interp)(int32_t,int32_t,int32_t,int32_t,int32_t*,float)=sym(h,"scene_awb_interp2_int");
    uint32_t(*evrow)(const void*,uint32_t,int32_t,uint32_t*,uint32_t*)=(void*)(bias+0x48f200);
    uint32_t(*gain)(const void*,uint32_t,uint32_t*,uint32_t*,float,float)=sym(h,"scene_awb_get_atmos_rbgain");
    uint32_t(*endvalue)(const void*,uint32_t,uint32_t*,uint32_t*,float,float)=sym(h,"scene_awb_get_e_nd_atmos_value_rbgain");
    uint32_t(*endgain)(const void*,uint32_t,uint32_t*,uint32_t*,float,float,float)=sym(h,"scene_awb_get_e_nd_atmos_rbgain");
    uint32_t(*catdist)(int,int,const void*,uint32_t*,uint32_t*)=(void*)(bias+0x490be0);
    uint32_t(*catct)(int,int,const void*,uint32_t*,uint32_t*)=(void*)(bias+0x490a58);
    uint32_t(*catev)(int,int,const void*,uint32_t*,uint32_t*)=(void*)(bias+0x4908d0);
    uint32_t(*process)(int)=sym(h,"scene_awb_atmos_proc");
    float isotemp[124];memcpy(isotemp,(void*)(bias+0x6ce418),sizeof isotemp);hb_temperature_model model={isotemp};dump(dir,"isotemperature_table.bin",isotemp,sizeof isotemp);
    unsigned char*base=malloc(C),*owned=malloc(C),*cfg=malloc(K),*original=malloc(K),*rr=malloc(R),*tables=malloc(0x18850);
    if(!base||!owned||!cfg||!original||!rr||!tables)return 71;memcpy(base,ctx,C);memcpy(original,config,K);if(reawb)memcpy(rr,reawb,R);
    for(unsigned t=0;t<4096;++t){int32_t x0=(int32_t)next(),x1=t%9==0?x0:(int32_t)next(),y0=(int32_t)next(),y1=(int32_t)next();float v=t%13==0?NAN:t%7==0?(float)x0:(float)(int32_t)next();
        int32_t a=123,b=hb_atmosphere_interpolate_signed(x0,x1,y0,y1,v);uint32_t st=interp(x0,x1,y0,y1,&a,v);status("signed_interp_status",t,st,0);equal("signed_interp_value",t,&a,&b,4);}
    for(unsigned t=0;t<2048;++t){ev_row(tables,10,t%100);uint32_t ct=t<256?t*50:next();int32_t tint=t<1024?(int32_t)t*7-3500:(int32_t)next();
        if(t%11==0)for(unsigned j=0;j<4;++j)for(unsigned k=0;k<4;++k){w32(tables+8+104*j+12+12*k,next());w32(tables+8+104*j+16+12*k,next());}
        uint32_t a=123,b=456,c=a,d=b,x=evrow(tables,ct,tint,&a,&b),y=hb_atmosphere_ev_row(tables,ct,tint,&c,&d);
        status("ev_row_status",t,x,y);equal("ev_row_r",t,&a,&c,4);equal("ev_row_b",t,&b,&d,4);}
    for(unsigned t=0;t<1024;++t){unsigned variant=t%100;float ev=t%19==0?NAN:(float)(t%120)*0.25f-3,tint=(float)((int)(t%100)*91-4500)+0.25f;uint32_t ct=t%31==0?next():1500+(t%100)*100;
        gain_table(tables,variant,0);if(t%17==0)tables[0]=0;uint32_t a=123,b=456,c=a,d=b,x=gain(tables,ct,&a,&b,ev,tint),y=hb_atmosphere_gains(tables,ct,ev,tint,&c,&d);
        status("gain_status",t,x,y);equal("gain_r",t,&a,&c,4);equal("gain_b",t,&b,&d,4);
        gain_table(tables,variant,1);if(t%17==0)tables[2]=0;a=c=123;b=d=456;x=endvalue(tables,ct,&a,&b,ev,tint);y=hb_atmosphere_end_value(tables,ct,ev,tint,&c,&d);
        status("end_value_status",t,x,y);equal("end_value_r",t,&a,&c,4);equal("end_value_b",t,&b,&d,4);
        end_table(tables,variant);if(t%17==0)tables[0]=0;float end=t%23==0?NAN:(float)(t%120)*0.25f-3;a=c=123;b=d=456;
        x=endgain(tables,ct,&a,&b,end,ev,tint);y=hb_atmosphere_end_gains(tables,ct,end,ev,tint,&c,&d);
        status("end_gain_status",t,x,y);equal("end_gain_r",t,&a,&c,4);equal("end_gain_b",t,&b,&d,4);
    }
    for(unsigned t=0;t<1024;++t){memcpy(ctx,base,C);unsigned slot=t%4;confidence_row(tables,128,t%100);unsigned char*ev=tables+8,*ct=ev+8;
        ctx[0x3761c]=(unsigned char)(t%30);w32(ctx+0x841bc+slot*0x74,t%31==0?next():1500+(t%100)*100);wf(ctx+0x841c4+slot*0x74,t%29==0?NAN:(float)((int)(t%100)*91-4500)+0.25f);
        if(t%11==0)for(unsigned j=0;j<4;++j)w32(ct+12+12*j,(uint32_t)-100);
        uint32_t a=123,b=456,c=a,d=b,x=catdist(0,(int)slot,ct,&a,&b),y=hb_atmosphere_category_distance(ctx,slot,ct,&c,&d);
        status("category_distance_status",t,x,y);equal("category_distance_r",t,&a,&c,4);equal("category_distance_b",t,&b,&d,4);
        a=c=123;b=d=456;x=catct(0,(int)slot,ev,&a,&b);y=hb_atmosphere_category_ct(ctx,slot,ev,&c,&d);
        status("category_ct_status",t,x,y);equal("category_ct_r",t,&a,&c,4);equal("category_ct_b",t,&b,&d,4);
        a=c=123;b=d=456;x=catev(0,(int)slot,tables,&a,&b);y=hb_atmosphere_category_ev(ctx,slot,tables,&c,&d);
        status("category_ev_status",t,x,y);equal("category_ev_r",t,&a,&c,4);equal("category_ev_b",t,&b,&d,4);
    }
    for(unsigned t=0;t<512;++t){setup(ctx,cfg,base,original,t);memcpy(owned,ctx,C);uint32_t x=process(0),y=hb_atmosphere_process(owned,cfg,&model);++stage_calls;stage_successes+=x==0;if(x<256)++errors[x];
        status("atmosphere_status",t,x,y);equal("atmosphere_context",t,ctx,owned,C);
        if(!x)for(unsigned slot=0;slot<4;++slot){unsigned row=(t*3+slot*17)%81;changed_slots+=ctx[0x84164+slot*0x74]&&(u32(ctx+0x84168+slot*0x74)!=u32(ctx+0x348+16*row)||u32(ctx+0x84170+slot*0x74)!=u32(ctx+0x34c+16*row));}
        if(t==14||t==30){char name[96];snprintf(name,sizeof name,"atmosphere_%u_original.bin",t);dump(dir,name,ctx,C);snprintf(name,sizeof name,"atmosphere_%u_owned.bin",t);dump(dir,name,owned,C);}
    }
    for(unsigned t=0;t<64;++t){setup(ctx,cfg,base,original,t);memcpy(cfg,original,K);ctx[0x8424c]=0;memcpy(owned,ctx,C);uint32_t x=process(0),y=hb_atmosphere_process(owned,cfg,&model);++authentic_calls;
        status("authentic_atmosphere_status",t,x,y);equal("authentic_atmosphere_context",t,ctx,owned,C);}
    setup(ctx,cfg,base,original,14);memcpy(owned,ctx,C);
    for(unsigned t=0;t<12;++t){wf(ctx+0x37618,4.25f+t);wf(owned+0x37618,4.25f+t);uint32_t x=process(0),y=hb_atmosphere_process(owned,cfg,&model);++sequence_calls;
        status("stateful_atmosphere_status",t,x,y);equal("stateful_atmosphere_context",t,ctx,owned,C);}
    dump(dir,"stateful_atmosphere_original.bin",ctx,C);dump(dir,"stateful_atmosphere_owned.bin",owned,C);
    equal("original_config_unchanged",0,config,original,K);if(reawb)equal("passive_reawb_unchanged",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_atmosphere\",\"all_passed\":%s,\"checks\":%u,\"failures\":%u,\"signed_interp_calls\":4096,\"ev_row_calls\":2048,\"gain_calls\":1024,\"end_value_calls\":1024,\"end_gain_calls\":1024,\"category_helper_calls\":3072,"
           "\"stage_calls\":%u,\"stage_successes\":%u,\"authentic_config_calls\":%u,\"stateful_calls\":%u,\"nonidentity_slot_outputs\":%u,\"status_91\":%u,\"status_92\":%u,\"status_93\":%u,\"status_94\":%u,\"status_168\":%u,\"status_189\":%u,\"synthetic_fixtures\":true,\"full_awb_validated\":false}\n",
           failures?"false":"true",checks,failures,stage_calls,stage_successes,authentic_calls,sequence_calls,changed_slots,errors[91],errors[92],errors[93],errors[94],errors[168],errors[189]);
    return failures?1:0;
}
