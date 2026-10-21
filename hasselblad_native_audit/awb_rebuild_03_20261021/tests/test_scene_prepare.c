/* Checkpoint03 host tests: bounded arithmetic, AE evidence, external replay. */
#include "hb_awb_scene_prepare.h"
#include <stdint.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint64_t checks=0;
#define MUST(X) do {++checks;if(!(X)){fprintf(stderr,"FAIL line=%d expr=%s\n",__LINE__,#X);exit(1);}}while(0)
static uint32_t rng=0x290AC607u;
static uint32_t rnd(void){rng ^=rng <<13; rng ^=rng >>17; rng ^=rng <<5;return rng;}
static hb_awb_frame_stats *sample(void){
    hb_awb_frame_stats *s=calloc(1,sizeof(*s)); MUST(s!=NULL);
    for(unsigned i=0;i<HB_AWB_FRAME_BLOCKS;++i){
        hb_awb_stat_block *b=&s->blocks[i];
        b->sample_count=4;
        b->min_sample=40;b->max_sample=1100;
        b->site_count[0]=b->site_count[1]=b->site_count[2]=b->site_count[3]=1;
        b->site_sum_q16[0]=-(int64_t)65537-(int64_t)i;
        b->site_sum_q16[1]=INT64_C(124550)+(int64_t)i;
        b->site_sum_q16[2]=INT64_C(173231)-(int64_t)i;
        b->site_sum_q16[3]=INT64_C(140250)+(int64_t)i;
        for(unsigned j=0;j<4;++j)b->raw_brightness_sum_q16+=b->site_sum_q16[j];
        b->at_or_above_white_count=i%7==0;
        b->above_white_count=b->at_or_above_white_count;
        b->at_or_below_black_count=i%11==0;
    }
    s->input_sample_count=4096;
    return s;
}
static hb_awb_explicit_calibration calib(void){
    hb_awb_explicit_calibration c={0};
    c.channel_gain_q16[0]=2*65536+17;
    c.channel_gain_q16[1]=65536;
    c.channel_gain_q16[2]=65536+111;
    c.channel_gain_q16[3]=32768;
    c.channel_bias_q16[0]=-141;
    c.channel_bias_q16[1]=100;
    return c;
}
/* Inputs to tests are safely bounded so direct 64-bit multiplication gives an
 * independent arithmetic reference. Production code uses checked operations. */
static int64_t oracle(int64_t v,uint32_t k){return v*(int64_t)k/65536;}
static void test_calibration(void){
    hb_awb_frame_stats *s=sample();
    hb_awb_frame_stats *out=calloc(1,sizeof(*out));MUST(out!=NULL);
    hb_awb_explicit_calibration c=calib();
    uint32_t *spatial=malloc(sizeof(uint32_t)*1024);MUST(spatial!=NULL);
    for(unsigned i=0;i<1024;++i)spatial[i]=(i%5==0)?32769:65536;
    c.spatial_gain_q16=spatial;
    MUST(hb_awb_apply_explicit_calibration(s,&c,out)==0);
    MUST(!out->vendor_e2_equivalence_proven);
    MUST(s->blocks[0].site_sum_q16[0]==-65537);
    for(unsigned i=0;i<1024;++i){
        MUST(out->blocks[i].raw_brightness_sum_q16==s->blocks[i].raw_brightness_sum_q16);
        MUST(out->blocks[i].sample_count==s->blocks[i].sample_count);
        MUST(out->blocks[i].min_sample==s->blocks[i].min_sample);
        for(unsigned j=0;j<4;++j){
            int64_t expect=oracle(oracle(s->blocks[i].site_sum_q16[j],c.channel_gain_q16[j]),
                                  spatial[i])+c.channel_bias_q16[j];
            MUST(out->blocks[i].site_sum_q16[j]==expect);
            MUST(out->blocks[i].site_count[j]==1);
        }
    }
    /* In-place conversion is allowed and yields bit-identical output. */
    hb_awb_frame_stats *alias=malloc(sizeof(*alias));MUST(alias!=NULL);*alias=*s;
    MUST(hb_awb_apply_explicit_calibration(alias,&c,alias)==0);
    MUST(memcmp(alias,out,sizeof(*out))==0);
    /* No output mutation if a stage fails, including overflow and invalid gain. */
    hb_awb_frame_stats *backup=malloc(sizeof(*backup));MUST(backup!=NULL);*backup=*out;
    c.channel_gain_q16[2]=HB_AWB_GAIN_Q16_MAX+1;
    MUST(hb_awb_apply_explicit_calibration(s,&c,out)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(out,backup,sizeof(*out))==0);
    c.channel_gain_q16[2]=65536+111;
    s->blocks[0].site_sum_q16[0]=INT64_MIN;
    MUST(hb_awb_apply_explicit_calibration(s,&c,out)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(out,backup,sizeof(*out))==0);
    s->blocks[0].site_sum_q16[0]=-65537;
    c.channel_bias_q16[1]=HB_AWB_BIAS_Q16_MAX+1;
    MUST(hb_awb_apply_explicit_calibration(s,&c,out)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(out,backup,sizeof(*out))==0);
    free(backup);free(alias);free(spatial);free(out);free(s);
}
static void test_ae(void){
    hb_awb_frame_stats *s=sample();
    hb_awb_ae_evidence *ae=malloc(sizeof(*ae));MUST(ae!=NULL);
    MUST(hb_awb_prepare_raw_ae_evidence(s,ae)==0);
    MUST(!ae->vendor_ae_equivalence_proven);
    MUST(ae->total_samples==4096);
    int64_t expect=0;
    uint64_t atw=0,low=0;
    for(unsigned i=0;i<1024;++i){
        const hb_awb_stat_block *b=&s->blocks[i];
        expect+=b->raw_brightness_sum_q16;
        atw+=b->at_or_above_white_count;low+=b->at_or_below_black_count;
        MUST(ae->raw_block_mean_q16[i]==b->raw_brightness_sum_q16/4);
        MUST(ae->at_or_above_white_ppm[i]==b->at_or_above_white_count*250000);
        MUST(ae->at_or_below_black_ppm[i]==b->at_or_below_black_count*250000);
    }
    MUST(ae->total_raw_sum_q16==expect && ae->frame_raw_mean_q16==expect/4096);
    MUST(ae->total_at_or_above_white==atw && ae->total_at_or_below_black==low);
    hb_awb_ae_evidence prev=*ae;
    s->blocks[12].at_or_below_black_count=5;
    MUST(hb_awb_prepare_raw_ae_evidence(s,ae)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(ae,&prev,sizeof(*ae))==0);
    s->blocks[12].at_or_below_black_count=0;
    s->input_sample_count=0;
    MUST(hb_awb_prepare_raw_ae_evidence(s,ae)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(ae,&prev,sizeof(*ae))==0);
    free(ae);free(s);
}
static void test_scene(void){
    hb_awb_frame_stats *s=sample();
    hb_awb_scene_prepare_result *r=calloc(1,sizeof(*r));MUST(r!=NULL);
    hb_awb_replay_masks *m=calloc(1,sizeof(*m));MUST(m!=NULL);
    hb_awb_explicit_calibration c=calib();
    m->neighbours=HB_AWB_NEIGHBORS_FOUR;
    unsigned ix[]={0,1,32,33,1023};
    for(unsigned j=0;j<5;++j)m->final_weight[ix[j]]=(uint8_t)(j+1);
    m->classifier_accepted[0]=1;m->classifier_accepted[1]=1;m->classifier_accepted[1023]=1;
    m->zone_override[32]=1;m->zone_override[33]=1;
    MUST(hb_awb_scene_prepare_bounded(s,&c,m,r)==0);
    MUST(!r->vendor_calibration_equivalence_proven && !r->vendor_classification_equivalence_proven);
    MUST(!r->produces_selected_neutral);
    MUST(r->accumulation.surviving_blocks==4);
    MUST(r->weighted_from_zone_not_classifier==2);
    MUST(r->weighted_from_classifier==2);
    MUST(r->weighted_with_both_origins==0);
    MUST(r->accumulation.weighted_but_unclassified_blocks==2);
    MUST(r->accumulation.filter.blocks_removed==1);
    int64_t calibrated_r=0, raw_brightness=0;
    for(unsigned i=0;i<4;++i){
        unsigned index=ix[i],w=m->final_weight[index];
        calibrated_r+=r->calibrated.blocks[index].site_sum_q16[0]*w;
        raw_brightness+=s->blocks[index].raw_brightness_sum_q16*w;
    }
    MUST(r->accumulation.weighted_site_sum_q16[0]==calibrated_r);
    MUST(r->accumulation.weighted_raw_brightness_q16==raw_brightness);
    /* Explicit negative contract: mysterious unclassified non-zone weights
       are NOT silently accepted or labelled vendor-derived. */
    hb_awb_scene_prepare_result *prev=malloc(sizeof(*prev));MUST(prev!=NULL);*prev=*r;
    m->zone_override[32]=0;
    MUST(hb_awb_scene_prepare_bounded(s,&c,m,r)==HB_AWB_REBUILD_UNSUPPORTED);
    MUST(memcmp(r,prev,sizeof(*r))==0);
    m->zone_override[32]=1;m->final_weight[33]=255;
    MUST(hb_awb_scene_prepare_bounded(s,&c,m,r)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(r,prev,sizeof(*r))==0);
    m->final_weight[33]=4;
    m->classifier_accepted[33]=2;
    MUST(hb_awb_scene_prepare_bounded(s,&c,m,r)==HB_AWB_REBUILD_BAD_INPUT);
    MUST(memcmp(r,prev,sizeof(*r))==0);
    m->classifier_accepted[33]=0;
    MUST(hb_awb_scene_prepare_bounded(s,&c,m,r)==0);
    free(prev);free(m);free(r);free(s);
}
static void test_random(void){
    hb_awb_frame_stats *s=sample();
    hb_awb_frame_stats *out=malloc(sizeof(*out));MUST(out!=NULL);
    hb_awb_explicit_calibration c={0};
    uint32_t *spatial=malloc(sizeof(uint32_t)*1024);MUST(spatial!=NULL);
    c.spatial_gain_q16=spatial;
    for(unsigned t=0;t<192;++t){
        for(unsigned j=0;j<4;++j){
            c.channel_gain_q16[j]=rnd()%(4*65536+1);
            c.channel_bias_q16[j]=(int32_t)(rnd()%131073)-65536;
        }
        for(unsigned i=0;i<1024;++i){
            spatial[i]=rnd()%(4*65536+1);
            hb_awb_stat_block *b=&s->blocks[i];
            for(unsigned j=0;j<4;++j)b->site_sum_q16[j]=(int32_t)(rnd()%80000001)-40000000;
        }
        MUST(hb_awb_apply_explicit_calibration(s,&c,out)==0);
        for(unsigned i=0;i<1024;++i){
            const hb_awb_stat_block *b=&s->blocks[i];
            for(unsigned j=0;j<4;++j){
                int64_t want=oracle(oracle(b->site_sum_q16[j],c.channel_gain_q16[j]),spatial[i])+
                                  c.channel_bias_q16[j];
                MUST(out->blocks[i].site_sum_q16[j]==want);
            }
        }
    }
    free(spatial);free(out);free(s);
}
int main(void){
    test_calibration();test_ae();test_scene();test_random();
    printf("{\"result\":\"PASS\",\"checks\":%" PRIu64 ",\"vendor_compared\":false,\"scope\":\"owned explicit calibration/AE evidence/replay\"}\n",checks);
    return 0;
}