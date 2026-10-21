/* SPDX-License-Identifier: MIT
 * Original top-level initialization. All binary/config dumps stay private.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { CONTEXT_BYTES=920560, CONFIG_BYTES=1502800, E2_BYTES=0x1ce90 };
#ifdef HB_ROI_COMPARE
int hb_run_roi_tests(void*,unsigned char*,void*,const char*);
#endif
#ifdef HB_STAT_DIFFERENCE_COMPARE
int hb_run_stat_difference_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_USER_FINISH_COMPARE
int hb_run_user_finish_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_USER_CONTROLS_COMPARE
int hb_run_user_controls_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_USER_MANUAL_COMPARE
int hb_run_user_manual_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_USER_E_ND_COMPARE
int hb_run_user_e_nd_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_USER_PREPARE_COMPARE
int hb_run_user_prepare_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_WHITE_LUT_COMPARE
int hb_run_white_lut_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_RUN_ENTRY_COMPARE
int hb_run_entry_tests(void*,unsigned char*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_DIAGNOSTICS_COMPARE
int hb_run_diagnostics_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_COMPLETION_COMPARE
int hb_run_completion_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_POST_COMPARE
int hb_run_post_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_POST_RESULTS_COMPARE
int hb_run_post_results_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_ATMOSPHERE_COMPARE
int hb_run_atmosphere_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_HISTORY_COMPARE
int hb_run_history_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_CONTROLLER_COMPARE
int hb_run_controller_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_TEMPERATURE_COMPARE
int hb_run_temperature_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_PREPARE_COMPARE
int hb_run_prepare_tests(void*,unsigned char*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_CANDIDATES_COMPARE
int hb_run_candidate_tests(void*,unsigned char*,void*,void*,const char*);
#endif
#ifdef HB_SCENE_PIPELINE
int hb_run_scene_pipeline(void*,unsigned char*,unsigned char*,void*,void*,const char*);
#endif
static void *symbol(void *h,const char *name) {
    void *p=dlsym(h,name);
    if(!p){fprintf(stderr,"missing symbol %s: %s\n",name,dlerror());_exit(3);}
    return p;
}
static uint32_t u32(const void *p) {uint32_t v;memcpy(&v,p,4);return v;}
static void record(const char *stage,uint32_t status) {
    printf("{\"stage\":\"%s\",\"status\":%u}\n",stage,status);
    if(status)_exit(10);
}
static void dump(const char *dir,const char *name,const void *p,size_t n) {
    char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path)_exit(64);
    FILE *f=fopen(path,"wb");if(!f||fwrite(p,1,n,f)!=n)_exit(74);fclose(f);
}
int main(int argc,char **argv) {
    if(argc!=4)return 64;
    setvbuf(stdout,NULL,_IONBF,0);
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if(!h){fprintf(stderr,"%s\n",dlerror());return 2;}
    uint32_t (*load)(void*,void**)=symbol(h,"awb_cfg_load");
    uint32_t (*init)(int,void*)=symbol(h,"awb_lib_init");
    unsigned char *(*getctx)(int)=symbol(h,"get_scene_awb_context");
    FILE *f=fopen(argv[2],"rb");if(!f)return 66;
    if(fseek(f,0,SEEK_END)!=0)return 74;long n=ftell(f);rewind(f);
    if(n!=66728)return 65;
    void *bin=malloc((size_t)n);if(!bin||fread(bin,1,(size_t)n,f)!=(size_t)n)return 74;fclose(f);
    void *handle=NULL;
    record("awb_cfg_load",load(bin,&handle));
    record("awb_lib_init",init(0,&handle));
    unsigned char *ctx=getctx(0);
    if(!ctx||u32(ctx+0x170)!=1)return 5;
    void *config=NULL;memcpy(&config,ctx+0xb2028,8);if(!config)return 6;
    uintptr_t bias=(uintptr_t)getctx-0x464068;
    void *(*gete2)(int)=(void*(*)(int))(bias+0x4dd468);
    unsigned char *e2=gete2(0);if(!e2)return 7;
    void *reawb=NULL;memcpy(&reawb,(void*)(bias+0x791450),sizeof reawb);
    if(reawb)dump(argv[3],"full_reawb.bin",reawb,1000);
    dump(argv[3],"full_context.bin",ctx,CONTEXT_BYTES);
    dump(argv[3],"full_config.bin",config,CONFIG_BYTES);
    dump(argv[3],"full_e2.bin",e2,E2_BYTES);
    printf("{\"event\":\"original_full_initialization\",\"initialized_marker\":%u,"
           "\"context_bytes\":%d,\"config_bytes\":%d,\"e2_bytes\":%d,\"e2_context_present\":true,\"reawb_handle_present\":%s}\n",
           u32(ctx+0x170),CONTEXT_BYTES,CONFIG_BYTES,E2_BYTES,reawb?"true":"false");
#ifdef HB_PREPARE_COMPARE
    _exit(hb_run_prepare_tests(h,ctx,e2,config,reawb,argv[3]));
#endif
#ifdef HB_SCENE_PIPELINE
    _exit(hb_run_scene_pipeline(h,ctx,e2,config,reawb,argv[3]));
#endif
#ifdef HB_CANDIDATES_COMPARE
    _exit(hb_run_candidate_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_TEMPERATURE_COMPARE
    _exit(hb_run_temperature_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_ROI_COMPARE
    _exit(hb_run_roi_tests(h,ctx,config,argv[3]));
#endif
#ifdef HB_STAT_DIFFERENCE_COMPARE
    _exit(hb_run_stat_difference_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_USER_FINISH_COMPARE
    _exit(hb_run_user_finish_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_USER_CONTROLS_COMPARE
    _exit(hb_run_user_controls_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_USER_MANUAL_COMPARE
    _exit(hb_run_user_manual_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_USER_E_ND_COMPARE
    _exit(hb_run_user_e_nd_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_USER_PREPARE_COMPARE
    _exit(hb_run_user_prepare_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_WHITE_LUT_COMPARE
    _exit(hb_run_white_lut_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_RUN_ENTRY_COMPARE
    _exit(hb_run_entry_tests(h,ctx,e2,config,reawb,argv[3]));
#endif
#ifdef HB_DIAGNOSTICS_COMPARE
    _exit(hb_run_diagnostics_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_COMPLETION_COMPARE
    _exit(hb_run_completion_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_POST_COMPARE
    _exit(hb_run_post_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_POST_RESULTS_COMPARE
    _exit(hb_run_post_results_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_ATMOSPHERE_COMPARE
    _exit(hb_run_atmosphere_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_HISTORY_COMPARE
    _exit(hb_run_history_tests(h,ctx,config,reawb,argv[3]));
#endif
#ifdef HB_CONTROLLER_COMPARE
    _exit(hb_run_controller_tests(h,ctx,config,reawb,argv[3]));
#endif
    _exit(0);
}
