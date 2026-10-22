/* SPDX-License-Identifier: MIT */
#include "hb_phone_neutral_observation.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static void sample(hb_ns_block *b,double red,double green,double blue) {
    b->mean[0]=red;b->mean[1]=green;b->mean[2]=green;b->mean[3]=blue;
    b->mean_brightness=(red+green+green+blue)*0.25;
    b->red_gain_q12=(uint32_t)(4096.0*green/red);
    b->blue_gain_q12=(uint32_t)(4096.0*green/blue);
    b->raw_flags=0;
}
int main(void) {
    hb_ns_frame *f=calloc(1,sizeof(*f));
    hb_ns_domain *d=calloc(1,sizeof(*d));
    hb_ns_result *o=malloc(sizeof(*o));
    assert(f && d && o);
    f->sensor_timestamp_ns=123456789;f->exposure_time_ns=24000000;f->ISO=50;
    f->bound_to_physical_sensor_and_frame=1;
    f->original_single_raw_proven=1;
    f->basis=HB_NS_BASIS_UNSHADED_SENSOR;
    for(unsigned i=0;i<1024;++i)sample(&f->blocks[i],.2,.3,.15);
    d->schema=HB_NS_SCHEMA;d->count=3;
    d->points[0]=(hb_ns_knot){2856,0,f->blocks[0].red_gain_q12,f->blocks[0].blue_gain_q12,0};
    d->points[1]=(hb_ns_knot){3000,0,0,0,1};
    d->points[2]=(hb_ns_knot){6504,50,9000,5000,0};
    hb_ns_policy p={128,128,16,.005,.9,.1};
    memset(o,0xA5,sizeof(*o));
    assert(hb_phone_neutral_observe(d,f,&p,o)==HB_NS_OK);
    assert(o->decision==HB_NS_ABSTAIN_UNCALIBRATED);
    assert(o->evaluated_blocks==1024 && o->near_valid_knot==1024);
    assert(o->spatial_components==1 && o->largest_spatial_component==1024);
    assert(o->render_permitted==0 && o->calibrated_policy==0);
    assert(o->usable_domain_points==2 && o->excluded_domain_points==1);
    assert(o->near_quadrants_bitmask==15);
    for(unsigned i=0;i<1024;++i) {
        assert(o->blocks[i].nearest_knot_index==0);
        assert(o->blocks[i].distance_q12==0);
        assert(o->blocks[i].component_index==0);
    }
    /* Skip every block, but keep a deterministic success with abstention. */
    for(unsigned i=0;i<1024;++i) {
        sample(&f->blocks[i],.2,.3,.15);
        f->blocks[i].raw_flags=1;
        f->blocks[i].red_gain_q12=f->blocks[i].blue_gain_q12=0;
    }
    assert(hb_phone_neutral_observe(d,f,&p,o)==HB_NS_OK);
    assert(o->raw_rejected==1024 && o->near_valid_knot==0);
    assert(o->decision==HB_NS_ABSTAIN_NO_CANDIDATE_SUPPORT);
    /* Cross-row wrap is deliberately NOT valid 8-neighbour connectivity. */
    sample(&f->blocks[31],.2,.3,.15);
    sample(&f->blocks[32],.2,.3,.15);
    p.minimum_support_blocks=4;
    assert(hb_phone_neutral_observe(d,f,&p,o)==HB_NS_OK);
    assert(o->spatial_components==2 && o->largest_spatial_component==1);
    assert(o->decision==HB_NS_ABSTAIN_NO_CANDIDATE_SUPPORT);
    /* No mutation on metadata failures and invalid masked knots. */
    memset(o,0x4A,sizeof(*o));
    f->bound_to_physical_sensor_and_frame=0;
    assert(hb_phone_neutral_observe(d,f,&p,o)==HB_NS_FRAME_UNPROVEN);
    const unsigned char *bytes=(const unsigned char*)o;
    for(size_t i=0;i<sizeof(*o);++i)assert(bytes[i]==0x4A);
    f->bound_to_physical_sensor_and_frame=1;
    d->points[1].red_gain_q12=1;
    assert(hb_phone_neutral_observe(d,f,&p,o)==HB_NS_DOMAIN_INVALID);
    for(size_t i=0;i<sizeof(*o);++i)assert(bytes[i]==0x4A);
    d->points[1].red_gain_q12=0;
    p.maximum_brightness=.004;
    assert(hb_phone_neutral_observe(d,f,&p,o)==HB_NS_POLICY_INVALID);
    for(size_t i=0;i<sizeof(*o);++i)assert(bytes[i]==0x4A);
    free(o);free(d);free(f);
    return 0;
}
