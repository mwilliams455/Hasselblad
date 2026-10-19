/* SPDX-License-Identifier: MIT
 * Original bounded probe for the pinned X2D II CCM coefficient-preparation leaf.
 * It invokes original mm_get_coeff and mm_mx_lerp_gap, not a camera pipeline.
 * Optional input/output files live only in the runner's temporary directory.
 */
#define _GNU_SOURCE 1
#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include "ccm_prepare.h"

enum { PROFILES=8, STRIDE=96, VALUES=PROFILES*STRIDE };
typedef struct { uint32_t index; int32_t fraction_q8; } Coeff;
typedef uint64_t (*GetCoeff)(const int32_t *, uint64_t, int32_t);
typedef int32_t (*LerpGap)(const int32_t *, uint32_t, const Coeff *,
                           const uint32_t *, uint32_t);
static const int32_t cct_axis[4]={2400,3050,5550,9100};
static const int32_t ccts[]={2000,2400,3001,3050,4300,5550,7001,9100,10000};
static const int32_t weights[]={0,1,64,128,255,256};

static Coeff reference_coeff(int32_t value) {
    Coeff c={0,0};
    if (value<cct_axis[0]) return c;
    if (value>=cct_axis[3]) { c.index=2;c.fraction_q8=256;return c; }
    while (value>=cct_axis[c.index+1]) c.index++;
    c.fraction_q8=(value-cct_axis[c.index])*256/
                   (cct_axis[c.index+1]-cct_axis[c.index]);
    return c;
}
int main(int argc,char **argv) {
    if (argc!=2 && argc!=4) return 64;
    setvbuf(stdout,NULL,_IONBF,0);
    size_t page=(size_t)sysconf(_SC_PAGESIZE);
    if (page!=4096) return 65;
    uint8_t *map=mmap(NULL,page*3,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if (map==MAP_FAILED || mprotect(map+page,page,PROT_READ|PROT_WRITE)) return 66;
    /* One read-only page, with real guard pages and untouched padding. */
    memset(map+page,0xa7,page);
    int32_t *src=(int32_t *)(map+page+(page-VALUES*sizeof(int32_t))/2);
    if (argc==4) {
        FILE *f=fopen(argv[2],"rb");
        if (!f) return 67;
        size_t n=fread(src,sizeof(*src),VALUES,f);
        int extra=fgetc(f);
        fclose(f);
        if (n!=VALUES || extra!=EOF) return 68;
    } else {
        for (uint32_t p=0;p<PROFILES;p++)
            for (uint32_t k=0;k<STRIDE;k++)
                src[p*STRIDE+k]=(int32_t)((p*19073u+k*1297u+p*k*173u)%65001u)-32500;
    }
    for (uint32_t k=0;k<VALUES;k++) if (src[k]<-32768 || src[k]>32767) return 69;
    uint8_t before[4096];
    memcpy(before,map+page,page);
    if (mprotect(map+page,page,PROT_READ)) return 70;
    void *lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if (!lib) { fprintf(stderr,"dlopen: %s\n",dlerror());return 71; }
    void *anchor=dlsym(lib,"dcam_isp_vreg_get_type");
    Dl_info info;
    if (!anchor || !dladdr(anchor,&info) || !info.dli_fname ||
        strcmp(info.dli_fname,argv[1]) || info.dli_saddr!=anchor) return 72;
    uintptr_t bias=(uintptr_t)anchor-UINT64_C(0x54b88);
    GetCoeff get_coeff=(GetCoeff)(bias+UINT64_C(0x2bac00));
    LerpGap lerp_gap=(LerpGap)(bias+UINT64_C(0x2bb138));
    FILE *output=argc==4?fopen(argv[3],"wb"):NULL;
    if (argc==4 && !output) return 73;
    uint32_t count=0, failures=0;
    for (size_t c=0;c<sizeof(ccts)/sizeof(ccts[0]);c++) {
        uint64_t bits=get_coeff(cct_axis,4,ccts[c]);
        Coeff coeff={(uint32_t)bits,(int32_t)(bits>>32)};
        Coeff expected_coeff=reference_coeff(ccts[c]);
        if (coeff.index!=expected_coeff.index || coeff.fraction_q8!=expected_coeff.fraction_q8) return 74;
        for (size_t h=0;h<sizeof(weights)/sizeof(weights[0]);h++) {
            Coeff coordinates[2]={coeff,{0,weights[h]}};
            Coeff original_coordinates[2];memcpy(original_coordinates,coordinates,sizeof(coordinates));
            uint32_t products[2]={4,8};
            struct { uint64_t pre;int32_t values[STRIDE];uint64_t post; } result;
            result.pre=UINT64_C(0x3141592653589793);
            result.post=UINT64_C(0x2718281828459045);
            int32_t portable[STRIDE];
            if (hb_ccm_prepare(src,VALUES,ccts[c],weights[h],portable,STRIDE)!=HB_CCM_OK)
                return 78;
            uint32_t errors=0;
            for (uint32_t k=0;k<STRIDE;k++) {
                result.values[k]=lerp_gap(src+k,STRIDE,coordinates,products,2);
                if (result.values[k]!=portable[k]) errors++;
            }
            int inputs_ok=!memcmp(before,map+page,page) &&
                !memcmp(coordinates,original_coordinates,sizeof(coordinates)) &&
                products[0]==4 && products[1]==8;
            int guards_ok=result.pre==UINT64_C(0x3141592653589793) &&
                          result.post==UINT64_C(0x2718281828459045);
            if (output && fwrite(result.values,sizeof(int32_t),STRIDE,output)!=STRIDE) return 75;
            int pass=!errors && inputs_ok && guards_ok;
            printf("{\"case\":%u,\"cct\":%d,\"secondary_weight_q8\":%d,"
                   "\"cct_index\":%u,\"cct_fraction_q8\":%d,\"values\":%u,"
                   "\"mismatches\":%u,\"inputs_unchanged\":%s,\"guards_ok\":%s,\"pass\":%s}\n",
                   count++,ccts[c],weights[h],coeff.index,coeff.fraction_q8,STRIDE,
                   errors,inputs_ok?"true":"false",guards_ok?"true":"false",pass?"true":"false");
            failures+=!pass;
        }
    }
    if (output && fclose(output)) return 76;
    if (munmap(map,page*3)) return 77;
    return failures?1:0;
}
