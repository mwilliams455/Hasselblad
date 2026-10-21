/* SPDX-License-Identifier: MIT
 * Synthetic same-process differential tests; private state never enters Git. */
#include "hb_diagnostics.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000,W=HB_DEBUG_WORKSPACE_BYTES};
static unsigned checks,failures,fresh,retained,custom,large,odd,scheduled_skips;
static uint32_t rng=0xd0212026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void same(const char*s,unsigned t,const void*a,const void*b,size_t n){++checks;if(!memcmp(a,b,n))return;++failures;if(failures<=20){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;printf("{\"diagnostics_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}}
static void dump(const char*dir,const char*kind,unsigned t,const void*p,size_t n){char path[4096];if(snprintf(path,sizeof path,"%s/%s_%u.bin",dir,kind,t)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);}
static void lengths(unsigned char*c,unsigned t){unsigned a=t%4==0?0:t%4==1?510:next()%511,b=t%4==0?0:t%4==1?505:next()%(1016-a);w16(c+0xa8ba8,(uint16_t)a);w16(c+0xa8baa,(uint16_t)b);}
static void nodump(unsigned char*c,unsigned t){
    c[0xb1ef8]=t%5==0?0:t%5==1?2:1;
    w16(c+0xb1efa,t%5==2?0:3);w16(c+0xb1efc,t%5==3?0:7);
    w32(c+0xb1f00,t%2?UINT32_MAX:8); /* Neither is divisible by seven. */
}
static void setup(unsigned char*c,const unsigned char*base,unsigned t){
    static const unsigned dims[][2]={{0,0},{1,1},{2,2},{3,5},{16,16},{32,32},{33,32},{33,33},{64,64},{63,61},{64,16},{17,61},{2,64},{64,1},{1,64},{48,48}};
    memcpy(c,base,C);unsigned w=dims[t%16][0],h=dims[t%16][1];w32(c+0x18,w);w32(c+0x1c,h);w32(c+0x28,w*h);
    unsigned mode=t%4==0?0:t%4==1?1:2+t%11;w32(c+0x194,mode);c[0xa851d]=(t/4)%3;
    lengths(c,t);nodump(c,t);
    for(unsigned i=0;i<0x34c;++i)c[0xa8510+i]^=(unsigned char)t;
    c[0xa851d]=(t/4)%3;
    for(unsigned i=0;i<w*h;++i){uint32_t r=next(),b=next();if(t%3){r%=65536;b%=65536;}w32(c+0xf450+40*i,r);w32(c+0xf458+40*i,b);}
}
int hb_run_diagnostics_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    unsigned char*base=malloc(C),*fixture=malloc(C),*owned=malloc(C),*input=malloc(C),*cfg=malloc(K),rr[R],work[W+32],guard[16];if(!base||!fixture||!owned||!input||!cfg||!reawb)return 71;
    memcpy(base,c,C);memcpy(fixture,c,C);memcpy(cfg,config,K);memcpy(rr,reawb,R);memset(guard,0xa5,sizeof guard);
    for(unsigned i=0xa8510;i<0xb0b10;++i)fixture[i]=(unsigned char)next();
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;
    void(*encode)(int)=(void*)(bias+0x495c20);uint32_t(*userdump)(int)=sym(h,"scene_awb_debug_userdump"),(*debug)(int)=sym(h,"scene_awb_debug_proc");
    for(unsigned t=0;t<512;++t){memcpy(c,fixture,C);lengths(c,t);memcpy(owned,c,C);encode(0);uint32_t a=hb_debug_encode(owned),zero=0;same("encode_owned_supported",t,&a,&zero,4);same("encode_context",t,c,owned,C);}
    for(unsigned t=0;t<384;++t){memcpy(c,fixture,C);nodump(c,t);memcpy(owned,c,C);uint32_t a=userdump(0),b=hb_debug_userdump_no_file(owned);same("no_file_status",t,&a,&b,4);same("no_file_context",t,c,owned,C);scheduled_skips+=t%5==4;}
    for(unsigned t=0;t<1024;++t){setup(c,fixture,t);memcpy(owned,c,C);memcpy(input,c,C);memset(work,0xa5,sizeof work);
        unsigned mode=t%4==0?0:t%4==1?1:2+t%11;if(mode>=2)++custom;else if(c[0xa851d])++fresh;else ++retained;
        static const unsigned large_flags[]={0,0,0,0,0,0,1,1,1,1,0,1,0,0,0,1};large+=large_flags[t%16];odd+=t%16==3||t%16==6||t%16==7||t%16==9||t%16==11;
        uint32_t a=debug(0),b=hb_debug_process(owned,work+16,W);unsigned before=failures;same("debug_status",t,&a,&b,4);same("debug_context",t,c,owned,C);same("workspace_front_guard",t,work,guard,16);same("workspace_rear_guard",t,work+16+W,guard,16);
        if(t<16||(failures!=before&&failures<20)){dump(dir,"debug_input",t,input,C);dump(dir,"debug_original",t,c,C);dump(dir,"debug_owned",t,owned,C);}}
    /* Exact coarse quantization/saturation boundaries, including wrapped sums. */
    static const uint32_t targets[]={0,1,399,400,401,1599,1600,1601,102399,102400,409599,409600,UINT32_MAX,0xfffffff0u,25600,65535};
    for(unsigned t=0;t<64;++t){memcpy(c,fixture,C);unsigned side=t<32?2:64,n=side*side;w32(c+0x18,side);w32(c+0x1c,side);w32(c+0x28,n);w32(c+0x194,2);w16(c+0xa8ba8,0);w16(c+0xa8baa,0);c[0xb1ef8]=0;memset(c+0xf450,0,40*n);
        uint32_t value=targets[t%16],first=(t/16)%2?UINT32_MAX:value,second=(t/16)%2?value+1:0;
        w32(c+0xf450,first);w32(c+0xf458,first);w32(c+0xf478,second);w32(c+0xf480,second);memcpy(owned,c,C);
        uint32_t a=debug(0),b=hb_debug_process(owned,work+16,W);same("packing_boundary_status",t,&a,&b,4);same("packing_boundary_context",t,c,owned,C);}
    /* Carry fresh and rejected diagnostics forward across actual calls. */
    setup(c,fixture,5);w32(c+0x194,0);c[0xb1ef8]=0;
    for(unsigned t=0;t<256;++t){c[0xa851d]=t%3==0?0:t%3==1?1:255;w32(c+0xa8510,next());w32(c+0xa85d2,next());w32(c+0xa86f7,next());memcpy(owned,c,C);uint32_t a=debug(0),b=hb_debug_process(owned,work+16,W);same("stateful_debug_status",t,&a,&b,4);same("stateful_debug_context",t,c,owned,C);memcpy(c,owned,C);if(t<3||t==255){dump(dir,"stateful_original",t,c,C);dump(dir,"stateful_owned",t,owned,C);}}
    /* Guard behavior is owned-only; do not run unsafe originals. */
    for(unsigned t=0;t<8;++t){setup(c,fixture,5);c[0xb1ef8]=0;size_t bytes=W;
        if(t==0)w16(c+0xa8ba8,511);if(t==1){w16(c+0xa8ba8,510);w16(c+0xa8baa,506);}if(t==2)w32(c+0x18,65);if(t==3)w32(c+0x1c,65);if(t==4)w32(c+0x28,1);if(t==5)bytes=W-1;if(t==6){c[0xb1ef8]=1;w16(c+0xb1efa,1);w16(c+0xb1efc,1);}if(t==7){c[0xb1ef8]=1;w16(c+0xb1efa,1);w16(c+0xb1efc,7);w32(c+0xb1f00,7);}
        memcpy(owned,c,C);memset(work,0xa5,sizeof work);unsigned char snapshot[W+32];memcpy(snapshot,work,sizeof work);uint32_t a=hb_debug_process(c,work+16,bytes),b=HB_PREP_UNSUPPORTED;same("owned_guard_status",t,&a,&b,4);same("owned_guard_context",t,c,owned,C);same("owned_guard_workspace",t,work,snapshot,sizeof work);}
    same("configuration_immutable",0,config,cfg,K);same("reawb_immutable",0,reawb,rr,R);memcpy(c,base,C);
    printf("{\"event\":\"owned_diagnostics_no_file\",\"checks\":%u,\"mismatches\":%u,\"encoding_cases\":512,\"userdump_no_file_cases\":384,\"full_debug_cases\":1024,\"fresh_backup_cases\":%u,\"retained_backup_cases\":%u,\"custom_mode_cases\":%u,\"large_statistics_cases\":%u,\"odd_dimension_cases\":%u,\"scheduled_skip_helper_cases\":%u,\"packing_boundary_cases\":64,\"stateful_calls\":256,\"owned_only_guard_checks\":24,\"all_passed\":%s,\"debug_file_io_owned\":false,\"synthetic_inputs\":true}\n",checks,failures,fresh,retained,custom,large,odd,scheduled_skips,failures?"false":"true");return failures?1:0;
}
