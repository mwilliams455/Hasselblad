/* SPDX-License-Identifier: MIT */
#include "hb_awb_lifecycle.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static unsigned long long assertions=0;
#define CHECK(c) do { ++assertions; if(!(c)){fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#c);exit(2);} }while(0)
static uint32_t seed=0x9283a9du;
static uint32_t rand32(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
static void fill(uint8_t *p,size_t n){for(size_t i=0;i<n;i++) p[i]=(uint8_t)rand32();}

int main(void) {
    uint8_t *ctx=malloc(HB_AWB_CONTEXT_BYTES),*before=malloc(HB_AWB_CONTEXT_BYTES);
    uint8_t *expected=malloc(HB_AWB_CONTEXT_BYTES),*handle=malloc(HB_AWB_REAWB_BYTES);
    uint8_t *handle_copy=malloc(HB_AWB_REAWB_BYTES);
    CHECK(ctx&&before&&expected&&handle&&handle_copy);
    hb_awb_lifecycle_journal journal={.revision=HB_AWB_LIFECYCLE_REVISION};
    const int status_cases[]={0,40,151,-4,0,0,151};
    const int final_cases[]={0,0,0,0,9,0,0};
    for(unsigned turn=0;turn<700;turn++) {
        fill(ctx,HB_AWB_CONTEXT_BYTES);fill(handle,HB_AWB_REAWB_BYTES);
        memcpy(before,ctx,HB_AWB_CONTEXT_BYTES);
        memcpy(handle_copy,handle,HB_AWB_REAWB_BYTES);
        memcpy(expected,ctx,HB_AWB_CONTEXT_BYTES);
        int inner=status_cases[turn%7],fin=final_cases[turn%7];
        const int req=turn%7==5 ? 1 : (turn%7==6 ? 2 : 0);
        ctx[HB_AWB_REFERENCE_REQUEST_OFFSET]=(uint8_t)req;
        before[HB_AWB_REFERENCE_REQUEST_OFFSET]=(uint8_t)req;
        expected[HB_AWB_REFERENCE_REQUEST_OFFSET]=(uint8_t)req;
        memset(expected+HB_AWB_CLEAR_OFFSET,0,4);
        int origin;
        if(req==1) {
            for(unsigned k=0;k<HB_AWB_RESULT_BYTES;k++) {
                uint8_t v=expected[HB_AWB_REFERENCE_RESULT_OFFSET+k];
                expected[HB_AWB_LIVE_A_OFFSET+k]=v;
                expected[HB_AWB_LIVE_B_OFFSET+k]=v;
                expected[HB_AWB_CONFIRMED_A_OFFSET+k]=v;
                expected[HB_AWB_CONFIRMED_B_OFFSET+k]=v;
            }
            expected[HB_AWB_REFERENCE_REQUEST_OFFSET]=0;
            origin=HB_AWB_ORIGIN_REFERENCE_OVERRIDE;
        } else if(inner!=0) {
            memcpy(expected+HB_AWB_LIVE_A_OFFSET,expected+HB_AWB_CONFIRMED_A_OFFSET,HB_AWB_RESULT_BYTES);
            memcpy(expected+HB_AWB_LIVE_B_OFFSET,expected+HB_AWB_CONFIRMED_B_OFFSET,HB_AWB_RESULT_BYTES);
            origin=HB_AWB_ORIGIN_RESTORED_CONFIRMED;
        } else {
            memcpy(expected+HB_AWB_CONFIRMED_A_OFFSET,expected+HB_AWB_LIVE_A_OFFSET,HB_AWB_RESULT_BYTES);
            memcpy(expected+HB_AWB_CONFIRMED_B_OFFSET,expected+HB_AWB_LIVE_B_OFFSET,HB_AWB_RESULT_BYTES);
            origin=HB_AWB_ORIGIN_LIVE_PUBLISHED;
        }
        hb_awb_lifecycle_result result={0};
        uint64_t serial=100000u+turn;
        int rc=hb_awb_lifecycle_advance(&journal,serial,ctx,HB_AWB_CONTEXT_BYTES,
                                         handle,HB_AWB_REAWB_BYTES,inner,fin,&result);
        CHECK(rc==0);
        CHECK(!memcmp(ctx,expected,HB_AWB_CONTEXT_BYTES));
        CHECK(!memcmp(handle,handle_copy,HB_AWB_REAWB_BYTES));
        CHECK(result.frame_serial==serial);
        CHECK(result.inner_status==inner);
        CHECK(result.outer_status==fin);
        CHECK((int)result.result_origin==origin);
        CHECK(result.outer_success==(fin==0));
        CHECK(result.result_restored_or_overridden==(origin!=HB_AWB_ORIGIN_LIVE_PUBLISHED));
        CHECK(result.fresh_vendor_estimate_proven==0);
        CHECK(result.passive_reawb_preserved==1);
        CHECK(journal.processed_frames==turn+1);
        CHECK(journal.last_frame_serial==serial);
        CHECK(journal.original_scene_estimate_verified==0);
        uint8_t prior_req=ctx[HB_AWB_REFERENCE_REQUEST_OFFSET];
        hb_awb_lifecycle_journal old=journal;
        hb_awb_lifecycle_result oldresult=result;
        CHECK(hb_awb_lifecycle_advance(&journal,serial,ctx,HB_AWB_CONTEXT_BYTES,handle,
                HB_AWB_REAWB_BYTES,inner,fin,&result)==HB_AWB_REBUILD_BAD_INPUT);
        CHECK(!memcmp(ctx,expected,HB_AWB_CONTEXT_BYTES));
        CHECK(!memcmp(handle,handle_copy,HB_AWB_REAWB_BYTES));
        CHECK(!memcmp(&old,&journal,sizeof(journal)));
        CHECK(!memcmp(&oldresult,&result,sizeof(result)));
        CHECK(ctx[HB_AWB_REFERENCE_REQUEST_OFFSET]==prior_req);
        CHECK(hb_awb_lifecycle_advance(&journal,serial+1,ctx,HB_AWB_CONTEXT_BYTES-1,handle,
                HB_AWB_REAWB_BYTES,inner,fin,&result)==HB_AWB_REBUILD_BAD_INPUT);
        CHECK(hb_awb_lifecycle_advance(&journal,serial+1,ctx,HB_AWB_CONTEXT_BYTES,handle,
                HB_AWB_REAWB_BYTES+1,inner,fin,&result)==HB_AWB_REBUILD_BAD_INPUT);
        CHECK(!memcmp(ctx,expected,HB_AWB_CONTEXT_BYTES));
    }
    CHECK(journal.processed_frames==700);
    CHECK(journal.confirmed_restorations>0);
    CHECK(journal.reference_overrides>0);
    CHECK(journal.live_publications>0);
    CHECK(journal.outer_returns_success>0);
    CHECK(journal.inner_returns_error>0);
    free(ctx);free(before);free(expected);free(handle);free(handle_copy);
    printf("LIFECYCLE PASS %llu assertions; 700 frames; vendor_equality=NOT_TESTED\n",assertions);
    return 0;
}