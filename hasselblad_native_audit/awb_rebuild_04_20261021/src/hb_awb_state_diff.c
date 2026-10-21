/* SPDX-License-Identifier: MIT */
#include "hb_awb_state_diff.h"
#include <limits.h>
int hb_awb_compare_state_snapshots(const uint8_t *oc,size_t ocl,
        const uint8_t *nc,size_t ncl,const uint8_t *oh,size_t ohl,
        const uint8_t *nh,size_t nhl,int32_t os,int32_t ns,hb_awb_diff_summary *out) {
    if (!oc || !nc || !oh || !nh || !out ||
        ocl!=HB_AWB_CONTEXT_BYTES || ncl!=HB_AWB_CONTEXT_BYTES ||
        ohl!=HB_AWB_REAWB_BYTES || nhl!=HB_AWB_REAWB_BYTES)
        return HB_AWB_REBUILD_BAD_INPUT;
    hb_awb_diff_summary tmp={0};
    tmp.context_first_mismatch=UINT32_MAX;
    tmp.reawb_first_mismatch=UINT32_MAX;
    tmp.original_return_status=os;
    tmp.owned_return_status=ns;
    for(uint32_t i=0;i<(uint32_t)HB_AWB_CONTEXT_BYTES;++i){
        if (oc[i]!=nc[i]){
            if(!tmp.context_differences)tmp.context_first_mismatch=i;
            ++tmp.context_differences;
        }
    }
    for(uint32_t i=0;i<(uint32_t)HB_AWB_REAWB_BYTES;++i){
        if (oh[i]!=nh[i]){
            if(!tmp.reawb_differences)tmp.reawb_first_mismatch=i;
            ++tmp.reawb_differences;
        }
    }
    tmp.all_bytes_and_status_equal=(uint8_t)(tmp.context_differences==0 &&
        tmp.reawb_differences==0 && os==ns);
    *out=tmp;
    return HB_AWB_REBUILD_OK;
}