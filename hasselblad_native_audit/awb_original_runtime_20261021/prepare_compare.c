/* SPDX-License-Identifier: MIT
 * Same-process original/owned preparation comparisons. Sensor records and
 * calibration curves below are explicit synthetic fixtures, not camera data.
 */
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum { C=920560,E=0x1ce90,P=0x20200,M=0x100,K=1502800,R=1000 };
static uint32_t seed=0x4e2c2026;
static uint32_t rnd(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
static uint32_t r32(const void *p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void *p,uint32_t v){memcpy(p,&v,4);}
static void w16(void *p,uint16_t v){memcpy(p,&v,2);}
static void wf(void *p,float v){memcpy(p,&v,4);}
static void *sym(void *h,const char *s){void *p=dlsym(h,s);if(!p)_exit(3);return p;}
static unsigned checks,failures,calls[6],frame_calls,blocks,zero_ratios,clipped_ratios;
static void equal(const char *stage,unsigned test,const void *a,const void *b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=12){const unsigned char *x=a,*y=b;size_t k=0;while(k<n&&x[k]==y[k])++k;
        printf("{\"mismatch_stage\":\"%s\",\"case\":%u,\"first_offset\":%zu,\"original_byte\":%u,\"owned_byte\":%u}\n",stage,test,k,x[k],y[k]);}
}
static void status(const char *stage,unsigned test,uint32_t a,uint32_t b){equal(stage,test,&a,&b,4);}
static void dump(const char *dir,const char *name,const void *p,size_t n){
    char path[4096];if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE *f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
int hb_run_prepare_tests(void *h,unsigned char *ctx,unsigned char *e2,void *config,void *reawb,const char *dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t (*set)(int,void*)=sym(h,"awb_e2_main_set_stat");
    uint32_t (*parse)(int,void*,void*)=sym(h,"awb_e2_main_get_stat_parse");
    uint32_t (*import)(int,void*,void*)=sym(h,"scene_awb_set_stat");
    uint32_t (*gain)(int)=sym(h,"scene_awb_stat_update_calib_gain");
    uint32_t (*calib)(int)=(uint32_t(*)(int))(bias+0x4ad3a0);
    void (*awbinfo)(int)=(void(*)(int))(bias+0x4ad298);
    void (*aeinfo)(int)=(void(*)(int))(bias+0x4ad4c0);
    unsigned char *base=malloc(C),*owned=malloc(C),*oe=malloc(E),*ebase=malloc(E),*conf=malloc(K),*rr=malloc(R);
    unsigned char *po_store=malloc(P+128),*pp_store=malloc(P+128),*mo_store=malloc(M+128),*mp_store=malloc(M+128);
    unsigned char *raw=malloc(0x4118),*rawcopy=malloc(0x4118);
    if(!base||!owned||!oe||!ebase||!conf||!rr||!po_store||!pp_store||!mo_store||!mp_store||!raw||!rawcopy)return 71;
    unsigned char *po=po_store+64,*pp=pp_store+64,*mo=mo_store+64,*mp=mp_store+64;
    memcpy(base,ctx,C);memcpy(ebase,e2,E);memcpy(conf,config,K);if(reawb)memcpy(rr,reawb,R);
    const uint16_t edge[]={0,1,2,3,15,16,63,64,255,256,1023,1024,4095,4096,32767,65534,65535};
    for(unsigned t=0;t<64;++t){
        memcpy(ctx,base,C);memcpy(e2,ebase,E);memset(raw,0,0x4118);
        w32(raw,r32(e2+0x4120));w32(raw+4,0x4118);w32(raw+8,t+1);w32(raw+12,r32(e2+0x412c));
        w32(raw+0x4110,rnd());w32(raw+0x4114,rnd());
        for(unsigned i=0;i<1024;++i){unsigned char *s=raw+16+16*i;
            for(unsigned j=0;j<4;++j)w16(s+2*j,t<8?edge[(i*(j+1)+t+j)%17]:(uint16_t)rnd());
            s[8]=(unsigned char)(i%5==0?0:i%5==1?9:i%5==2?10:i%5==3?255:rnd());
        }
        memcpy(rawcopy,raw,0x4118);status("native_e2_set",t,set(0,raw),0);
        memcpy(owned,ctx,C);memcpy(oe,e2,E);
        memset(po_store,0xa5,P+128);memset(pp_store,0xa5,P+128);
        memset(mo_store,0x5a,M+128);memset(mp_store,0x5a,M+128);
        uint32_t a=parse(0,po,mo),b=hb_e2_main_parse(owned,oe,pp,mp);++calls[0];++frame_calls;
        status("e2_parse_status",t,a,b);equal("e2_parse_context",t,ctx,owned,C);equal("e2_parse_e2",t,e2,oe,E);
        equal("e2_parse_output_and_guards",t,po_store,pp_store,P+128);equal("e2_parse_meta_and_guards",t,mo_store,mp_store,M+128);
        equal("native_input_immutable",t,raw,rawcopy,0x4118);
        for(unsigned i=0;i<1024;++i){++blocks;zero_ratios+=r32(po+16+32*i)==0;clipped_ratios+=r32(po+16+32*i)==65535;}
        /* No secondary regions in this native main-only fixture. */
        po[0x20010]=0;memcpy(owned,ctx,C);
        a=import(0,po,mo);b=hb_import_stats(owned,po,mo);++calls[1];
        status("import_status",t,a,b);equal("import_context",t,ctx,owned,C);
        memcpy(owned,ctx,C);awbinfo(0);hb_stat_awb_info(owned);++calls[2];equal("awb_info_context",t,ctx,owned,C);
        ctx[0x19c]=(unsigned char)(t%2);ctx[0x1a0]=2;
        w32(ctx+0x1a4,2000);w32(ctx+0x1a8,3072);w32(ctx+0x1ac,6144);
        w32(ctx+0x1b0,8000);w32(ctx+0x1b4,6144);w32(ctx+0x1b8,3072);w32(ctx+0x1bc,t*200);
        memcpy(owned,ctx,C);a=calib(0);b=hb_stat_calib_proc(owned);++calls[4];
        status("calib_status",t,a,b);equal("calib_context",t,ctx,owned,C);
        wf(ctx+0x990d4,(float)t-20.5f);w32(ctx+0x990d8,rnd());ctx[0x990dc]=(unsigned char)rnd();w32(ctx+0x990e0,rnd());
        w32(ctx+0x990e4,t%17);wf(ctx+0x990e8,t%4?1234.5f:0.0f);
        for(unsigned j=0;j<16;++j)wf(ctx+0x990ec+4*j,(float)(rnd()%2000));
        memcpy(owned,ctx,C);aeinfo(0);hb_stat_ae_info(owned,config);++calls[5];equal("ae_info_context",t,ctx,owned,C);
        if(t==63){dump(dir,"native_e2_fixture.bin",raw,0x4118);dump(dir,"parsed_e2_fixture.bin",po,P);dump(dir,"prepared_context.bin",ctx,C);}
    }
    /* Direct calibration interpolation boundaries and wraparound products. */
    for(unsigned t=0;t<1024;++t){
        memcpy(ctx,base,C);ctx[0x1a0]=(unsigned char)(t%3);w32(ctx+0x1a4,1000+(t%9)*1000);w32(ctx+0x1b0,t%5?9000:2000);
        w32(ctx+0x1a8,t<32?edge[t%17]:rnd());w32(ctx+0x1ac,rnd());w32(ctx+0x1b4,rnd());w32(ctx+0x1b8,rnd());
        w32(ctx+0x1bc,t<128?t*100:rnd());
        memcpy(owned,ctx,C);uint32_t a=gain(0),b=hb_update_calib_gain(owned);++calls[3];
        status("gain_status",t,a,b);equal("gain_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<128;++t){
        memcpy(ctx,base,C);ctx[0x19c]=(unsigned char)(t%3);ctx[0x1a0]=(unsigned char)(t%3);
        w32(ctx+0x1a4,2000);w32(ctx+0x1b0,8000);w32(ctx+0x1bc,t*97);
        w32(ctx+0x1a8,rnd());w32(ctx+0x1ac,rnd());w32(ctx+0x1b4,rnd());w32(ctx+0x1b8,rnd());
        w32(ctx+0x28,t%9==0?4096:t%129);w32(ctx+0x2c,t%9);
        for(unsigned i=0;i<4096*40;++i)ctx[0xf450+i]=(unsigned char)rnd();
        for(unsigned i=0;i<8*40+8;++i)ctx[0x37450+i]=(unsigned char)rnd();
        memcpy(owned,ctx,C);uint32_t a=calib(0),b=hb_stat_calib_proc(owned);++calls[4];
        status("calib_edge_status",t,a,b);equal("calib_edge_context",t,ctx,owned,C);
    }
    equal("config_immutable",0,config,conf,K);if(reawb)equal("passive_reawb_immutable",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_preparation\",\"all_passed\":%s,\"failures\":%u,\"checks\":%u,"
           "\"native_frames\":%u,\"native_blocks\":%u,\"zero_red_ratios\":%u,\"clipped_red_ratios\":%u,"
           "\"parse_calls\":%u,\"import_calls\":%u,\"awb_info_calls\":%u,\"calibration_gain_calls\":%u,"
           "\"block_calibration_calls\":%u,\"ae_info_calls\":%u,\"passive_reawb_compared\":%s,"
           "\"synthetic_sensor_inputs\":true,\"camera_calibration_recovered\":false}\n",
           failures?"false":"true",failures,checks,frame_calls,blocks,zero_ratios,clipped_ratios,
           calls[0],calls[1],calls[2],calls[3],calls[4],calls[5],reawb?"true":"false");
    return failures?1:0;
}
