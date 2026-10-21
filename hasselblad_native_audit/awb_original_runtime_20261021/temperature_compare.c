/* SPDX-License-Identifier: MIT
 * Original/owned comparisons; calibration and isotemperature table bytes are
 * private external inputs. Generated fixtures are not real camera frames. */
#include "hb_temperature.h"
#include "hb_scene_candidates.h"
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,xy_calls,row_calls,matrix_calls,mode_calls[5],errors[256];
static unsigned accumulation_calls,scene_calls,scene_ok,alias_calls;
static uint32_t rng=0x49133826;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;
        printf("{\"temperature_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}
}
static void matrices(unsigned char *first,unsigned n,unsigned variant){
    for(unsigned i=0;i<n;++i){unsigned char*p=first+40*i;w32(p,2000+2500*i);
        for(unsigned j=0;j<9;++j){float value=j%4==0?0.8f+(float)(i+variant)/16.0f:(float)((int)(i+j+variant)%7-3)/32.0f;
            if(variant==7)value=0;if(variant==8)value=j%4==0?-1.0f:0;wf(p+4+4*j,value);}}
}
static void make_config(unsigned char *cfg,unsigned t){
    cfg[0x1332bc]=(unsigned char)(1+t%4);matrices(cfg+0x1332c0,cfg[0x1332bc],t%9);
    cfg[0x133518]=(unsigned char)(t%4);
    for(unsigned j=0;j<3;++j){unsigned char*p=cfg+0x13351c+604*j;w16(p,(uint16_t)(j*12));p[2]=(unsigned char)(1+(j+t)%4);matrices(p+4,p[2],t%9);}
}
static void dump(const char *dir,const char *name,const void*p,size_t n){char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
int hb_run_temperature_tests(void*h,unsigned char*ctx,void*config,void*reawb,const char*dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    void(*xy_ref)(const float*,float*,float*)=(void*)(bias+0x4921c8);
    void(*row_ref)(const void*,void*,float)=(void*)(bias+0x4929c0);
    void(*matrix_ref)(int,void*,float)=(void*)(bias+0x491f60);
    uint32_t(*ae_ref)(int,void*,float,float)=(void*)(bias+0x491dc8);
    uint32_t(*temp_ref)(int,uint32_t,uint32_t,uint32_t,uint32_t,float*,float*)=sym(h,"scene_awb_color_temperature_compute");
    uint32_t(*scene_ref)(int)=sym(h,"scene_awb_scene_proc");
    uint32_t(*accum_ref)(int,int,int,const void*,const void*,uint32_t,int)=(void*)(bias+0x4a88a0);
    float table[31*4];memcpy(table,(void*)(bias+0x6ce418),sizeof table);hb_temperature_model model={table};
    dump(dir,"isotemperature_table.bin",table,sizeof table);
    unsigned char *base=malloc(C),*before=malloc(C),*cfg=malloc(K),*original=malloc(K),*rr=malloc(R);
    if(!base||!before||!cfg||!original||!rr)return 71;
    memcpy(base,ctx,C);memcpy(original,config,K);if(reawb)memcpy(rr,reawb,R);
    for(unsigned t=0;t<2048;++t){float xy[2]={(float)(next()%15001)/10000.0f-0.25f,(float)(next()%15001)/10000.0f-0.25f};
        if(t<1024){xy[0]=0.1f+(float)(t%32)/40.0f;xy[1]=0.1f+(float)(t/32)/40.0f;}
        float a[2]={123,456},b[2]={123,456};xy_ref(xy,a,a+1);uint32_t st=hb_temperature_xy(&model,xy,b,b+1);++xy_calls;
        equal("xy_values",t,a,b,8);uint32_t zero=0;equal("xy_status",t,&zero,&st,4);
    }
    unsigned char row[4+40*4];
    for(unsigned t=0;t<512;++t){memset(row,0,sizeof row);row[2]=(unsigned char)(1+t%4);matrices(row+4,row[2],t%9);
        float ct=t<256?(float)t*50.0f:(float)(next()%20000)+0.375f,a[9],b[9];memset(a,0xa5,sizeof a);memcpy(b,a,sizeof a);
        row_ref(row,a,ct);uint32_t st=hb_temperature_matrix_row(row,ct,b);++row_calls;equal("matrix_row",t,a,b,sizeof a);uint32_t zero=0;equal("matrix_row_status",t,&zero,&st,4);
    }
    for(unsigned t=0;t<512;++t){memcpy(ctx,base,C);memcpy(cfg,original,K);make_config(cfg,t);memcpy(ctx+0xb2028,&cfg,8);
        unsigned ae=t%2;if(ae&&!cfg[0x133518])cfg[0x133518]=1;
        float ct=(float)(next()%15000)+0.125f,ev=(float)(t%40)+0.25f,a[9]={0},b[9]={0};uint32_t x=0;
        if(ae)x=ae_ref(0,a,ev,ct);else matrix_ref(0,a,ct);
        uint32_t y=hb_temperature_matrix(cfg,(int)ae,ev,ct,b);++matrix_calls;
        equal("matrix_values",t,a,b,sizeof a);equal("matrix_status",t,&x,&y,4);
    }
    char tracepath[4096];if(snprintf(tracepath,sizeof tracepath,"%s/temperature_vectors.bin",dir)>=(int)sizeof tracepath)return 64;
    FILE*trace=fopen(tracepath,"wb");if(!trace)return 74;
    for(unsigned mode=0;mode<5;++mode){unsigned total=mode==0?128:mode<3?2048:16;
        for(unsigned t=0;t<total;++t){
            memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);
            if(t>=512)make_config(cfg,t);ctx[0x990dc]=(unsigned char)(t%3==0);wf(ctx+0x990d8,(float)(t%40)+0.5f);
            uint32_t r,g=4096,b;
            if(t<81){r=u32(ctx+0x348+16*t);b=u32(ctx+0x34c+16*t);}
            else{r=1+next()%24000;b=1+next()%24000;g=t%7==0?1+next()%20000:4096;}
            if(t%31==0)r=0;if(t%43==0)g=0;if(t%47==0)b=0;
            if(mode==2&&t>=768){r=u32(ctx+0x848)+1+t%4096;
                if(t%9==0)w32(ctx+0x838,u32(ctx+0x848)+1);
                if(t%11==0)w32(ctx+0x83c,u32(ctx+0x84c)-1);
                if(t%13==0)w32(ctx+0x828,2*u32(ctx+0x838)-u32(ctx+0x848));
                if(t%17==0)w32(ctx+0x838,u32(ctx+0x848));
            }
            memcpy(before,ctx,C);float a[2]={123,456},b0[2]={123,456};
            uint32_t x=temp_ref(0,mode,r,g,b,a,a+1),y=hb_temperature_compute(ctx,cfg,&model,mode,r,g,b,b0,b0+1);++mode_calls[mode];if(x<256)++errors[x];
            equal("mode_status",mode*10000+t,&x,&y,4);equal("mode_values",mode*10000+t,a,b0,8);equal("mode_context_unchanged",mode*10000+t,ctx,before,C);
            uint32_t input[6]={mode,t,r,g,b,x};if(fwrite(input,1,sizeof input,trace)!=sizeof input||fwrite(a,1,8,trace)!=8||fwrite(b0,1,8,trace)!=8)return 74;
        }
    }
    fclose(trace);
    for(unsigned t=0;t<32;++t){memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);float a=123,b=123;
        uint32_t r=u32(ctx+0x348+16*(t%81)),blue=u32(ctx+0x34c+16*(t%81)),mode=1+t%2;
        uint32_t x=temp_ref(0,mode,r,4096,blue,&a,&a),y=hb_temperature_compute(ctx,cfg,&model,mode,r,4096,blue,&b,&b);++alias_calls;
        equal("temperature_alias_status",t,&x,&y,4);equal("temperature_alias_value",t,&a,&b,4);
    }
    for(unsigned t=0;t<128;++t){
        memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);unsigned slot=t%4,scene=t%8,mode=1+t%2;
        w32(ctx+0x18,32);w32(ctx+0x1c,32);w32(ctx+0x28,1024);ctx[0x3761c]=(unsigned char)(4+t%16);
        ctx[0x990dc]=(unsigned char)(t%3==0);wf(ctx+0x990d8,(float)(t%40));
        if(t>=64)make_config(cfg,t);
        for(unsigned i=0;i<1024;++i){unsigned row=(t+i/128)%81;unsigned char*d=ctx+0xf450+40*i;
            w32(d,u32(ctx+0x348+16*row));w32(d+8,u32(ctx+0x34c+16*row));
            w16(ctx+0x3dace +slot*0x10188+scene*0x2020+2*i,(uint16_t)(t%13==0?0:1+next()%65535));}
        memcpy(before,ctx,C);const unsigned char*p=cfg+0x154c+slot*0xa278,*curve=cfg+0xa594+slot*0xa278;
        uint32_t x=accum_ref(0,(int)scene,(int)slot,p,curve,mode,0),y=hb_candidate_accumulate_with_model(before,cfg,p,curve,scene,slot,mode,0,&model);++accumulation_calls;
        equal("calibrated_accum_status",t,&x,&y,4);equal("calibrated_accum_context",t,ctx,before,C);
    }
    for(unsigned t=0;t<64;++t){
        memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);
        w32(ctx+0x18,32);w32(ctx+0x1c,32);w32(ctx+0x28,1024);ctx[0x3761c]=(unsigned char)(4+t%16);
        w16(ctx+0x3da50,(uint16_t)(t%3!=1));w16(ctx+0x3da52,(uint16_t)(t%3!=0));
        w32(cfg+0x1544,1+t%2);w32(cfg+0x1544+0xa278,1+(t/2)%2);
        for(unsigned i=0;i<1024;++i){unsigned row=(10+t+i/256)%81;unsigned char*d=ctx+0xf450+40*i;
            w32(d,u32(ctx+0x348+16*row));w32(d+8,u32(ctx+0x34c+16*row));w32(d+12,2000+100*row);w32(d+16,row);d[24]=1;wf(d+28,1);w32(d+36,2048);}
        memcpy(before,ctx,C);uint32_t x=scene_ref(0),y=hb_normal_scene_with_model(before,cfg,&model);++scene_calls;scene_ok+=x==0;
        equal("calibrated_scene_status",t,&x,&y,4);equal("calibrated_scene_context",t,ctx,before,C);
        if(t<4){char name[128];snprintf(name,sizeof name,"scene_%u_original.bin",t);dump(dir,name,ctx,C);snprintf(name,sizeof name,"scene_%u_owned.bin",t);dump(dir,name,before,C);}
    }
    equal("original_config_unchanged",0,config,original,K);if(reawb)equal("passive_reawb_unchanged",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_temperature\",\"all_passed\":%s,\"failures\":%u,\"checks\":%u,\"xy_calls\":%u,\"matrix_row_calls\":%u,\"matrix_calls\":%u,"
           "\"mode_calls\":[%u,%u,%u,%u,%u],\"status_91\":%u,\"status_92\":%u,\"status_93\":%u,\"status_94\":%u,"
           "\"alias_calls\":%u,\"accumulation_calls\":%u,\"scene_calls\":%u,\"scene_successes\":%u,\"synthetic_fixtures\":true,\"real_device_calibration_recovered\":false}\n",
           failures?"false":"true",failures,checks,xy_calls,row_calls,matrix_calls,mode_calls[0],mode_calls[1],mode_calls[2],mode_calls[3],mode_calls[4],errors[91],errors[92],errors[93],errors[94],alias_calls,accumulation_calls,scene_calls,scene_ok);
    return failures?1:0;
}
