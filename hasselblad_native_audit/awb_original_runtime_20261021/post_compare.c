/* SPDX-License-Identifier: MIT
 * Whole-context differential checks against the pinned, unmodified firmware.
 * Inputs are synthetic; private camera tables are never embedded here. */
#include "hb_post_controller.h"
#include "hb_stat_prepare.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
enum{C=920560,K=1502800,R=1000};
static unsigned checks,failures,inverse_cases,publish_cases,post_cases,post_status[256],stateful_cases,sync_changed,manual_applied,manual_fallback,color_calls;
static uint32_t rng=0x21c02026;
static uint32_t next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static void w32(void*p,uint32_t v){memcpy(p,&v,4);}
static void w16(void*p,uint16_t v){memcpy(p,&v,2);}
static void wf(void*p,float v){memcpy(p,&v,4);}
static void *sym(void*h,const char*s){void*p=dlsym(h,s);if(!p)_exit(3);return p;}
static void dump(const char*dir,const char*name,const void*p,size_t n){char path[4096];if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);FILE*f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);}
static void equal(const char*s,unsigned t,const void*a,const void*b,size_t n){++checks;if(!memcmp(a,b,n))return;++failures;if(failures<=40){const unsigned char*x=a,*y=b;size_t i=0;while(i<n&&x[i]==y[i])++i;printf("{\"post_mismatch\":\"%s\",\"case\":%u,\"offset\":%zu,\"original\":%u,\"owned\":%u}\n",s,t,i,x[i],y[i]);}}
static void record(unsigned char*p,unsigned t){for(unsigned j=0;j<0x9c;++j)p[j]=(unsigned char)next();p[0]=1;for(unsigned j=0;j<9;++j)w32(p+4+4*j,j%3==1?4096:3000+(t*23+j*17)%5000);for(unsigned j=0;j<6;++j)w32(p+0x74+4*j,4000+j*100);w32(p+0x58,2000+t*31%8000);w32(p+0x5c,3000+t*31%7000);}
static void setup(unsigned char*c,unsigned char*k,const unsigned char*base,const unsigned char*cfg,unsigned t){memcpy(c,base,C);memcpy(k,cfg,K);memcpy(c+0xb2028,&k,8);w32(c+0x194,t%2);k[0x153c0c]=0;k[0x16eae4]=0;k[0xca078]=0;c[0xd47c]=c[0xd4a4]=c[0xd338]=c[0xee84]=0;
    record(c+0xb0b10,t);record(c+0xb0bac,t+1);record(c+0xb0c48,t+2);record(c+0xb0ce4,t+3);
    for(unsigned i=0;i<4;++i){unsigned char*p=c+0x84164+0x74*i;memset(p,0,0x74);p[0]=(t>>i)&1;for(unsigned j=0;j<9;++j)w32(p+4+4*j,j%3==1?4096:2000+next()%6000);w32(p+104,100+next()%2000);w32(p+112,1+next()%256);w16(c+0x3da50+2*i,(uint16_t)(1+next()%256));memcpy(c+0x40f8+0x74*i,p,0x74);c[0x40f8+0x74*i]=(t>>(i+2))&1;}
    for(unsigned i=0;i<2;++i){unsigned char*p=k+0x15a30+0x2bd0*i;p[0]=(t>>(i+4))&1;p[8]=0;}
    c[0x84128]=c[0x840fc]=0;w32(c+0x8415c,0);w32(c+0x84160,0);w32(c+0x4168,17+t);w32(c+0x41dc,19+t);
    for(unsigned j=0;j<4;++j)w32(k+0x44+4*j,16+j*17);w32(k+0x54,90);w32(k+0x58,81);for(unsigned j=0;j<4;++j)w32(k+0x60+4*j,100-j*11);
    c[0x42c8]=t%3!=0;for(unsigned i=0;i<10;++i)w16(c+0xa84f2+2*i,(uint16_t)(t%5==0?0:1));w32(c+0xb2020,0);
    for(unsigned s=0;s<2;++s){unsigned char*p=c+(s?0x42dc:0x4314);w32(p,31);w32(p+4,63);for(unsigned j=0;j<12;++j)w32(p+8+4*j,3000+next()%4000);}
    k[0x5c]=t%3==0;k[0x138294]=t%2;k[0x16446c]=t%3==1;c[0xc4cc]=t%9;c[0xc4ce]=t%2;w32(c+0xef34,t%9);w32(c+0x4368,t%8);w32(c+0x42d8,(t+3)%8);c[0x42ca]=t%2;
    for(unsigned i=0;i<9;++i){w32(k+0x1385f8+0x58*i,20+i*7);w32(k+0x1385fc+0x58*i,30+i*5);}for(unsigned i=0;i<10;++i)w32(k+0x16aa30+4*i,12+i*9);
    w32(c+0x434c,100+next()%1000);w32(c+0xc434,t%2);w32(c+0xc44c,113);w32(c+0xc43c,273);w32(c+0x4360,t%3);w32(c+0x42d4,t%3);w16(c+0x42cc,(uint16_t)(t%4==0?239:t%4==1?240:t%4==2?0:100));c[0x42c9]=t%2;
    c[0x42d2]=t%2;c[0x42d3]=(t/2)%2;c[0x990dc]=(t/4)%2;c[0x42cf]=t%2;w16(c+0x42d0,t%4);w16(c+0x4358,(uint16_t)next());w16(c+0x435a,(uint16_t)next());
    w32(c+0x28,12);for(unsigned j=0;j<12;++j){unsigned char*p=c+0xf450+40*j;memset(p,0,40);unsigned row=(t+j*5)%81;w32(p,u32(c+0x348+16*row));w32(p+4,4096);w32(p+8,u32(c+0x34c+16*row));w32(p+12,2000+100*row);w32(p+20,j%3);}
}
static void tree(unsigned char*p,unsigned depth,unsigned levels,int sign){static const size_t strides[]={0x1a48,0x348,0x68,12};unsigned index=depth+4-levels;p[4]=2;for(unsigned i=0;i<2;++i){unsigned char*q=p+8+i*strides[index];w32(q,sign&&index==3?(uint32_t)(i?500:-500):i?10000:0);if(index==3){w32(q+4,2000+next()%5000);w32(q+8,2000+next()%5000);}else tree(q,depth+1,levels,sign);}}
int hb_run_post_tests(void*h,unsigned char*c,void*config,void*reawb,const char*dir){
    uintptr_t bias=(uintptr_t)sym(h,"get_scene_awb_context")-0x464068;float table[124];memcpy(table,(void*)(bias+0x6ce418),sizeof table);hb_temperature_model model={table};dump(dir,"isotemperature_table.bin",table,sizeof table);
    uint32_t(*inverse)(int,uint32_t,uint32_t,uint32_t*,uint32_t*,uint32_t*,float)=sym(h,"scene_awb_ct_tint_to_gain");
    uint32_t(*category)(int)=(void*)(bias+0x4a0958),(*publish)(int)=(void*)(bias+0x4a0d80),(*post)(int)=sym(h,"scene_awb_post_proc");
    uint32_t(*smooth)(void*,uint32_t,uint32_t,const void*,void*,uint32_t)=(void*)(bias+0x4a3128);
    uint32_t(*merge)(int,const void*,uint32_t*,uint32_t*)=(void*)(bias+0x4a2668),(*iso)(const void*,uint32_t,uint32_t,int32_t,uint32_t*,uint32_t*)=(void*)(bias+0x4a2ce0),(*gate)(int,unsigned,const void*,uint32_t*)=(void*)(bias+0x4a2538);
    unsigned char*base=malloc(C),*cfg=malloc(K),*k=malloc(K),*owned=malloc(C),*input=malloc(C),*rr=malloc(R),*row=calloc(1,0xd248);if(!base||!cfg||!k||!owned||!input||!rr||!row)return 71;memcpy(base,c,C);memcpy(cfg,config,K);if(reawb)memcpy(rr,reawb,R);
    for(unsigned t=0;t<512;++t){setup(c,k,base,cfg,t);uint32_t ct=t<500?1000+t*31:t==500?0:next(),scale=t%13==0?next():4096,a[3]={0},b[3]={0};float tint=(float)((int)(t%81)-40)*1.25f;uint32_t x=inverse(0,ct,scale,a,a+1,a+2,tint),y=hb_post_inverse(c,k,&model,ct,tint,scale,b);equal("inverse_status",t,&x,&y,4);equal("inverse_gains",t,a,b,12);++inverse_cases;}
    for(unsigned t=0;t<256;++t){unsigned char s[64],o[64],in[0x9c],a[0x9c],b[0x9c];for(unsigned i=0;i<64;++i)s[i]=(unsigned char)next();memcpy(o,s,64);record(in,t);record(a,t+1);memcpy(b,a,sizeof b);uint32_t w1=t<200?next()%129:next(),w2=t<200?next()%129:next(),scale=1000+t;uint32_t x=smooth(s,w1,w2,in,a,scale),y=hb_post_smooth(o,w1,w2,in,b,scale);equal("smooth_status",t,&x,&y,4);equal("smooth_state",t,s,o,64);equal("smooth_record",t,a,b,sizeof a);}
    for(unsigned t=0;t<128;++t){setup(c,k,base,cfg,t);tree(row,0,4,0);w32(c+0xb0c04,t*97);w32(c+0x8415c,t*89);w32(c+0x84160,t*83);w32(c+0x84154,t*79);uint32_t a[2]={0},b[2]={0},x=merge(0,row,a,a+1),y=hb_post_merge_row(c,row,b,b+1);equal("merge_row_status",t,&x,&y,4);equal("merge_row_values",t,a,b,8);
        tree(row,0,3,1);x=iso(row,t*97,t*89,(int32_t)t*13-700,a,a+1);y=hb_post_iso_row(row,t*97,t*89,(int32_t)t*13-700,b,b+1);equal("iso_row_status",t,&x,&y,4);equal("iso_row_values",t,a,b,8);
        memset(row,0,0x48);row[4]=t%9;for(unsigned j=0;j<8;++j){row[8+8*j]=j*32;w32(row+12+8*j,100+j*97);}w16(c+0x3da54+2*(t%2),t*3);x=gate(0,t%2,row,a);y=hb_post_gate(c,t%2,row,b);equal("gate_status",t,&x,&y,4);equal("gate_value",t,a,b,4);
    }
    uint32_t(*otint)(int,int32_t,const void*,uint16_t*,int16_t*)=sym(h,"scene_awb_switch_sensor_trans_tint_calc");
    uint32_t(*otrans)(int,uint32_t,uint32_t,int32_t)=sym(h,"scene_awb_switch_sensor_trans_proc");
    uint32_t(*ozones)(int,uint32_t*,unsigned char*,float*,const uint32_t*,const uint32_t*)=sym(h,"scene_awb_sync_zone_info");
    uint32_t(*oshift)(int,uint32_t*,uint32_t*,uint32_t*,uint32_t,uint32_t,const uint32_t*,const uint32_t*,uint32_t,uint32_t,uint32_t)=sym(h,"scene_awb_sync_gain_shift");
    uint32_t(*osync)(int)=sym(h,"scene_awb_sync_calc_proc");
    for(unsigned t=0;t<256;++t){setup(c,k,base,cfg,t);unsigned char tintrow[52]={0};tintrow[2]=3;for(unsigned j=0;j<3;++j){w16(tintrow+4+6*j,(uint16_t)((int)j*100-100));w16(tintrow+6+6*j,3000+j*1700);w16(tintrow+8+6*j,(uint16_t)((int)j*30-30));}uint16_t ca=0,cb=0;int16_t ta=0,tb=0;uint32_t x=otint(0,(int)t*2-200,tintrow,&ca,&ta),y=hb_post_sensor_tint(tintrow,(int)t*2-200,&cb,&tb);equal("sensor_tint_status",t,&x,&y,4);equal("sensor_tint_ct",t,&ca,&cb,2);equal("sensor_tint_tint",t,&ta,&tb,2);
        c[0xd32c]=1;k[0x1531e6]=1;w32(k+0x1531e8,31);k[0x1531ec]=3;for(unsigned j=0;j<3;++j){memcpy(k+0x1531ee + 0x34*j,tintrow,52);w16(k+0x1531ee + 0x34*j,3000+j*2000);for(unsigned l=0;l<3;++l)w16(k+0x1531f4+0x34*j+6*l,2000+j*1200+l*300);}
        memcpy(owned,c,C);x=otrans(0,t%7==0?32:31,2000+t*29,(int)t-120);y=hb_post_sensor_transform(owned,k,t%7==0?32:31,2000+t*29,(int)t-120);equal("sensor_transform_status",t,&x,&y,4);equal("sensor_transform_context",t,c,owned,C);
        uint32_t r[8],b[8],act[8]={0},bct[8]={0};unsigned char av[8]={0},bv[8]={0};float aw[8]={0},bw[8]={0};for(unsigned j=0;j<8;++j){unsigned i=(t+j*7)%81;r[j]=u32(c+0x348+16*i)+(int)(t%31)-15;b[j]=u32(c+0x34c+16*i)+(int)(t%47)-23;if((t+j)%17==0)r[j]=0;}
        x=ozones(0,act,av,aw,r,b);y=hb_post_sync_zones(c,k,bct,bv,bw,r,b);equal("sync_zones_status",t,&x,&y,4);equal("sync_zones_ct",t,act,bct,sizeof act);equal("sync_zones_valid",t,av,bv,sizeof av);equal("sync_zones_weight",t,aw,bw,sizeof aw);
        uint32_t a[3]={4000+t,4096,5000+t},o[3],current[3]={4200,4096,5300};memcpy(o,a,12);c[0x2c]=8;for(unsigned j=0;j<8;++j){c[0x98f48+32*j]=(t+j)%3==0;w32(c+0x98f4c+32*j,r[j]);w32(c+0x98f54+32*j,b[j]);r[j]+=100;b[j]+=200;}
        x=oshift(0,a,a+1,a+2,4100,5400,r,b,4200,4096,5300);y=hb_post_sync_shift(c,k,o,4100,5400,r,b,current);equal("sync_shift_status",t,&x,&y,4);equal("sync_shift_gains",t,a,o,12);
        w16(c+0x9c18c,3000+t*17);wf(c+0x9c190,(float)((int)t%40-20));w32(c+0x9c19c,31);w16(c+0x9c186,4100);w16(c+0x9c18a,5400);for(unsigned j=0;j<8;++j){w32(c+0x9c144+4*j,r[j]);w32(c+0x9c164+4*j,b[j]);}wf(k+0x16eae8,t%2?0.1f:0.4f);wf(k+0x16eaec,t%2?0.4f:0.1f);w32(c+0xb0b78,500);memcpy(owned,c,C);memcpy(input,c,C);
        x=osync(0);y=hb_post_sync(owned,k,&model);unsigned before=failures;equal("sync_status",t,&x,&y,4);equal("sync_context",t,c,owned,C);sync_changed+=memcmp(input,c,C)!=0;if(before!=failures&&failures<=40){char n[96];snprintf(n,sizeof n,"sync_%u_original.bin",t);dump(dir,n,c,C);snprintf(n,sizeof n,"sync_%u_owned.bin",t);dump(dir,n,owned,C);snprintf(n,sizeof n,"sync_%u_input.bin",t);dump(dir,n,input,C);snprintf(n,sizeof n,"sync_%u_cfg.bin",t);dump(dir,n,k,K);}
    }
    for(unsigned kind=0;kind<3;++kind)for(unsigned t=0;t<(kind==2?1024:384);++t){setup(c,k,base,cfg,t);if(kind==0)w32(c+0x194,t%12);if(kind==1){w32(c+0x194,t%12);w32(c+0xc434,(t/5)%2);w32(c+0x84158,(t/7)%2);if(reawb){((unsigned char*)reawb)[0x1c]=(t/13)%2;((unsigned char*)reawb)[0x21]=(t/17)%2;}}
        if(kind==2){if(t>=256)w32(c+0x194,2+t%10);if(t%13==0){c[0xd338]=1;record(c+0xd33c,t);}if(t%17==0){c[0xd47c]=1;w16(c+0xd484,5400);w16(c+0xd47e,4400);w32(c+0xd488,7);w32(c+0xd480,(uint32_t)-12);}if(t%19==0){k[0x16446c]=1;c[0xee84]=1;w32(c+0xeeb4,128);w32(c+0xee94,5200);w32(c+0xee9c,7100);}}
        if(kind==2&&t>=384){w32(c+0x194,t%2);c[0x84164]=1;
            if(t<512){k[0x15a30]=1;k[0x15a38]=1;c[0x8424c]=0;k[0x15a44]=2;for(unsigned j=0;j<2;++j){unsigned char*p=k+0x15a48+0x48*j;w32(p,j*3000);p[4]=2;p[8]=0;p[16]=255;w32(p+12,64+j*32);w32(p+20,192+j*32);}}
            else if(t<640){k[0xca078]=2;for(unsigned j=0;j<2;++j){unsigned char*p=k+0xca07c+0xd248*j;w32(p,j*20);tree(p,0,4,0);}wf(c+0x37618,(float)(t%25));w32(c+0xb0c04,2000+(t%81)*100);}
            else if(t<768){c[0xd4a4]=1;k[0x153ec0]=2;for(unsigned j=0;j<2;++j){unsigned char*p=k+0x153ec4+0x1a48*j;wf(p,(float)j*20-10);tree(p,0,3,1);}wf(c+0x990d0,(float)(t%10));wf(c+0x990d4,(float)(t%40)-20);}
            else if(t<896){c[0x990dc]=0;k[0x16eae4]=1;k[0x16eae5]=3;c[0x9c184]=1;c[0xd32c]=0;c[0x2c]=0;w16(c+0x9c18c,3000+(t%81)*100);wf(c+0x9c190,(float)((int)(t%30)-15));wf(k+0x16eae8,0.1f);wf(k+0x16eaec,0.4f);}
            else{w32(c+0xb0c4c,0);w32(c+0xb0d64,0);if(t%2)w32(c+0x1c0,0);if(t%3==0)w32(c+0x84168,0);if(t%5==0){c[0x84164]=0;c[0x841d8]=0;k[0x15a30]=k[0x18600]=0;}}
        }
        if(kind==2&&t%23==0){++color_calls;k[0x153c0c]=1;k[0x153c10]=1;w32(c+0xd478,0);w32(k+0x153c14,0);w32(k+0x153c18,0);for(unsigned j=0;j<2;++j){unsigned char*p=k+0x153cc4+124*j;p[0]=2;w32(p+4,2000);w32(p+16,10000);w32(p+8,3800);w32(p+12,4500);w32(p+20,4300);w32(p+24,3900);}}
        memcpy(owned,c,C);memcpy(input,c,C);uint32_t x=kind==0?category(0):kind==1?publish(0):post(0);uint32_t y=kind==0?hb_post_category(owned,k):kind==1?hb_post_publish(owned,k,reawb):hb_post_process(owned,k,&model,reawb);unsigned before=failures;equal(kind==0?"category_status":kind==1?"publish_status":"post_status",t,&x,&y,4);equal(kind==0?"category_context":kind==1?"publish_context":"post_context",t,c,owned,C);
        if(kind==1)++publish_cases;if(kind==2){manual_applied+=input[0xd47c]==1&&!c[0xd47c];manual_fallback+=input[0xd47c]==1&&!c[0xd47c]&&c[0xb0b10]!=1&&u32(c+0xb0b68)==5400;++post_cases;if(x<256)++post_status[x];}
        if((failures!=before&&failures<=40)||(kind==2&&t<8)){char n[128];snprintf(n,sizeof n,"kind_%u_case_%u_input.bin",kind,t);dump(dir,n,input,C);snprintf(n,sizeof n,"kind_%u_case_%u_original.bin",kind,t);dump(dir,n,c,C);snprintf(n,sizeof n,"kind_%u_case_%u_owned.bin",kind,t);dump(dir,n,owned,C);snprintf(n,sizeof n,"kind_%u_case_%u_cfg.bin",kind,t);dump(dir,n,k,K);}
    }
    setup(c,k,base,cfg,2);k[0x5c]=1;k[0x138294]=0;k[0x16446c]=0;c[0x42c8]=0;w32(c+0x194,0);w16(c+0xa84f2,1);if(reawb){((unsigned char*)reawb)[0x1c]=0;((unsigned char*)reawb)[0x21]=1;}
    for(unsigned t=0;t<288;++t){c[0x84164]=t%17!=0;c[0x841d8]=t%7==0;w32(c+0x84168,2500+t*13);w32(c+0x84170,8000-t*11);w32(c+0x84174,2900+t*12);w32(c+0x8417c,7700-t*9);w32(c+0xc434,t<8?1:0);c[0x84128]=0;memcpy(owned,c,C);uint32_t x=post(0),y=hb_post_process(owned,k,&model,reawb);equal("stateful_post_status",t,&x,&y,4);equal("stateful_post_context",t,c,owned,C);++stateful_cases;if(t==0||t==8||t==248||t==287){char n[96];snprintf(n,sizeof n,"stateful_%u_original.bin",t);dump(dir,n,c,C);snprintf(n,sizeof n,"stateful_%u_owned.bin",t);dump(dir,n,owned,C);}memcpy(c,owned,C);}
    uint32_t timer=u32(c+0x42d4),zero=0;equal("stateful_fast_smoothing_expired",288,&timer,&zero,4);
    /* Unsupported malformed inputs are owned-only: the original may read past
     * fixed table storage or abort. They must not masquerade as parity cases. */
    setup(c,k,base,cfg,0);uint32_t unsupported=HB_PREP_UNSUPPORTED,a[3]={0};memset(row,0,0xd248);row[4]=9;uint32_t st=hb_post_merge_row(c,row,a,a+1);equal("oversized_merge_guard",0,&st,&unsupported,4);st=hb_post_inverse(c,k,NULL,5000,0,4096,a);equal("missing_model_guard",0,&st,&unsupported,4);
    if(reawb)memcpy(reawb,rr,R);memcpy(c,base,C);printf("{\"event\":\"owned_post_controller\",\"checks\":%u,\"mismatches\":%u,\"inverse_cases\":%u,\"publish_cases\":%u,\"post_cases\":%u,\"post_successes\":%u,\"stateful_cases\":%u,\"sync_changed_cases\":%u,\"manual_requests_cleared\":%u,\"manual_fallback_applied\":%u,\"active_color_calls\":%u,\"post_invalid_results\":%u,\"all_passed\":%s,\"synthetic_inputs\":true,\"authentic_frame_replayed\":false}\n",checks,failures,inverse_cases,publish_cases,post_cases,post_status[0],stateful_cases,sync_changed,manual_applied,manual_fallback,color_calls,post_status[151],failures?"false":"true");return failures?1:0;
}
