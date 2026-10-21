/* SPDX-License-Identifier: MIT */
#include "hb_awb_stages.h"
#include "hb_awb_recalib.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks=0;
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"FAILED %s:%d: %s\n", __FILE__,__LINE__, #x); exit(2); } checks++; } while(0)
static uint32_t seed=0x20261021u;
static uint32_t rnd(void) { seed^=seed<<13; seed^=seed>>17; seed^=seed<<5; return seed; }
static void set32(uint8_t *p, uint32_t n) { for(unsigned i=0;i<4;++i) p[i]=(uint8_t)(n>>(i*8)); }
static void fill(uint8_t *p,size_t n) { for(size_t i=0;i<n;++i) p[i]=(uint8_t)rnd(); }
static void oracle_context(uint8_t *buf,int prior,int copy_status,unsigned request) {
    /* An independent byte-index oracle with explicit two result pairs. */
    for (unsigned i=0;i<4;i++) buf[HB_AWB_CLEAR_OFFSET+i]=0;
    if (request==1) {
        uint8_t temp[HB_AWB_RESULT_BYTES];
        memcpy(temp,buf+HB_AWB_REFERENCE_RESULT_OFFSET,sizeof temp);
        const size_t offsets[4]={HB_AWB_LIVE_A_OFFSET,HB_AWB_LIVE_B_OFFSET,
                                 HB_AWB_CONFIRMED_A_OFFSET,HB_AWB_CONFIRMED_B_OFFSET};
        for(unsigned i=0;i<4;i++) memcpy(buf+offsets[i],temp,sizeof temp);
        buf[HB_AWB_REFERENCE_REQUEST_OFFSET]=0;
    } else {
        const size_t from[2]={prior ? HB_AWB_CONFIRMED_A_OFFSET : HB_AWB_LIVE_A_OFFSET,
                              prior ? HB_AWB_CONFIRMED_B_OFFSET : HB_AWB_LIVE_B_OFFSET};
        const size_t to[2]={prior ? HB_AWB_LIVE_A_OFFSET : HB_AWB_CONFIRMED_A_OFFSET,
                            prior ? HB_AWB_LIVE_B_OFFSET : HB_AWB_CONFIRMED_B_OFFSET};
        for(unsigned i=0;i<2;i++) memcpy(buf+to[i],buf+from[i],HB_AWB_RESULT_BYTES);
    }
    (void)copy_status;
}
static void test_outer(void) {
    uint8_t *raw=malloc(HB_AWB_CONTEXT_BYTES),*expect=malloc(HB_AWB_CONTEXT_BYTES);
    REQUIRE(raw!=NULL && expect!=NULL);
    hb_awb_completion o;
    REQUIRE(hb_awb_outer_complete_bounded(NULL,HB_AWB_CONTEXT_BYTES,0,0,&o)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(hb_awb_outer_complete_bounded(raw,HB_AWB_CONTEXT_BYTES-1,0,0,&o)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(hb_awb_outer_complete_bounded(raw,HB_AWB_CONTEXT_BYTES,0,0,NULL)==HB_AWB_REBUILD_BAD_INPUT);
    for(int n=0;n<240;++n) {
        fill(raw,HB_AWB_CONTEXT_BYTES);
        int prior=(n%5==0?0:n%5==1?40:n%5==2?151:n%5==3?-1:128);
        int helper=(n%11==0?73:0);
        unsigned req=(unsigned)(n%4==0?1:n%4==1?0:n%4==2?2:255);
        raw[HB_AWB_REFERENCE_REQUEST_OFFSET]=(uint8_t)req;
        memcpy(expect,raw,HB_AWB_CONTEXT_BYTES);
        oracle_context(expect,prior,helper,req);
        REQUIRE(hb_awb_outer_complete_bounded(raw,HB_AWB_CONTEXT_BYTES,prior,helper,&o)==HB_AWB_REBUILD_OK);
        REQUIRE(!memcmp(raw,expect,HB_AWB_CONTEXT_BYTES));
        REQUIRE(o.preceding_status==prior && o.final_copy_status==helper && o.outer_status==helper);
        REQUIRE(o.fresh_estimate_proven==0);
        REQUIRE(o.reference_request_consumed==(req==1));
        REQUIRE(o.origin==(req==1?HB_AWB_ORIGIN_REFERENCE_OVERRIDE:prior?HB_AWB_ORIGIN_RESTORED_CONFIRMED:HB_AWB_ORIGIN_LIVE_PUBLISHED));
    }
    /* Both historically documented recovery witnesses must return outer zero
     * while retaining a *restored* and non-fresh result. */
    for(int i=0;i<2;++i) {
        fill(raw,HB_AWB_CONTEXT_BYTES); raw[HB_AWB_REFERENCE_REQUEST_OFFSET]=0;
        hb_awb_scene_entry no_eligible={0,0};
        int prior=i?151:40;
        REQUIRE(hb_awb_outer_complete_bounded(raw,HB_AWB_CONTEXT_BYTES,prior,0,&o)==0);
        REQUIRE(o.outer_status==0 && o.origin==HB_AWB_ORIGIN_RESTORED_CONFIRMED);
        fill(raw,HB_AWB_CONTEXT_BYTES); raw[HB_AWB_REFERENCE_REQUEST_OFFSET]=0;
        REQUIRE(hb_awb_recover_no_eligible(raw,HB_AWB_CONTEXT_BYTES,&no_eligible,&o)==0);
        REQUIRE(o.preceding_status==40 && o.outer_status==0 && !o.fresh_estimate_proven);
    }
    free(raw);free(expect);
}
static void test_scene(void) {
    hb_awb_scene_entry s={0,0};
    REQUIRE(hb_awb_select_supported_scene(NULL)==HB_AWB_SCENE_BAD_INPUT);
    REQUIRE(hb_awb_select_supported_scene(&s)==HB_AWB_SCENE_NO_ELIGIBLE);
    s.eligible_scene_mask=1u<<3;
    REQUIRE(hb_awb_select_supported_scene(&s)==HB_AWB_SCENE_SUPPORTED_SELECTED);
    s.eligible_scene_mask |= 1u<<2;
    REQUIRE(hb_awb_select_supported_scene(&s)==HB_AWB_SCENE_UNSUPPORTED);
    s.eligible_scene_mask=1u<<3; s.ordinary_illumination=1;
    REQUIRE(hb_awb_select_supported_scene(&s)==HB_AWB_SCENE_UNSUPPORTED);
    s.eligible_scene_mask=0;
    REQUIRE(hb_awb_select_supported_scene(&s)==HB_AWB_SCENE_UNSUPPORTED);
    s.ordinary_illumination=0;
    REQUIRE(hb_awb_select_supported_scene(&s)==HB_AWB_SCENE_NO_ELIGIBLE);
}
static void test_shading(void) {
    uint8_t *context=calloc(HB_AWB_CONTEXT_BYTES,1);
    REQUIRE(context!=NULL);
    hb_awb_shading_choice choose={{0},{0},1};
    for(int i=0;i<7;++i) choose.vendor_label_id[i]=(uint8_t)(i+1);
    hb_awb_shading_result out;
    REQUIRE(hb_awb_shading_select_bounded(NULL,HB_AWB_CONTEXT_BYTES,&choose,&out)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(hb_awb_shading_select_bounded(context,HB_AWB_CONTEXT_BYTES-1,&choose,&out)==HB_AWB_REBUILD_BAD_INPUT);
    set32(context+HB_AWB_SHADING_REFERENCE_CT_OFFSET,5200);
    set32(context+HB_AWB_SHADING_NORMAL_CT_OFFSET,7800);
    set32(context+HB_AWB_SHADING_OUTPUT_CT_OFFSET,9000);
    for(int val=0;val<256;++val) if(val!=1) {
        choose.validity=(uint8_t)val;
        REQUIRE(hb_awb_shading_select_bounded(context,HB_AWB_CONTEXT_BYTES,&choose,&out)==0);
        REQUIRE(!out.published && context[HB_AWB_SHADING_OUTPUT_CT_OFFSET]==(9000&255));
    }
    choose.validity=1;
    /* Later index wins even if all seven ratios are equal. */
    REQUIRE(hb_awb_shading_select_bounded(context,HB_AWB_CONTEXT_BYTES,&choose,&out)==0);
    REQUIRE(out.selected_index==6 && out.selected_label_id==7 && out.chosen_ct==7800);
    /* Every selected vendor ID is exercised, including the special labels. */
    for(int label=1;label<=7;++label) {
        for(unsigned i=0;i<7;++i) choose.label_ratio[i]=100;
        choose.label_ratio[label-1]=101;
        set32(context+HB_AWB_SHADING_PRIMARY_LABEL_OFFSET,2);
        set32(context+HB_AWB_SHADING_PRIMARY_COUNT_OFFSET,100);
        REQUIRE(hb_awb_shading_select_bounded(context,HB_AWB_CONTEXT_BYTES,&choose,&out)==0);
        REQUIRE(out.selected_label_id==label && out.selected_ratio==101);
        REQUIRE(out.chosen_ct==((label==1 || label==4)?5200u:7800u));
        REQUIRE(out.from_reference_ct==(label==1 || label==4));
        if(label!=1 && label!=4) {
            set32(context+HB_AWB_SHADING_PRIMARY_LABEL_OFFSET,3);
            set32(context+HB_AWB_SHADING_PRIMARY_COUNT_OFFSET,59);
            REQUIRE(hb_awb_shading_select_bounded(context,HB_AWB_CONTEXT_BYTES,&choose,&out)==0);
            REQUIRE(out.chosen_ct==7800);
            set32(context+HB_AWB_SHADING_PRIMARY_COUNT_OFFSET,60);
            REQUIRE(hb_awb_shading_select_bounded(context,HB_AWB_CONTEXT_BYTES,&choose,&out)==0);
            REQUIRE(out.chosen_ct==5200 && out.from_reference_ct);
        }
    }
    free(context);
}
static void test_publication(void) {
    uint8_t cand[156], published[156], history[156];
    hb_awb_publication_flags gates;
    REQUIRE(hb_awb_publication_gates(1, NULL, published,history, 156,&gates)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(hb_awb_publication_gates(1, cand, published,history, 0,&gates)==HB_AWB_REBUILD_BAD_INPUT);
    for(int valid=0;valid<256;++valid) {
        fill(cand,sizeof cand); fill(published,sizeof published); fill(history,sizeof history);
        uint8_t previous_pub[156],previous_hist[156];
        memcpy(previous_pub,published,sizeof published);
        memcpy(previous_hist,history,sizeof history);
        REQUIRE(hb_awb_publication_gates((uint8_t)valid,cand,published,history,sizeof cand,&gates)==HB_AWB_REBUILD_OK);
        REQUIRE(gates.candidate_published==(valid!=0));
        REQUIRE(gates.history_copied==(valid==1));
        REQUIRE(memcmp(published,valid?cand:previous_pub,sizeof cand)==0);
        REQUIRE(memcmp(history,valid==1?cand:previous_hist,sizeof cand)==0);
    }
    /* Later failure does not erase already published candidate/history here. */
    REQUIRE(hb_awb_publication_gates(1,cand,published,history,sizeof cand,&gates)==0);
    REQUIRE(memcmp(published,cand,sizeof cand)==0 && memcmp(history,cand,sizeof cand)==0);
}
static void test_filter(void) {
    uint8_t mask[1024]={0},out[1024]={0};
    hb_awb_component_stats st;
    REQUIRE(hb_awb_prune_small_components(NULL,out,HB_AWB_NEIGHBORS_FOUR,&st)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(hb_awb_prune_small_components(mask,out,(enum hb_awb_connectivity)6,&st)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(hb_awb_prune_small_components(mask,out,HB_AWB_NEIGHBORS_FOUR,&st)==0);
    REQUIRE(st.groups_kept==0 && st.groups_removed==0 && st.blocks_kept==0);
    /* One island with 3 blocks must disappear; separate island with 4 survives. */
    mask[0]=1; mask[1]=1; mask[2]=1;
    mask[10]=1; mask[11]=1; mask[42]=1; mask[43]=1;
    REQUIRE(hb_awb_prune_small_components(mask,out,HB_AWB_NEIGHBORS_FOUR,&st)==0);
    REQUIRE(st.groups_removed==1 && st.blocks_removed==3);
    REQUIRE(st.groups_kept==1 && st.blocks_kept==4);
    REQUIRE(!out[0] && !out[1] && !out[2] && out[10] && out[11] && out[42] && out[43]);
    /* Connection by diagonal changes with topology; we do not guess vendor topology. */
    memset(mask,0,1024);
    for(unsigned i=0;i<4;++i) mask[i*33]=255;
    REQUIRE(hb_awb_prune_small_components(mask,out,HB_AWB_NEIGHBORS_FOUR,&st)==0);
    REQUIRE(st.blocks_removed==4 && st.blocks_kept==0);
    REQUIRE(hb_awb_prune_small_components(mask,out,HB_AWB_NEIGHBORS_EIGHT,&st)==0);
    REQUIRE(st.blocks_removed==0 && st.blocks_kept==4);
    /* Aliasing input and output is supported by snapshot-before-filter. */
    REQUIRE(hb_awb_prune_small_components(mask,mask,HB_AWB_NEIGHBORS_EIGHT,&st)==0);
    REQUIRE(mask[0] && mask[33] && mask[66] && mask[99]);
}
static void test_q12(void) {
    for(unsigned i=0;i<10000;++i) {
        hb_awb_q12_pair in={rnd() & HB_AWB_MAX_SAFE_GAIN,rnd() & HB_AWB_MAX_SAFE_GAIN};
        hb_awb_q12_pair cal={rnd()|1u,rnd()|1u};
        if(i&1) { cal.a=(cal.a&16383)+1; cal.b=(cal.b&16383)+1; }
        hb_awb_recalib_result res=hb_awb_recalib_portable(in,cal);
        REQUIRE(res.adapter_status==HB_AWB_OK);
        REQUIRE(res.output.a==((uint64_t)in.a * 4096u)/cal.a);
        REQUIRE(res.output.b==((uint64_t)in.b * 4096u)/cal.b);
    }
    hb_awb_q12_pair t={4096,4096};
    hb_awb_q12_pair zero={0,4096};
    REQUIRE(hb_awb_recalib_portable(t,zero).adapter_status==HB_AWB_ZERO_CALIBRATION);
    t.a=HB_AWB_MAX_SAFE_GAIN+1;
    REQUIRE(hb_awb_recalib_portable(t,(hb_awb_q12_pair){4096,4096}).adapter_status==HB_AWB_GAIN_OVERFLOW);
}
int main(void) {
    test_outer(); test_scene(); test_shading(); test_publication(); test_filter(); test_q12();
    REQUIRE(hb_awb_clamp_ct(0)==2000);
    REQUIRE(hb_awb_clamp_ct(2000)==2000);
    REQUIRE(hb_awb_clamp_ct(5500)==5500);
    REQUIRE(hb_awb_clamp_ct(10000)==10000);
    REQUIRE(hb_awb_clamp_ct(UINT32_MAX)==10000);
    printf("{\"result\":\"PASS\",\"checks\":%u,\"original_firmware_compared\":false,\"scope\":\"bounded recorded contracts and synthetic scaffolding\"}\n",checks);
    return 0;
}