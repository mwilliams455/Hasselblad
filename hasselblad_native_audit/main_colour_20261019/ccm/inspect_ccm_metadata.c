/* SPDX-License-Identifier: MIT
 * Original read-only CCM metadata probe for exact-hash X2D II 1.3.16.2 librcam.
 * No camera function is invoked. dlopen runs the original initializers.
 * All data offsets come from audited AArch64 consumers in this exact ELF.
 */
#define _GNU_SOURCE 1
#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static uintptr_t bias;
static int inside(uintptr_t p, size_t n) {
    uintptr_t v=p-bias;
    return p>=bias && v+n>=v &&
           ((v>=UINT64_C(0x2b000) && v+n<=UINT64_C(0x56e184)) ||
            (v>=UINT64_C(0x580e20) && v+n<=UINT64_C(0x5b8608)));
}
static uintptr_t pointer_at(uintptr_t p) {
    uintptr_t result=0;
    if (!inside(p,8)) { fputs("metadata pointer out of bounds\n",stderr); _exit(20); }
    memcpy(&result,(void *)p,8);
    return result;
}
static uint32_t word_at(uintptr_t p) {
    uint32_t result=0;
    if (!inside(p,4)) { fputs("metadata word out of bounds\n",stderr); _exit(21); }
    memcpy(&result,(void *)p,4);
    return result;
}
int main(int argc,char **argv) {
    if (argc!=2) return 64;
    setvbuf(stdout,NULL,_IONBF,0);
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if (!h) { fprintf(stderr,"dlopen: %s\n",dlerror()); return 2; }
    void *a=dlsym(h,"dcam_isp_vreg_get_type");
    Dl_info info;
    if (!a || !dladdr(a,&info) || !info.dli_fname || strcmp(info.dli_fname,argv[1]) || info.dli_saddr!=a) return 3;
    bias=(uintptr_t)a-UINT64_C(0x54b88);
    uintptr_t dispatch=pointer_at(bias+UINT64_C(0x59c240)+50*8);
    int dispatch_ok=dispatch==bias+UINT64_C(0x3b9ea8);
    printf("{\"event\":\"calc_dispatch\",\"table_va\":\"0x59c240\",\"index\":50,"
           "\"target_va\":\"0x%" PRIxPTR "\",\"matches\":%s}\n",
           dispatch-bias,dispatch_ok?"true":"false");
    if (!dispatch_ok) return 9;
    uintptr_t reg_table=pointer_at(bias+UINT64_C(0x59e048));
    uintptr_t count_addr=pointer_at(bias+UINT64_C(0x59e148));
    uintptr_t groups=pointer_at(bias+UINT64_C(0x59e150));
    uint32_t group_count=word_at(count_addr);
    if (group_count>16) return 4;
    printf("{\"event\":\"main_ccm_metadata\",\"register_table_va\":\"0x%" PRIxPTR
           "\",\"groups_va\":\"0x%" PRIxPTR "\",\"group_count\":%u}\n",
           reg_table-bias,groups-bias,group_count);
    for (uint32_t g=0;g<group_count;g++) {
        uintptr_t group=groups+g*24;
        uintptr_t params=pointer_at(group);
        uint32_t count=word_at(group+8);
        if (count>64) return 5;
        printf("{\"event\":\"parameter_group\",\"group\":%u,\"params_va\":\"0x%" PRIxPTR
               "\",\"count\":%u,\"register_group_id\":%u}\n",g,params-bias,count,word_at(group+12));
        for (uint32_t j=0;j<count;j++) {
            uintptr_t param=params+j*48;
            uintptr_t id_addr=pointer_at(param);
            uint32_t ids=word_at(param+8);
            if (!ids || ids>32) return 7;
            for (uint32_t k=0;k<ids;k++) {
                uint32_t id=word_at(id_addr+4*k);
                if (id>8191) return 8;
                uintptr_t descriptor=reg_table+(uintptr_t)id*16;
                uint32_t header=word_at(descriptor), type=header&65535;
                uint32_t parent=(type==3)?header>>16:id;
                if (parent>8191) return 10;
                uintptr_t parent_desc=reg_table+(uintptr_t)parent*16;
                uint32_t group_num=(type==2||type==3)?word_at(parent_desc+12):1;
                printf("{\"event\":\"parameter\",\"group\":%u,\"index\":%u,"
                       "\"parameter_va\":\"0x%" PRIxPTR "\",\"register_slot\":%u,\"register_count\":%u,\"register_id\":%u,"
                       "\"iq_getter_va\":\"0x%" PRIxPTR "\",\"module_getter_va\":\"0x%" PRIxPTR
                       "\",\"descriptor_va\":\"0x%" PRIxPTR "\",\"type\":%u,"
                       "\"descriptor_word0\":%u,\"descriptor_word1\":%u,"
                       "\"descriptor_word2\":\"0x%08x\",\"descriptor_word3\":%u,"
                       "\"parent_register_id\":%u,\"parent_word1\":\"0x%08x\","
                       "\"parent_word2\":\"0x%08x\",\"group_num\":%u}\n",
                       g,j,param-bias,k,ids,id,pointer_at(param+16)-bias,pointer_at(param+32)-bias,
                       descriptor-bias,type,header,word_at(descriptor+4),word_at(descriptor+8),
                       word_at(descriptor+12),parent,word_at(parent_desc+4),
                       word_at(parent_desc+8),group_num);
            }
        }
    }
    uintptr_t extra_count_addr=pointer_at(bias+UINT64_C(0x59e158));
    uint32_t extra_count=word_at(extra_count_addr);
    /* This pinned CCM module has no extra non-vreg parameters. */
    if (extra_count!=0) return 6;
    printf("{\"event\":\"non_vreg_count\",\"count\":%u}\n",extra_count);
    _exit(0);
}
