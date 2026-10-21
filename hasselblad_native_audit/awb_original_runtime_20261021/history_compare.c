/* SPDX-License-Identifier: MIT
 * Differential history/geometry tests; generated inputs are synthetic. */
#include "hb_history.h"
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,errors[256],history_calls,history_successes,authentic_calls,dense_calls,sequence_calls,extended_calls,nonidentity_outputs;
static uint32_t rng=0x48202621;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=24){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;
        printf("{\"history_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}
}
static void status(const char*s,unsigned t,uint32_t a,uint32_t b){equal(s,t,&a,&b,4);}
static void dump(const char*dir,const char*name,const void*p,size_t n){char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
static void zone(unsigned char*z,int32_t center,unsigned v){
    memset(z,0,52);w32(z,(uint32_t)(center-1000));w32(z+4,(uint32_t)(center+1000));
    w32(z+8,(uint32_t)(center-2000));w32(z+12,(uint32_t)(center+2000));
    for(unsigned i=0;i<4;++i){w32(z+16+8*i,(uint32_t)(int32_t)((int)(v%5)-2)*2048);w32(z+20+8*i,(uint32_t)(center+(i%2?1500:-1500)));}
    z[48]=(unsigned char)(1+v%255);
}
static void broad_zone(unsigned char*z){zone(z,0,2);w32(z,(uint32_t)-100000);w32(z+4,100000);w32(z+8,(uint32_t)-100000);w32(z+12,100000);
    for(unsigned i=0;i<4;++i)w32(z+20+8*i,(uint32_t)(i%2?100000:-100000));z[48]=1;}
static void table(unsigned char*p,unsigned variant){memset(p,0,100);p[0]=3;
    for(unsigned j=0;j<3;++j){w32(p+4+12*j,(uint32_t)(int32_t)((int)j-1)*1000);w32(p+8+12*j,4500+variant*137+j*51);w32(p+12+12*j,2700+variant*73+j*39);}}
static void history_entry(unsigned char*e,unsigned variant){memset(e,0,0xd78);e[0]=(unsigned char)(variant%7);w32(e+4,128);e[12]=1;
    for(unsigned sub=0;sub<2;++sub){unsigned char*p=e+16+0x6b4*sub;p[0]=3;p[1]=0;p[2]=10;p[3]=21;
        for(unsigned j=0;j<3;++j)w16(p+10+2*j,256);p[26]=2;w16(p+28,0);w16(p+30,20);w16(p+44,256);w16(p+46,256);
        uint32_t ct[4]={2000,4000,6000,10000};for(unsigned j=0;j<4;++j)w32(p+60+4*j,ct[j]);
        p[76]=1;broad_zone(p+80);p[288]=1;broad_zone(p+292);w32(p+500,0);w32(p+904,128);w32(p+908,192);w32(p+1312,256);
        for(unsigned k=0;k<3;++k)for(unsigned j=0;j<4;++j)table(p+(unsigned[]){504,912,1316}[k]+100*j,variant+sub+k+j);
    }
}
static void setup(unsigned char*ctx,unsigned char*cfg,const unsigned char*base,const unsigned char*original,unsigned t,int synthetic){
    memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);
    unsigned count=t%19==0?0:t>=240?4096:128;w32(ctx+0x28,count);ctx[0x3761c]=(unsigned char)(t%23);ctx[0x990dc]=(unsigned char)(t%3==0);
    cfg[0x138748]=(unsigned char)(t%2);w16(ctx+0x3c230,(uint16_t)(t%3?256:0));
    for(unsigned j=0;j<7;++j)w16(ctx+0x3da42+2*j,(uint16_t)(t%3?256:0));
    for(unsigned j=0;j<count;++j){unsigned row=(t+j)%81;unsigned char*d=ctx+0xf450+40*j;
        w32(d,u32(ctx+0x348+16*row));w32(d+8,u32(ctx+0x34c+16*row));w32(d+12,2000+100*row);w32(d+20,j%3);ctx[0x3be2c+j]=(unsigned char)(j%7);}
    for(unsigned slot=0;slot<4;++slot){size_t o=slot*0x10188;unsigned row=(t+slot*17)%81;ctx[0x4dbcc+o]=(unsigned char)(t%31==0?2:1);
        w32(ctx+0x4dc24+o,2000+row*100);w32(ctx+0x4dbd0+o,u32(ctx+0x348+16*row));w32(ctx+0x4dbd8+o,u32(ctx+0x34c+16*row));
        w32(ctx+0x4dbdc+o,u32(ctx+0x348+16*((row+5)%81)));w32(ctx+0x4dbe4+o,u32(ctx+0x34c+16*((row+5)%81)));
        ctx[0x4dc3c+o]=(unsigned char)(slot+3);w32(ctx+0x4dc40+o,17+slot);
        if(synthetic){cfg[0xa1f44+slot*0x6bc4]=(unsigned char)(t%29==0?0:1);history_entry(cfg+0xa1f48+slot*0x6bc4,t+slot);}
    }
    w32(ctx+0xb0c84,8000);w32(ctx+0xb0c8c,8000);w32(ctx+0xb0c4c,8000);w32(ctx+0xb0c54,8000);
    if(synthetic){
        /* Exercise early rejection, nearest-zone fallback, and ordered errors. */
        if(t%11==1)cfg[0xa1f48]=7;
        if(t%11==2)for(unsigned k=0;k<3;++k)for(unsigned j=0;j<4;++j)cfg[0xa1f58+(unsigned[]){504,912,1316}[k]+100*j]=0;
        if(t%11==3)for(unsigned k=0;k<3;++k)for(unsigned j=0;j<4;++j){unsigned char*p=cfg+0xa1f58+(unsigned[]){504,912,1316}[k]+100*j;p[0]=2;w32(p+4,(uint32_t)-2000000000);w32(p+16,2000000000);}
        if(t%11==4){w32(ctx+0xb0c84,200000);w32(ctx+0xb0c8c,200000);w32(ctx+0xb0c4c,100050);w32(ctx+0xb0c54,0);}
        if(t%11==5)w32(ctx+0xb0c84,200000);
        if(t%11==6)for(unsigned s=0;s<4;++s)cfg[0xa1f58+s*0x6bc4+76]=0;
        if(t%11==7){ctx[0x3761c]=255;cfg[0xa1f59]=128;}
    }
}
int hb_run_history_tests(void*h,unsigned char*ctx,void*config,void*reawb,const char*dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t(*distance)(int,uint32_t,uint32_t,uint32_t,int32_t*)=sym(h,"scene_awb_get_color_temperature_dis");
    uint32_t(*contains)(const void*,uint32_t,uint32_t)=(void*)(bias+0x4b37f8);
    uint32_t(*edge)(const void*,uint32_t,uint32_t,int32_t*)=(void*)(bias+0x4b35c8);
    uint32_t(*zone_distance)(const void*,uint32_t,uint32_t,int32_t*)=sym(h,"scene_awb_zone_get_zone_dis");
    uint32_t(*zone_count)(int,uint32_t,uint32_t,uint32_t,const void*,uint32_t*,uint32_t*)=sym(h,"scene_awb_zone_get_hist_zone_num");
    uint32_t(*history)(int)=sym(h,"scene_awb_hist_proc");
    unsigned char*base=malloc(C),*owned=malloc(C),*cfg=malloc(K),*original=malloc(K),*rr=malloc(R);
    if(!base||!owned||!cfg||!original||!rr)return 71;memcpy(base,ctx,C);memcpy(original,config,K);if(reawb)memcpy(rr,reawb,R);
    for(unsigned t=0;t<4096;++t){uint32_t ct=t<256?t*50:next(),r=next(),b=next();int32_t a=123,v=hb_temperature_distance(ctx,ct,r,b);
        uint32_t st=distance(0,ct,r,b,&a);status("temperature_distance_status",t,st,0);equal("temperature_distance",t,&a,&v,4);}
    unsigned char zones[52*8];
    for(unsigned t=0;t<4096;++t){zone(zones,4000,t);uint32_t r=t<2048?2500+t*2:next(),b=t<2048?1000+(t*73)%6000:next();
        const unsigned char*z=t%127?zones:NULL;status("zone_contains",t,contains(z,r,b),hb_zone_contains(z,r,b));
        int32_t a=123,v=456;uint32_t x=edge(z,r,b,&a),y=hb_zone_edge(z,r,b,&v);status("zone_edge_status",t,x,y);equal("zone_edge_value",t,&a,&v,4);
        if(z){x=zone_distance(z,r,b,&a);v=hb_zone_distance(z,r,b);status("zone_distance_status",t,x,0);equal("zone_distance_value",t,&a,&v,4);}
    }
    for(unsigned t=0;t<192;++t){setup(ctx,cfg,base,original,t,1);unsigned n=t%9;
        for(unsigned j=0;j<8;++j)zone(zones+52*j,6000+(int)j*1000,t+j);
        if(t%3==0)broad_zone(zones);uint32_t a=123,b=456,c=a,d=b;
        uint32_t x=zone_count(0,t%7,t%2,n,zones,&a,&b),y=hb_history_zone_count(ctx,cfg,t%7,t%2,n,zones,&c,&d);
        status("zone_count_status",t,x,y);equal("zone_count",t,&a,&c,4);equal("zone_weighted_count",t,&b,&d,4);
    }
    for(unsigned t=0;t<256;++t){setup(ctx,cfg,base,original,t,1);memcpy(owned,ctx,C);
        uint32_t x=history(0),y=hb_history_process(owned,cfg);++history_calls;history_successes+=!x;dense_calls+=t>=240;if(x<256)++errors[x];
        status("history_status",t,x,y);equal("history_context",t,ctx,owned,C);
        if(t==8||t==9||t==10){char name[96];snprintf(name,sizeof name,"history_%u_original.bin",t);dump(dir,name,ctx,C);snprintf(name,sizeof name,"history_%u_owned.bin",t);dump(dir,name,owned,C);}
    }
    for(unsigned t=0;t<256;++t){setup(ctx,cfg,base,original,8,1);
        unsigned count=t%17==0?0:t%19==0?4096:128;w32(ctx+0x28,count);ctx[0x3761c]=(unsigned char)(t%22);
        float ev=(float)(t%100)*0.25f-1.0f,end=(float)(t%96)*0.25f-2.0f;
        if(t==254)ev=NAN;if(t==255)end=NAN;wf(ctx+0x37618,ev);wf(ctx+0x990d8,end);
        ctx[0x990dc]=(unsigned char)(t%4);cfg[0x138748]=(unsigned char)(t%2);w16(ctx+0x3c230,(uint16_t)(t*251));
        for(unsigned cat=0;cat<7;++cat)w16(ctx+0x3da42+2*cat,(uint16_t)(t*239+cat*17));
        for(unsigned i=0;i<count;++i){unsigned char*d=ctx+0xf450+40*i;w32(d,8000);w32(d+8,8000);w32(d+12,4500);w32(d+20,i%3);ctx[0x3be2c+i]=(unsigned char)(i%7);}
        for(unsigned slot=0;slot<4;++slot){size_t o=slot*0x10188;unsigned n=1+t%4;cfg[0xa1f44+slot*0x6bc4]=(unsigned char)n;
            unsigned row=(t*3+slot*17)%81;w32(ctx+0x4dc24+o,2000+row*100);
            w32(ctx+0x4dbd0+o,u32(ctx+0x348+16*row)+(t%7)*100);w32(ctx+0x4dbd8+o,u32(ctx+0x34c+16*row));
            for(unsigned j=0;j<n;++j){unsigned char*e=cfg+0xa1f48+slot*0x6bc4+j*0xd78;history_entry(e,t+j*7);e[12]=(unsigned char)(j%3);w32(e+4,(t%5)*100);
                for(unsigned sub=0;sub<2;++sub){unsigned char*q=e+16+sub*0x6b4;
                    if(t%11==0)q[0]=1;q[1]=2;q[2]=10;q[3]=18;
                    for(unsigned k=0;k<3;++k)w16(q+10+2*k,(uint16_t)(t%13==0?65535:64+(t+k*13)%400));
                    q[26]=(unsigned char)(t%3);w16(q+28,3);w16(q+30,16);w16(q+44,(uint16_t)(t%7==0?0:127));w16(q+46,511);
                    uint32_t axis[4]={3000,4500,6500,9000};for(unsigned k=0;k<4;++k)w32(q+60+4*k,axis[k]);
                    if(t%7==0)q[76]=0;
                    q[288]=(unsigned char)(t%3);if(q[288]==2)broad_zone(q+292+52);q[292+48]=(unsigned char)(t%4);
                    if(q[288]==2)q[292+52+48]=(unsigned char)(t%5);
                    for(unsigned k=0;k<3;++k)for(unsigned l=0;l<4;++l){unsigned char*curve=q+(unsigned[]){504,912,1316}[k]+100*l;
                        if(t%23==0)curve[0]=1;
                        if(t%29==0){w32(curve+8,UINT32_MAX);w32(curve+12,0);}
                    }
                }
            }
        }
        memcpy(owned,ctx,C);uint32_t x=history(0),y=hb_history_process(owned,cfg);++extended_calls;
        status("extended_history_status",t,x,y);equal("extended_history_context",t,ctx,owned,C);
        if(!x)for(unsigned slot=0;slot<4;++slot)nonidentity_outputs+=u32(ctx+0x84168+slot*0x74)!=u32(ctx+0x4dbd0+slot*0x10188)||u32(ctx+0x84170+slot*0x74)!=u32(ctx+0x4dbd8+slot*0x10188);
        if(t==24){dump(dir,"nonidentity_history_config.bin",cfg,K);dump(dir,"nonidentity_history_original.bin",ctx,C);dump(dir,"nonidentity_history_owned.bin",owned,C);}
    }
    for(unsigned t=0;t<64;++t){setup(ctx,cfg,base,original,t,0);memcpy(cfg,original,K);wf(ctx+0x37618,(float)(t%22)+0.25f);memcpy(owned,ctx,C);uint32_t x=history(0),y=hb_history_process(owned,cfg);++authentic_calls;
        status("authentic_history_status",t,x,y);equal("authentic_history_context",t,ctx,owned,C);}
    setup(ctx,cfg,base,original,8,1);memcpy(owned,ctx,C);
    for(unsigned t=0;t<12;++t){ctx[0x3761c]=owned[0x3761c]=(unsigned char)(t+4);uint32_t x=history(0),y=hb_history_process(owned,cfg);++sequence_calls;
        status("stateful_history_status",t,x,y);equal("stateful_history_context",t,ctx,owned,C);}
    dump(dir,"stateful_history_original.bin",ctx,C);dump(dir,"stateful_history_owned.bin",owned,C);
    equal("original_config_unchanged",0,config,original,K);if(reawb)equal("passive_reawb_unchanged",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_history\",\"all_passed\":%s,\"checks\":%u,\"failures\":%u,\"temperature_distance_calls\":4096,\"zone_contains_calls\":4096,\"zone_edge_calls\":4096,\"zone_distance_calls\":4063,\"zone_count_calls\":192,"
           "\"history_calls\":%u,\"history_successes\":%u,\"authentic_config_calls\":%u,\"dense_calls\":%u,\"stateful_calls\":%u,\"extended_calls\":%u,\"nonidentity_slot_outputs\":%u,\"status_74\":%u,\"status_79\":%u,\"status_80\":%u,\"synthetic_fixtures\":true,\"full_awb_validated\":false}\n",
           failures?"false":"true",checks,failures,history_calls,history_successes,authentic_calls,dense_calls,sequence_calls,extended_calls,nonidentity_outputs,errors[74],errors[79],errors[80]);
    return failures?1:0;
}
