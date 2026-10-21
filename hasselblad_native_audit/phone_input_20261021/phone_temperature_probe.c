/* SPDX-License-Identifier: MIT */
#include "hb_phone_temperature.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint32_t kelvin; float tint; uint32_t forward_status;
    hb_phone_temperature_gains gains; uint32_t inverse_status;
    hb_phone_temperature_estimate estimate; float matrix[9];
} record;
_Static_assert(sizeof(record)==76,"record ABI");
_Static_assert(sizeof(hb_phone_temperature_input)==152,"input ABI");
static void check(int ok) { if (!ok) { fprintf(stderr,"probe assertion failed\n");exit(3); } }

static unsigned guards(hb_phone_temperature *w,const hb_phone_temperature_input *input) {
    unsigned n=0;
    for (unsigned kind=0;kind<9;++kind) {
        hb_phone_temperature_input bad=*input;
        if (kind==0) bad.anchor[0].kelvin=0;
        if (kind==1) bad.anchor[1].kelvin=100001;
        if (kind==2) bad.anchor[0].kelvin=bad.anchor[1].kelvin;
        if (kind==3) bad.anchor[0].color[0]=NAN;
        if (kind==4) bad.anchor[1].calibration[0]=INFINITY;
        if (kind==5) memset(bad.anchor[0].color,0,36);
        if (kind==6) bad.anchor[0].calibration[0]=17;
        if (kind>=7) {
            /* Positive endpoint determinants, singular at t=.5 (kind7),
             * and at two non-grid fractions (kind8). */
            memset(&bad,0,sizeof(bad));bad.anchor[0].kelvin=2856;bad.anchor[1].kelvin=6504;
            for (unsigned k=0;k<2;++k) for (unsigned i=0;i<3;++i)
                bad.anchor[k].color[4*i]=bad.anchor[k].calibration[4*i]=1;
            bad.anchor[1].color[0]=kind==7?-1:-1.331f;
            bad.anchor[1].color[4]=kind==7?-1:-1.333f;
        }
        hb_phone_temperature *out=w;
        check(hb_phone_temperature_create(&bad,&out)!=0 && out==w);++n;
    }
    hb_phone_temperature *out=w;
    check(hb_phone_temperature_create(NULL,&out)==HB_PHONE_TEMP_ARGUMENT && out==w);++n;
    check(hb_phone_temperature_create(input,NULL)==HB_PHONE_TEMP_ARGUMENT);++n;
    const float bad_temp[]={0,1666,100001,NAN,INFINITY};
    for (unsigned i=0;i<5;++i) {
        float matrix[9],before[9];memset(matrix,0xa5,sizeof(matrix));memcpy(before,matrix,sizeof(matrix));
        check(hb_phone_temperature_matrix(w,bad_temp[i],matrix)==HB_PHONE_TEMP_RANGE &&
              memcmp(matrix,before,sizeof(matrix))==0);++n;
    }
    for (unsigned i=0;i<6;++i) {
        hb_phone_temperature_gains g,before;memset(&g,0xa5,sizeof(g));before=g;
        uint32_t ct=i==0?0:i==1?1666:i==2?100001:5000;
        float tint=i==3?NAN:i==4?INFINITY:i==5?151:0;
        check(hb_phone_temperature_to_gain(w,ct,tint,&g)==HB_PHONE_TEMP_RANGE &&
              memcmp(&g,&before,sizeof(g))==0);++n;
    }
    const uint32_t invalid[][3]={{0,4096,4096},{4096,65536,4096},{1,10,1},{65535,4096,4096}};
    for (unsigned i=0;i<4;++i) {
        hb_phone_temperature_estimate e,before;memset(&e,0xa5,sizeof(e));before=e;
        check(hb_phone_temperature_from_gain(w,invalid[i],&e)!=0 &&
              memcmp(&e,&before,sizeof(e))==0);++n;
    }
    return n;
}

int main(int argc,char **argv) {
    if (argc!=3) return 2;
    FILE *f=fopen(argv[1],"rb"); if (!f) return 2;
    hb_phone_temperature_input input;uint32_t hal_gain[3];
    check(fread(&input,sizeof(input),1,f)==1 && fread(hal_gain,sizeof(hal_gain),1,f)==1 && fgetc(f)==EOF);
    fclose(f);hb_phone_temperature *w=NULL;
    check(hb_phone_temperature_create(&input,&w)==0);
    uint32_t header[3]={1,243,guards(w,&input)};
    f=fopen(argv[2],"wb");if (!f) { hb_phone_temperature_destroy(w);return 2; }
    check(fwrite(header,sizeof(header),1,f)==1);
    for (int tint=-25;tint<=25;tint+=25) for (unsigned ct=2000;ct<=10000;ct+=100) {
        record r;memset(&r,0,sizeof(r));r.kelvin=ct;r.tint=(float)tint;
        check(hb_phone_temperature_matrix(w,(float)ct,r.matrix)==0);
        r.forward_status=(uint32_t)hb_phone_temperature_to_gain(w,ct,(float)tint,&r.gains);
        r.inverse_status=r.forward_status?UINT32_MAX:
            (uint32_t)hb_phone_temperature_from_gain(w,r.gains.gain_q12,&r.estimate);
        check(fwrite(&r,sizeof(r),1,f)==1);
    }
    hb_phone_temperature_estimate hal={0,0,0};
    uint32_t st=(uint32_t)hb_phone_temperature_from_gain(w,hal_gain,&hal);
    check(fwrite(&st,sizeof(st),1,f)==1 && fwrite(&hal,sizeof(hal),1,f)==1);
    check(fclose(f)==0);hb_phone_temperature_destroy(w);
    fprintf(stderr,"temperature probe: 243 samples, %u guard cases\n",header[2]);return 0;
}
