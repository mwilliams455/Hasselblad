/* SPDX-License-Identifier: MIT
 * Bounded original scene initialization with the exact private AWB FlatBuffer.
 * Config, tables, pointers, and context dumps are private optional outputs.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { CONTEXT_BYTES=920560, CONFIG_BYTES=1502800, CONFIG_POINTER_OFFSET=0xb2028 };
static void *symbol(void *h,const char *name) {
    void *p=dlsym(h,name);
    if (!p) { fprintf(stderr,"missing symbol %s: %s\n",name,dlerror()); _exit(3); }
    return p;
}
static void record(const char *stage,uint32_t status) {
    printf("{\"stage\":\"%s\",\"status\":%u}\n",stage,status);
    if (status) _exit(10);
}
static void dump(const char *dir,const char *name,void *p,size_t size) {
    char path[4096];
    if(snprintf(path,sizeof path,"%s/%s",dir,name)>=(int)sizeof path) _exit(64);
    FILE *f=fopen(path,"wb"); if(!f||fwrite(p,1,size,f)!=size) _exit(74); fclose(f);
}
int main(int argc,char **argv) {
    if(argc!=4) return 64;
    setvbuf(stdout,NULL,_IONBF,0);
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if(!h){fprintf(stderr,"%s\n",dlerror());return 2;}
    uint32_t (*manager)(int,void*)=symbol(h,"_create_scene_awb_lib_manager");
    uint32_t (*clear)(int)=symbol(h,"scene_awb_clear_context");
    uint32_t (*load)(void*,void**)=symbol(h,"awb_cfg_load");
    uint32_t (*cfginit)(int,void*)=symbol(h,"scene_awb_cfg_init");
    uint32_t (*sceneinit)(int)=symbol(h,"scene_awb_lib_init");
    void *(*getctx)(int)=symbol(h,"get_scene_awb_context");
    FILE *f=fopen(argv[2],"rb"); if(!f)return 66;
    if(fseek(f,0,SEEK_END)!=0)return 74;long n=ftell(f);rewind(f);
    if(n!=66728)return 65;
    void *bin=malloc((size_t)n);if(!bin||fread(bin,1,(size_t)n,f)!=(size_t)n)return 74;fclose(f);
    unsigned char *storage=malloc(CONTEXT_BYTES+128);if(!storage)return 71;
    memset(storage,0x5a,CONTEXT_BYTES+128);
    unsigned char *ctx=storage+64;memset(ctx,0,CONTEXT_BYTES);
    record("register_context",manager(0,ctx));
    if(getctx(0)!=ctx)return 5;
    record("clear_context",clear(0));
    void *cfg_handle=NULL;
    record("awb_cfg_load",load(bin,&cfg_handle));
    record("scene_awb_cfg_init",cfginit(0,cfg_handle));
    void *config=NULL;memcpy(&config,ctx+CONFIG_POINTER_OFFSET,sizeof config);
    if(!config)return 6;
    dump(argv[3],"config_original.bin",config,CONFIG_BYTES);
    dump(argv[3],"context_before_scene_init.bin",ctx,CONTEXT_BYTES);
    record("scene_awb_lib_init",sceneinit(0));
    dump(argv[3],"context_after_scene_init.bin",ctx,CONTEXT_BYTES);
    int guards=1;
    for(unsigned i=0;i<64;++i) guards &= storage[i]==0x5a && storage[CONTEXT_BYTES+64+i]==0x5a;
    uint32_t initialized;memcpy(&initialized,ctx+0x170,4);
    printf("{\"event\":\"original_scene_initialization\",\"context_bytes\":%d,"
           "\"config_bytes\":%d,\"guard_ok\":%s,\"initialized_marker\":%u,"
           "\"authentic_frame_replayed\":false,\"owned_optimizer_compared\":false}\n",
           CONTEXT_BYTES,CONFIG_BYTES,guards?"true":"false",initialized);
    _exit(guards && initialized==1 ? 0 : 7);
}
