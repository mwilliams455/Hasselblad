/* SPDX-License-Identifier: MIT */
/* Actual phone RAW+Domain1 C structs; no firmware calibration is in this test. */
#include "hb_phone_neutral_binding.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    hb_phone_raw_grid *raw=calloc(1,sizeof(*raw));
    hb_phone_domain_result *temperature=calloc(1,sizeof(*temperature));
    hb_ns_frame *frame=malloc(sizeof(*frame));
    hb_ns_domain *domain=malloc(sizeof(*domain));
    hb_ns_result *result=malloc(sizeof(*result));
    assert(raw && temperature && frame && domain && result);
    const double r=.2,g=.3,b=.15;
    const uint32_t rg=(uint32_t)(4096.0*g/r),bg=(uint32_t)(4096.0*g/b);
    for(unsigned i=0;i<1024;++i) {
        hb_phone_block *x=&raw->blocks[i];
        x->mean[0]=r;x->mean[1]=g;x->mean[2]=g;x->mean[3]=b;
        x->mean_brightness=(r+g+g+b)/4;
        x->red_gain_q12=rg;x->blue_gain_q12=bg;
    }
    raw->ratio_blocks=1024;
    temperature->schema_version=HB_PHONE_DOMAIN_SCHEMA;
    temperature->requested=(hb_phone_domain_request){2856,2856,1,0,0,1};
    temperature->kelvin_count=1;temperature->tint_count=1;
    temperature->point_count=1;temperature->representable=1;
    temperature->points[0].kelvin=2856;
    temperature->points[0].tint=0;
    temperature->points[0].exclusion=HB_PHONE_DOMAIN_REPRESENTABLE;
    temperature->points[0].gain_q12[0]=rg;
    temperature->points[0].gain_q12[1]=4096;
    temperature->points[0].gain_q12[2]=bg;
    hb_ns_capture_binding meta={123456789,24000000,50,1,1,1,HB_NS_BASIS_UNSHADED_SENSOR};
    memset(frame,0xA5,sizeof(*frame));memset(domain,0xA5,sizeof(*domain));
    assert(hb_phone_neutral_bind(raw,temperature,&meta,frame,domain)==HB_NS_BIND_OK);
    assert(frame->blocks[0].mean[1]==g && domain->points[0].red_gain_q12==rg);
    hb_ns_policy policy={128,128,16,.005,.9,.1};
    assert(hb_phone_neutral_observe(domain,frame,&policy,result)==HB_NS_OK);
    assert(result->near_valid_knot==1024 && result->render_permitted==0);
    assert(result->decision==HB_NS_ABSTAIN_UNCALIBRATED);
    /* Wrong physical source and inconsistent Domain1 exclusions reject
     * without mutating either output. */
    meta.physical_camera_and_result_frame_proven=0;
    memset(frame,0xA5,sizeof(*frame));memset(domain,0xA5,sizeof(*domain));
    assert(hb_phone_neutral_bind(raw,temperature,&meta,frame,domain)==HB_NS_BIND_UNPROVEN);
    const unsigned char *p=(const unsigned char*)frame,*q=(const unsigned char*)domain;
    for(size_t i=0;i<sizeof(*frame);++i)assert(p[i]==0xA5);
    for(size_t i=0;i<sizeof(*domain);++i)assert(q[i]==0xA5);
    meta.physical_camera_and_result_frame_proven=1;
    temperature->points[0].exclusion=HB_PHONE_DOMAIN_TEMPERATURE_CLIPPED;
    assert(hb_phone_neutral_bind(raw,temperature,&meta,frame,domain)==HB_NS_BIND_DOMAIN_INVALID);
    for(size_t i=0;i<sizeof(*frame);++i)assert(p[i]==0xA5);
    for(size_t i=0;i<sizeof(*domain);++i)assert(q[i]==0xA5);
    free(raw);free(temperature);free(frame);free(domain);free(result);
    return 0;
}
