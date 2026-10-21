/* SPDX-License-Identifier: MIT */
#ifndef HB_STAT_DIFFERENCE_H
#define HB_STAT_DIFFERENCE_H
#include <stdint.h>
/* Initialized research ABI: context920560/config1502800, <=1024 samples and
 * <=12 ROI records. Optional REAWB handle is1000 bytes; NULL models the
 * original missing-handle path. It is read only. No linked storage is used.
 * Owns diagnostic counter advancement but excludes diagnostic logging.
 * Zero samples are supported on forced/disabled/ROI/periodic refresh routes;
 * reaching numerical difference with zero samples returns HB_PREP_UNSUPPORTED
 * before mutation (the original aborts). Other shape guards also precede writes.
 * Original missing-handle+disabled-check returns UINT32_MAX after setting the
 * refresh flag; other supported paths return0. */
uint32_t hb_stat_difference(unsigned char*,const unsigned char*,const unsigned char*);
#endif
