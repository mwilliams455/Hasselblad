/* SPDX-License-Identifier: MIT */
#include "hb_phone_scene.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
_Static_assert(sizeof(hb_phone_scene_policy)==32,"policy ABI");
_Static_assert(sizeof(hb_phone_scene_result)==24636,"result ABI");
static void check(int ok) {if (!ok) {fprintf(stderr,"scene probe assertion failed\n");exit(3);}}
static void readfile(const char *name,void *data,size_t bytes) {
    FILE *f=fopen(name,"rb");check(f!=NULL);
    check(fread(data,bytes,1,f)==1 && fgetc(f)==EOF);check(fclose(f)==0);
}
int main(int argc,char **argv) {
    if (argc!=4) return 2;
    struct {hb_phone_temperature_input input;hb_phone_scene_policy policy;} request;
    _Static_assert(sizeof(request)==184,"request ABI");
    readfile(argv[1],&request,sizeof(request));
    hb_phone_raw_grid *grid=malloc(sizeof(*grid)),*bad=malloc(sizeof(*bad));
    hb_phone_scene_result *result=malloc(sizeof(*result)),*guard=malloc(sizeof(*guard));
    check(grid && bad && result && guard);readfile(argv[2],grid,sizeof(*grid));
    hb_phone_scene *s=NULL;check(hb_phone_scene_create(&request.input,&request.policy,&s)==0);
    check(hb_phone_scene_run(s,grid,result)==0);
    FILE *f=fopen(argv[3],"wb");check(f!=NULL);
    check(fwrite(result,sizeof(*result),1,f)==1);check(fclose(f)==0);
    unsigned checks=0;
    for (unsigned i=0;i<12;++i) {
        hb_phone_scene_policy p=request.policy;
        if (i==0) p.center_tint=NAN;
        if (i==1) p.center_tint=101;
        if (i==2) p.radius_q12=0;
        if (i==3) p.radius_q12=4097;
        if (i==4) p.neighbor_factor=0;
        if (i==5) p.neighbor_factor=256;
        if (i==6) p.minimum_blocks=0;
        if (i==7) p.minimum_blocks=5;
        if (i==8) p.minimum_blocks=1024;
        if (i==9) p.minimum_brightness=NAN;
        if (i==10) p.maximum_brightness=1.01;
        if (i==11) p.minimum_brightness=p.maximum_brightness;
        hb_phone_scene *out=s;
        check(hb_phone_scene_create(&request.input,&p,&out)==HB_PHONE_SCENE_POLICY && out==s);++checks;
    }
    unsigned good=1024;for (unsigned i=0;i<1024;++i) if (!grid->blocks[i].flags) {good=i;break;}
    for (unsigned i=0;i<3;++i) {
        *bad=*grid;
        if (i==0) bad->blocks[0].mean[0]=NAN;
        if (i==1) bad->blocks[0].flags=128;
        if (i==2) bad->blocks[0].mean_brightness+=1;
        memset(guard,0xa5,sizeof(*guard));
        check(hb_phone_scene_run(s,bad,guard)==HB_PHONE_SCENE_ARGUMENT);
        for (unsigned j=0;j<sizeof(*guard);++j) check(((unsigned char*)guard)[j]==0xa5);
        ++checks;
    }
    if (good<1024) {
        *bad=*grid;++bad->blocks[good].red_gain_q12;memset(guard,0xa5,sizeof(*guard));
        check(hb_phone_scene_run(s,bad,guard)==HB_PHONE_SCENE_ARGUMENT);
        for (unsigned j=0;j<sizeof(*guard);++j) check(((unsigned char*)guard)[j]==0xa5);
        ++checks;
    }
    /* A successful empty frame after a candidate MUST clear all selections. */
    memset(bad,0,sizeof(*bad));for (unsigned i=0;i<1024;++i) bad->blocks[i].flags=HB_PHONE_NONPOSITIVE;
    *guard=*result;check(hb_phone_scene_run(s,bad,guard)==0 && guard->decision==0);
    for (unsigned i=0;i<3;++i) check(guard->gain_q12[i]==0 && guard->neutral[i]==0);
    check(hb_phone_scene_run(s,grid,guard)==0 && memcmp(result,guard,sizeof(*guard))==0);
    hb_phone_scene_destroy(s);free(guard);free(result);free(bad);free(grid);
    fprintf(stderr,"scene probe: %u guards, no-result reset and deterministic replay passed\n",checks);
    return 0;
}
