/* SPDX-License-Identifier: MIT
 * Differential post-result helpers and the complete mode-2 branch.
 * All records are synthetic. Original initialization and calibration are private. */
#include "hb_post_results.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,nonidentity,ct_errors[256],chain_errors[256],mode2_errors[256];
static uint32_t rng=0x10212026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){
    ++checks;if(!memcmp(a,b,n))return;++failures;
    if(failures<=24){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;
        printf("{\"post_result_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}
}
static void status(const char*s,unsigned t,uint32_t a,uint32_t b){equal(s,t,&a,&b,4);}
static void dump(const char*dir,const char*name,const void*p,size_t n){char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
static const size_t groups[]={0xb0c58,0xb0c4c,0xb0cf4,0xb0ce8,0xb0cc8,0xb0cbc,0xb0d64,0xb0d58};
static void gains(unsigned char*ctx,unsigned t,int extreme){
    for(unsigned i=0;i<8;++i)for(unsigned j=0;j<3;++j)w32(ctx+groups[i]+4*j,extreme?next():1200+next()%12000);
    if(t%4==0)w32(ctx+groups[(t/4)%8]+4*((t/32)%3),0);
}
static void colors(unsigned char*ctx,unsigned char*cfg,unsigned t){
    cfg[0x153c0c]=(unsigned char)(t%13==0?0:1+t%3);cfg[0x153c10]=(unsigned char)(t%7==0?255:t%23);
    for(unsigned i=0;i<22;++i){w32(cfg+0x153c14+8*i,i);w32(cfg+0x153c18+8*i,i%2+256*(t%3));}
    w32(ctx+0xd478,t%26);w32(ctx+0x194,t%11);
    for(unsigned i=0;i<4;++i){unsigned char*p=cfg+0x153cc4+124*i;p[0]=(unsigned char)(t%17==0?11:1+t%10);
        for(unsigned j=0;j<10;++j){w32(p+4+12*j,2000+j*2000);w32(p+8+12*j,3000+j*133+i*71+(t%5==0?0x10000:0));w32(p+12+12*j,6000-j*97-i*31+(t%5==0?0x20000:0));}}
    w32(ctx+0xb0ca0,t<400?1500+(t*97)%25000:next());
}
static void setup(unsigned char*ctx,unsigned char*cfg,const unsigned char*base,const unsigned char*original,unsigned t){
    memcpy(ctx,base,C);memcpy(cfg,original,K);memcpy(ctx+0xb2028,&cfg,8);gains(ctx,t,0);colors(ctx,cfg,t);
    ctx[0x2f4]=(unsigned char)(t%3);ctx[0x278]=(unsigned char)(t%4);ctx[0x990dc]=(unsigned char)(t%3);
    for(unsigned i=0;i<3;++i){size_t off=i==0?0x1c0:i==1?0x2ec:0x300;w32(ctx+off,3000+t*3+i*100);w32(ctx+off+4,5000-t*2+i*50);}
    if(t%19==0)w32(ctx+(t%3==0?0x1c0:t%3==1?0x2ec:0x300)+4*(t%2),0);
}
int hb_run_post_results_tests(void*h,unsigned char*ctx,void*config,void*reawb,const char*dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    uint32_t(*blend)(int,uint32_t,uint32_t,const void*,const void*)=(void*)(bias+0x4a2360);
    uint32_t(*conversion)(uint32_t,uint32_t,uint32_t,uint32_t*,uint32_t*,uint32_t*,uint32_t,uint32_t)=sym(h,"scene_awb_golden_gain_conversion");
    const char*names[]={"scene_awb_compute_result_ct","scene_awb_result_update_golden_gain_auto","scene_awb_result_e_nd_temp_recalib","scene_awb_result_e_nd_unit_recalib","scene_awb_result_recalib","scene_awb_result_normalise_all","scene_awb_color_mode_proc"};
    uint32_t(*original_fn[7])(int);for(unsigned i=0;i<7;++i)original_fn[i]=sym(h,names[i]);
    uint32_t(*post)(int)=sym(h,"scene_awb_post_proc");
    float table[124];memcpy(table,(void*)(bias+0x6ce418),sizeof table);hb_temperature_model model={table};dump(dir,"isotemperature_table.bin",table,sizeof table);
    unsigned char *base=malloc(C),*owned=malloc(C),*reference=malloc(C),*cfg=malloc(K),*cfgbefore=malloc(K),*cfgafter=malloc(K),*original=malloc(K),*rr=malloc(R);
    if(!base||!owned||!reference||!cfg||!cfgbefore||!cfgafter||!original||!rr)return 71;
    memcpy(base,ctx,C);memcpy(original,config,K);if(reawb)memcpy(rr,reawb,R);
    for(unsigned t=0;t<4096;++t){uint32_t r=next(),g=next(),b=next(),scale=next(),div=t%17==0?0:next(),a[3]={11,22,33},o[3]={11,22,33};
        unsigned ir=t%3,ig=t%7==0?ir:(ir+1)%3,ib=t%11==0?ig:(ir+2)%3;
        uint32_t x=conversion(r,g,b,t%31==0?NULL:a+ir,t%37==0?NULL:a+ig,t%41==0?NULL:a+ib,scale,div);
        uint32_t y=hb_post_golden_conversion(r,g,b,t%31==0?NULL:o+ir,t%37==0?NULL:o+ig,t%41==0?NULL:o+ib,scale,div);
        status("golden_conversion_status",t,x,y);equal("golden_conversion_outputs",t,a,o,sizeof a);
    }
    for(unsigned t=0;t<512;++t){memcpy(ctx,base,C);unsigned char a[0x74],b[0x74];for(unsigned i=0;i<sizeof a;++i){a[i]=(unsigned char)next();b[i]=(unsigned char)next();}
        uint32_t wa=next(),wb=t%7==0?0-wa:next();memcpy(owned,ctx,C);uint32_t x=blend(0,wa,wb,a,b),y=hb_post_blend_normal(owned,wa,wb,a,b);
        status("normal_blend_status",t,x,y);equal("normal_blend_context",t,ctx,owned,C);
    }
    for(unsigned fn=1;fn<=5;++fn)for(unsigned t=0;t<256;++t){setup(ctx,cfg,base,original,t);gains(ctx,t,t%3==0);w32(cfg+0x80,t%7==0?next():1024+t*17);
        memcpy(owned,ctx,C);uint32_t x=original_fn[fn](0),y=fn==1?hb_post_golden_snapshot(owned):fn==2?hb_post_end_temperature(owned):fn==3?hb_post_end_unit(owned):fn==4?hb_post_recalibrate(owned):hb_post_normalize(owned,cfg);
        status(names[fn],t,x,y);equal("gain_helper_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<512;++t){setup(ctx,cfg,base,original,t);memcpy(owned,ctx,C);memcpy(cfgbefore,cfg,K);
        uint32_t before_r=u32(ctx+0xb0c4c),before_b=u32(ctx+0xb0c54);uint32_t x=original_fn[6](0);memcpy(cfgafter,cfg,K);memcpy(cfg,cfgbefore,K);uint32_t y=hb_post_color_mode(owned,cfg);
        status("color_mode_status",t,x,y);equal("color_mode_context",t,ctx,owned,C);equal("color_mode_config",t,cfgafter,cfg,K);
        nonidentity+=!x&&(u32(ctx+0xb0c4c)!=before_r||u32(ctx+0xb0c54)!=before_b);
    }
    for(unsigned t=0;t<192;++t){setup(ctx,cfg,base,original,t);if(t%17==0){cfg[0x1332bc]=1;memset(cfg+0x1332c0+4,0,36);ctx[0x990dc]=0;}
        memcpy(owned,ctx,C);uint32_t x=original_fn[0](0),y=hb_post_result_ct(owned,cfg,&model);if(x<256)++ct_errors[x];
        status("result_ct_status",t,x,y);equal("result_ct_context",t,ctx,owned,C);
    }
    for(unsigned t=0;t<256;++t){setup(ctx,cfg,base,original,t);memcpy(owned,ctx,C);memcpy(cfgbefore,cfg,K);uint32_t x=0;
        for(unsigned i=0;i<7&&!x;++i)x=original_fn[i](0);
        memcpy(cfgafter,cfg,K);memcpy(cfg,cfgbefore,K);uint32_t y=hb_post_finalize(owned,cfg,&model);if(x<256)++chain_errors[x];
        status("finalize_sequence_status",t,x,y);equal("finalize_sequence_context",t,ctx,owned,C);equal("finalize_sequence_config",t,cfgafter,cfg,K);
        if(t==1||t==7){char name[96];snprintf(name,sizeof name,"post_finalize_%u_original.bin",t);dump(dir,name,ctx,C);snprintf(name,sizeof name,"post_finalize_%u_owned.bin",t);dump(dir,name,owned,C);}
    }
    for(unsigned t=0;t<256;++t){setup(ctx,cfg,base,original,t);w32(ctx+0x194,2);w32(ctx+0xb0ca4,t*100);w32(ctx+0xb0d3c,t*150);w32(ctx+0xb0d40,t*75);
        memcpy(owned,ctx,C);memcpy(cfgbefore,cfg,K);uint32_t x=post(0);memcpy(cfgafter,cfg,K);memcpy(cfg,cfgbefore,K);uint32_t y=hb_post_mode2(owned,cfg);if(x<256)++mode2_errors[x];
        status("complete_mode2_status",t,x,y);equal("complete_mode2_context",t,ctx,owned,C);equal("complete_mode2_config",t,cfgafter,cfg,K);
        if(t==1||t==4){char name[96];snprintf(name,sizeof name,"post_mode2_%u_original.bin",t);dump(dir,name,ctx,C);snprintf(name,sizeof name,"post_mode2_%u_owned.bin",t);dump(dir,name,owned,C);}
    }
    setup(ctx,cfg,base,original,1);cfg[0x153c0c]=0;memcpy(owned,ctx,C);
    for(unsigned t=0;t<16;++t){uint32_t x=0;for(unsigned i=0;i<7&&!x;++i)x=original_fn[i](0);uint32_t y=hb_post_finalize(owned,cfg,&model);
        status("stateful_finalize_status",t,x,y);equal("stateful_finalize_context",t,ctx,owned,C);}
    dump(dir,"post_stateful_original.bin",ctx,C);dump(dir,"post_stateful_owned.bin",owned,C);
    /* Unsupported boundaries are checked without invoking undefined original tables. */
    setup(ctx,cfg,base,original,1);w32(ctx+0x194,0);memcpy(reference,ctx,C);status("unsupported_mode",0,hb_post_mode2(ctx,cfg),HB_PREP_UNSUPPORTED);equal("unsupported_mode_unchanged",0,ctx,reference,C);
    cfg[0x153c10]=0;cfg[0x153cc4]=0;status("empty_color_axis",0,hb_post_color_mode(ctx,cfg),HB_PREP_UNSUPPORTED);
    cfg[0x153c10]=1;w32(ctx+0xd478,0);w32(cfg+0x153c14,0);w32(cfg+0x153c18,2);status("invalid_color_mapping",0,hb_post_color_mode(ctx,cfg),HB_PREP_UNSUPPORTED);
    gains(ctx,1,0);w32(ctx+0x194,2);status("mode2_propagates_unsupported",0,hb_post_mode2(ctx,cfg),HB_PREP_UNSUPPORTED);
    equal("original_config_unchanged",0,config,original,K);if(reawb)equal("passive_reawb_unchanged",0,reawb,rr,R);
    printf("{\"event\":\"original_owned_post_results\",\"all_passed\":%s,\"checks\":%u,\"failures\":%u,\"golden_conversion_calls\":4096,\"normal_blend_calls\":512,\"gain_helper_calls\":1280,\"color_mode_calls\":512,\"result_ct_calls\":192,\"finalize_sequence_calls\":256,\"complete_mode2_calls\":256,\"stateful_finalize_calls\":16,\"nonidentity_color_results\":%u,\"ct_status_0\":%u,\"ct_status_92\":%u,\"ct_status_95\":%u,\"finalize_status_0\":%u,\"finalize_status_89\":%u,\"finalize_status_95\":%u,\"finalize_status_133\":%u,\"finalize_status_191\":%u,\"mode2_status_0\":%u,\"mode2_status_151\":%u,\"full_post_stage_owned\":false,\"synthetic_fixtures\":true,\"full_awb_validated\":false}\n",
        failures?"false":"true",checks,failures,nonidentity,ct_errors[0],ct_errors[92],ct_errors[95],chain_errors[0],chain_errors[89],chain_errors[95],chain_errors[133],chain_errors[191],mode2_errors[0],mode2_errors[151]);
    return failures?1:0;
}
