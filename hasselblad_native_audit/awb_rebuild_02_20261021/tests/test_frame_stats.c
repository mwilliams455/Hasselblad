/* Rebuild 02: synthetic host contract checks (NOT vendor E2 checks). */
#include "hb_awb_frame_stats.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <limits.h>
static uint32_t checks;
#define REQ(x) do{++checks;if(!(x)){fprintf(stderr,"FAIL: line %d : %s\n",__LINE__,#x);exit(1);}}while(0)
static uint32_t rng=0xA7BEFEED;
static uint32_t rnd(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void write_code(uint8_t *buf,const hb_awb_frame_input *f,uint32_t x,uint32_t y,uint16_t code) {
    uint8_t *p=buf+(size_t)y*f->row_stride_bytes+(size_t)x*f->pixel_stride_bytes;
    p[0]=(uint8_t)code; p[1]=(uint8_t)(code>>8);
}
static hb_awb_frame_input frame(uint32_t w,uint32_t h,uint32_t pitch,uint32_t stride) {
    hb_awb_frame_input f={0};
    f.width=w;f.height=h;f.row_stride_bytes=pitch;f.pixel_stride_bytes=stride;
    f.right=w;f.bottom=h;f.cfa=HB_AWB_RGGB;f.white_code=1023;
    for(unsigned i=0;i<4;++i) f.black_q16[i]=64*HB_AWB_Q16_ONE;
    return f;
}
static void sum_blocks(const hb_awb_frame_stats *s,int64_t sums[4],uint64_t counts[4],
                       uint64_t *bright,uint64_t *atwhite) {
    *bright=*atwhite=0;
    for(unsigned c=0;c<4;++c){sums[c]=0;counts[c]=0;}
    for(unsigned i=0;i<1024;++i) {
        const hb_awb_stat_block *b=&s->blocks[i];
        for(unsigned c=0;c<4;++c){sums[c]+=b->site_sum_q16[c];counts[c]+=b->site_count[c];}
        *bright+=b->sample_count;
        *atwhite+=b->at_or_above_white_count;
        REQ(b->sample_count>=4);
        REQ(b->sample_count==b->site_count[0]+b->site_count[1]+b->site_count[2]+b->site_count[3]);
        REQ(b->raw_brightness_sum_q16==b->site_sum_q16[0]+b->site_sum_q16[1]+b->site_sum_q16[2]+b->site_sum_q16[3]);
    }
}
static void test_streams(void){
    hb_awb_frame_stats *a=malloc(sizeof *a);REQ(a!=NULL);
    hb_awb_frame_input f=frame(64,64,64*6+19,6);
    size_t len=(size_t)f.row_stride_bytes*f.height;
    uint8_t *raw=calloc(len,1);REQ(raw!=NULL);
    for(int pat=0;pat<4;++pat){
        f.cfa=(enum hb_awb_cfa)pat;
        for(uint32_t y=0;y<f.height;++y)
            for(uint32_t x=0;x<f.width;++x) {
                uint16_t v=(uint16_t)(100+(x&1u)*10+(y&1u)*20);
                write_code(raw,&f,x,y,v);
            }
        REQ(hb_awb_raw_to_block_stats(raw,len,&f,a)==0);
        REQ(a->input_sample_count==4096 && !a->vendor_e2_equivalence_proven);
        int64_t sums[4];uint64_t counts[4],samples,saturated;
        sum_blocks(a,sums,counts,&samples,&saturated);
        REQ(samples==4096 && saturated==0);
        for(int c=0;c<4;++c)REQ(counts[c]==1024);
        /* Top-left colour for each 2x2 location per Bayer pattern. */
        static const unsigned colourmap[4][4]={{0,1,2,3},{1,0,3,2},{2,3,0,1},{3,2,1,0}};
        for(unsigned k=0;k<4;++k){
            const uint32_t code=100+(k&1u)*10+(k/2)*20;
            REQ(sums[colourmap[pat][k]]==(int64_t)(code-64)*HB_AWB_Q16_ONE*1024);
        }
    }
    /* Backed-up source identity: original RAW doesn't get normalized/clipped. */
    f=frame(64,64,64*2,2);f.black_q16[0]=63*HB_AWB_Q16_ONE+HB_AWB_Q16_ONE*15/16;
    uint8_t *s=calloc(f.row_stride_bytes*f.height,1);REQ(s!=NULL);
    for(unsigned y=0;y<64;++y)for(unsigned x=0;x<64;++x)
        write_code(s,&f,x,y,(uint16_t)(x==0 && y==0 ? 65535 : 63));
    REQ(hb_awb_raw_to_block_stats(s,(size_t)f.row_stride_bytes*f.height,&f,a)==0);
    const hb_awb_stat_block *b=&a->blocks[0];
    REQ(b->min_sample==63 && b->max_sample==65535 && b->above_white_count==1);
    REQ(b->site_sum_q16[0]==((int64_t)65535*HB_AWB_Q16_ONE-f.black_q16[0]));
    REQ(b->raw_brightness_sum_q16>0);
    REQ(b->at_or_below_black_count==3);
    REQ(a->blocks[1].site_sum_q16[0]==(int64_t)(63*HB_AWB_Q16_ONE-f.black_q16[0]));
    free(s);
    /* Non-zero even crop origin must retain original Bayer phase and Q16 black. */
    f=frame(134,136,134*4+2,4);f.left=2;f.top=4;f.right=132;f.bottom=134;
    uint8_t *large=calloc(f.row_stride_bytes*f.height,1);REQ(large!=NULL);
    for(unsigned y=0;y<f.height;++y)for(unsigned x=0;x<f.width;++x)
        write_code(large,&f,x,y,(uint16_t)(80+(x&1)*10+(y&1)*20));
    REQ(hb_awb_raw_to_block_stats(large,(size_t)f.row_stride_bytes*f.height,&f,a)==0);
    REQ(a->input_sample_count==130u*130u);
    int64_t sums[4];uint64_t counts[4],pixels,sat;
    sum_blocks(a,sums,counts,&pixels,&sat);
    REQ(pixels==130u*130u);
    for(int c=0;c<4;++c)REQ(counts[c]==65u*65u);
    free(large);free(raw);free(a);
}
static void test_validation(void){
    hb_awb_frame_stats *a=malloc(sizeof *a);REQ(a!=NULL);
    hb_awb_frame_input f=frame(64,64,128,2);
    uint8_t *buf=calloc(8192,1);REQ(buf!=NULL);
    REQ(hb_awb_raw_to_block_stats(NULL,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    REQ(hb_awb_raw_to_block_stats(buf,8192,NULL,a)==HB_AWB_REBUILD_BAD_INPUT);
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,NULL)==HB_AWB_REBUILD_BAD_INPUT);
    REQ(hb_awb_raw_to_block_stats(buf,8191,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.white_code=0;REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.white_code=1023;f.cfa=(enum hb_awb_cfa)4;
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.cfa=HB_AWB_RGGB;f.left=1;
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.left=0;f.pixel_stride_bytes=3;
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.pixel_stride_bytes=2;f.black_q16[0]=-1;
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.black_q16[0]=0;f.right=62;
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    f.right=64;f.width=70;
    REQ(hb_awb_raw_to_block_stats(buf,8192,&f,a)==HB_AWB_REBUILD_BAD_INPUT);
    free(buf);free(a);
}
static void test_accumulation(void){
    hb_awb_frame_stats *a=calloc(1,sizeof *a); REQ(a!=NULL);
    uint8_t *weights=calloc(1024,1);REQ(weights!=NULL);
    uint8_t *accepted=calloc(1024,1);REQ(accepted!=NULL);
    hb_awb_scene_accumulation r;
    /* Four connected weighted blocks survive. One standalone block is pruned.
     * Three of four retained blocks are classifier rejected: classification
     * mask cannot override precomputed weights. No vendor weight policy used. */
    weights[0]=1;weights[1]=2;weights[32]=3;weights[33]=4;weights[1000]=1;
    accepted[0]=1;
    for(unsigned i=0;i<1024;++i){
        for(unsigned c=0;c<4;++c){a->blocks[i].site_sum_q16[c]=(int64_t)(c+1)*1000;
            a->blocks[i].site_count[c]=1;}
        a->blocks[i].sample_count=4;
        a->blocks[i].at_or_above_white_count=1;
        a->blocks[i].raw_brightness_sum_q16=10000;
    }
    REQ(hb_awb_accumulate_owned_candidates(a,weights,accepted,HB_AWB_NEIGHBORS_FOUR,&r)==0);
    REQ(r.surviving_blocks==4 && r.weighted_but_unclassified_blocks==3);
    REQ(r.filter.blocks_removed==1 && r.filter.blocks_kept==4);
    REQ(r.weighted_sample_count==4u*(1u+2u+3u+4u));
    REQ(r.weighted_raw_brightness_q16==10000*(1+2+3+4));
    REQ(r.weighted_site_sum_q16[0]==1000*(1+2+3+4));
    REQ(r.weighted_site_sum_q16[3]==4000*(1+2+3+4));
    REQ(!r.vendor_candidate_equivalence_proven);
    weights[0]=33;
    hb_awb_scene_accumulation before=r;
    REQ(hb_awb_accumulate_owned_candidates(a,weights,accepted,HB_AWB_NEIGHBORS_FOUR,&r)==HB_AWB_REBUILD_BAD_INPUT);
    REQ(memcmp(&r,&before,sizeof r)==0);
    weights[0]=1;
    a->blocks[0].site_sum_q16[0]=INT64_MAX;
    REQ(hb_awb_accumulate_owned_candidates(a,weights,accepted,HB_AWB_NEIGHBORS_FOUR,&r)==HB_AWB_REBUILD_BAD_INPUT);
    REQ(memcmp(&r,&before,sizeof r)==0);
    free(accepted);free(weights);free(a);
}
static void test_random_conservation(void) {
    hb_awb_frame_stats *a=malloc(sizeof *a);REQ(a!=NULL);
    const uint32_t cases[][2]={{64,64},{66,72},{128,74},{408,288},{104,100},{256,192}};
    for(unsigned t=0;t<sizeof(cases)/sizeof(*cases);++t){
        hb_awb_frame_input f=frame(cases[t][0],cases[t][1],cases[t][0]*2+4,2);
        size_t sz=(size_t)f.row_stride_bytes*f.height;
        uint8_t *raw=malloc(sz);REQ(raw!=NULL);memset(raw,0,sz);
        int64_t expected[4]={0};uint64_t cnts[4]={0};uint32_t below=0,above=0;
        for(uint32_t y=0;y<f.height;++y)for(uint32_t x=0;x<f.width;++x){
            uint16_t code=(uint16_t)(rnd()%1300);
            write_code(raw,&f,x,y,code);
            unsigned colour=(y&1u)*2u+(x&1u);
            expected[colour]+=(int64_t)(code-64)*HB_AWB_Q16_ONE;
            ++cnts[colour];below+=(code<=64);above+=(code>=1023);
        }
        REQ(hb_awb_raw_to_block_stats(raw,sz,&f,a)==0);
        int64_t sums[4];uint64_t counts[4],pixels,abv;
        sum_blocks(a,sums,counts,&pixels,&abv);
        REQ(pixels==(uint64_t)f.width*f.height);
        REQ(abv==above);
        for(unsigned c=0;c<4;++c){REQ(sums[c]==expected[c]);REQ(counts[c]==cnts[c]);}
        uint32_t belowactual=0;
        for(unsigned i=0;i<1024;++i) belowactual+=a->blocks[i].at_or_below_black_count;
        REQ(belowactual==below);
        free(raw);
    }
    free(a);
}
int main(void){
    test_streams();test_validation();test_accumulation();test_random_conservation();
    printf("{\"result\":\"PASS\",\"checks\":%" PRIu32 ",\"vendor_compared\":false,\"scope\":\"owned 1024 block RAW stats and weighted accumulation\"}\n",checks);
}