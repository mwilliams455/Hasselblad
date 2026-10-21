/* SPDX-License-Identifier: MIT
 * Negative controls and two-phase replay of the HISTORICALLY RECORDED
 * optimizer caller-side updates. This is not a vendor algorithm test.
 */
#include "hb_awb_optimizer_boundary.h"
#include "hb_awb_state_diff.h"
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint64_t checks=0;
#define REQUIRE(X) do { ++checks; if (!(X)) {fprintf(stderr,"line %d: %s\n",__LINE__,#X);exit(2);} } while(0)
static uint32_t seed=0xBADC0DE1u;
static uint32_t rand32(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}

static hb_awb_scene_accumulation accum(uint32_t x){
    hb_awb_scene_accumulation a={0};
    for(unsigned j=0;j<4;++j){a.weighted_site_sum_q16[j]=((int64_t)(int32_t)(x^((j+1)*3137u)))*65536;
        a.weighted_site_count[j]=4u+x%113u+j;}
    a.weighted_sample_count=30u+x%4096u;
    a.weighted_raw_brightness_q16=-(int64_t)x*71;
    a.weighted_at_or_above_white_count=x%7;
    a.surviving_blocks=4u+x%1000u;
    a.filter.blocks_kept=(uint16_t)a.surviving_blocks;
    a.filter.groups_kept=1;
    a.weighted_but_unclassified_blocks=x%a.surviving_blocks;
    return a;
}
static void test_pair(void) {
    hb_awb_optimizer_caller_state s={0};
    for(uint64_t serial=1;serial<=10000;++serial){
        hb_awb_scene_accumulation a=accum(rand32());
        hb_awb_optimizer_trace trace={0};
        trace.revision=1;
        trace.frame_serial=serial;
        trace.expected_accumulation_fingerprint=hb_awb_accumulation_fingerprint(&a);
        trace.caller_window_observed=1;
        trace.observed_optimizer_status=(serial%19u==0u)?151:(serial%29u==0u)?40:0;
        trace.observed_caller_delta_blocks=rand32()%5;
        trace.observed_caller_delta_samples=rand32()%600;
        trace.observed_caller_delta_candidates=rand32()%3;
        for(unsigned j=0;j<32;++j)trace.opaque_result[j]=(uint8_t)rand32();
        hb_awb_optimizer_staged staged={0};
        hb_awb_optimizer_caller_state before=s;
        REQUIRE(hb_awb_optimizer_stage_observation(&a,&trace,&staged)==0);
        REQUIRE(memcmp(&s,&before,sizeof(s))==0);
        REQUIRE(staged.frame_serial==serial);
        REQUIRE(staged.input_fingerprint==trace.expected_accumulation_fingerprint);
        REQUIRE(staged.observed_optimizer_status==trace.observed_optimizer_status);
        REQUIRE(!staged.original_firmware_equivalence_proven);
        REQUIRE(!staged.selected_neutral_produced);
        uint64_t expected_c=s.candidate_count+trace.observed_caller_delta_candidates;
        uint64_t expected_b=s.consumed_block_count+trace.observed_caller_delta_blocks;
        uint64_t expected_s=s.consumed_sample_count+trace.observed_caller_delta_samples;
        REQUIRE(hb_awb_optimizer_apply_observed_caller_update(&staged,&s)==0);
        REQUIRE(s.candidate_count==expected_c && s.consumed_block_count==expected_b);
        REQUIRE(s.consumed_sample_count==expected_s);
        REQUIRE(s.last_applied_frame_serial==serial);
        REQUIRE(s.last_optimizer_status==trace.observed_optimizer_status);
        REQUIRE(memcmp(s.opaque_last_result,trace.opaque_result,32)==0);
        hb_awb_optimizer_caller_state snapshot=s;
        REQUIRE(hb_awb_optimizer_apply_observed_caller_update(&staged,&s)==HB_AWB_REBUILD_BAD_INPUT);
        REQUIRE(memcmp(&snapshot,&s,sizeof(s))==0);
        if(serial%128u==0u){
            hb_awb_optimizer_staged unchanged=staged;
            trace.expected_accumulation_fingerprint^=UINT64_C(1);
            REQUIRE(hb_awb_optimizer_stage_observation(&a,&trace,&staged)==HB_AWB_REBUILD_UNSUPPORTED);
            REQUIRE(memcmp(&staged,&unchanged,sizeof(staged))==0);
            trace.expected_accumulation_fingerprint^=UINT64_C(1);
            trace.caller_window_observed=0;
            REQUIRE(hb_awb_optimizer_stage_observation(&a,&trace,&staged)==HB_AWB_REBUILD_BAD_INPUT);
            REQUIRE(memcmp(&staged,&unchanged,sizeof(staged))==0);
        }
    }
    hb_awb_scene_accumulation a=accum(999);
    hb_awb_optimizer_trace t={.revision=1,.frame_serial=10001,.caller_window_observed=1};
    t.expected_accumulation_fingerprint=hb_awb_accumulation_fingerprint(&a);
    hb_awb_optimizer_staged staged={0};
    REQUIRE(hb_awb_optimizer_stage_observation(&a,&t,&staged)==0);
    hb_awb_optimizer_caller_state before=s;
    s.candidate_count=UINT64_MAX;
    before=s;
    staged.caller_delta_candidates=1;
    REQUIRE(hb_awb_optimizer_apply_observed_caller_update(&staged,&s)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(memcmp(&before,&s,sizeof(s))==0);
    s.candidate_count=0;s.consumed_block_count=UINT64_MAX;before=s;
    staged.caller_delta_candidates=0;staged.caller_delta_blocks=2;
    REQUIRE(hb_awb_optimizer_apply_observed_caller_update(&staged,&s)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(memcmp(&before,&s,sizeof(s))==0);
    s.consumed_block_count=0;s.consumed_sample_count=UINT64_MAX;before=s;
    staged.caller_delta_blocks=0;staged.caller_delta_samples=1;
    REQUIRE(hb_awb_optimizer_apply_observed_caller_update(&staged,&s)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(memcmp(&before,&s,sizeof(s))==0);
    a.surviving_blocks=0;
    staged.frame_serial=999999;
    REQUIRE(hb_awb_optimizer_stage_observation(&a,&t,&staged)==HB_AWB_REBUILD_BAD_INPUT);
}
static void test_byte_diff(void){
    uint8_t *o=calloc(HB_AWB_CONTEXT_BYTES,1),*n=calloc(HB_AWB_CONTEXT_BYTES,1);
    uint8_t *h=calloc(HB_AWB_REAWB_BYTES,1),*k=calloc(HB_AWB_REAWB_BYTES,1);
    REQUIRE(o&&n&&h&&k);
    hb_awb_diff_summary result={0};
    REQUIRE(hb_awb_compare_state_snapshots(o,HB_AWB_CONTEXT_BYTES,n,HB_AWB_CONTEXT_BYTES,
        h,HB_AWB_REAWB_BYTES,k,HB_AWB_REAWB_BYTES,0,0,&result)==0);
    REQUIRE(result.all_bytes_and_status_equal && result.context_first_mismatch==UINT32_MAX);
    REQUIRE(result.reawb_first_mismatch==UINT32_MAX && !result.original_reference_proven);
    n[0]=1;n[HB_AWB_CONTEXT_BYTES-1]=1;k[432]=1;
    REQUIRE(hb_awb_compare_state_snapshots(o,HB_AWB_CONTEXT_BYTES,n,HB_AWB_CONTEXT_BYTES,
        h,HB_AWB_REAWB_BYTES,k,HB_AWB_REAWB_BYTES,151,0,&result)==0);
    REQUIRE(!result.all_bytes_and_status_equal);
    REQUIRE(result.context_differences==2 && result.context_first_mismatch==0);
    REQUIRE(result.reawb_differences==1 && result.reawb_first_mismatch==432);
    REQUIRE(result.original_return_status==151 && result.owned_return_status==0);
    hb_awb_diff_summary backup=result;
    REQUIRE(hb_awb_compare_state_snapshots(o,HB_AWB_CONTEXT_BYTES-1,n,HB_AWB_CONTEXT_BYTES,
        h,HB_AWB_REAWB_BYTES,k,HB_AWB_REAWB_BYTES,151,0,&result)==HB_AWB_REBUILD_BAD_INPUT);
    REQUIRE(memcmp(&backup,&result,sizeof(result))==0);
    n[0]=0;n[HB_AWB_CONTEXT_BYTES-1]=0;k[432]=0;
    REQUIRE(hb_awb_compare_state_snapshots(o,HB_AWB_CONTEXT_BYTES,n,HB_AWB_CONTEXT_BYTES,
        h,HB_AWB_REAWB_BYTES,k,HB_AWB_REAWB_BYTES,0,1,&result)==0);
    REQUIRE(!result.all_bytes_and_status_equal);
    REQUIRE(result.context_differences==0 && result.reawb_differences==0);
    free(o);free(n);free(h);free(k);
}
int main(void){test_pair();test_byte_diff();printf("{\"result\":\"PASS\",\"checks\":%" PRIu64 ",\"scope\":\"owned optimizer trace/caller update and byte diff\",\"vendor_compared\":false}\n",checks);return 0;}