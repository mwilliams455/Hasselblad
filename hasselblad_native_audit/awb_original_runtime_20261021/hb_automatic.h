/* SPDX-License-Identifier: MIT */
#ifndef HB_AUTOMATIC_H
#define HB_AUTOMATIC_H
#include "hb_run_entry.h"
#include "hb_run_dispatch.h"
#include "hb_completion.h"
#include "hb_roi_sync.h"
#include "hb_temperature.h"
#include <stddef.h>
enum hb_auto_stage { HB_AUTO_ENTRY, HB_AUTO_WHITE_LUT, HB_AUTO_USER,
 HB_AUTO_DISPATCH, HB_AUTO_SYNC, HB_AUTO_ROI, HB_AUTO_STATISTICS,
 HB_AUTO_SENSOR, HB_AUTO_PARSING, HB_AUTO_DETECT, HB_AUTO_FACE,
 HB_AUTO_SCENE, HB_AUTO_HISTORY, HB_AUTO_ATMOSPHERE, HB_AUTO_POST,
 HB_AUTO_REAWB, HB_AUTO_DEBUG, HB_AUTO_SHADING, HB_AUTO_COMPLETION,
 HB_AUTO_STAGE_COUNT };
typedef struct {
 const hb_temperature_model *temperature;
 const hb_roi_sync_model *roi;
 unsigned char *debug_workspace;
 size_t debug_workspace_bytes;
} hb_automatic_inputs;
typedef struct {
 hb_run_entry_result entry;
 hb_dispatch_result dispatch;
 uint64_t stages;
 enum hb_auto_stage failed_stage; /* STAGE_COUNT when no stage failed. */
 uint32_t stage_status; /* Preserves the error hidden by original recovery. */
 unsigned completed;
 hb_completion_record completion;
} hb_automatic_trace;
enum hb_auto_tail { HB_AUTO_REFRESH_TAIL, HB_AUTO_REUSE_TAIL,
                   HB_AUTO_ERROR_TAIL };
/* Initialized research ABI: context920560/config1502800/REAWB1000 bytes.
 * All existing stage table bounds apply. Models/calibration are caller-owned;
 * no firmware functions or data are embedded. Modes0/1 only. Initialization,
 * native statistics import and phone calibration remain external.
 * Early entry/LUT/user returns preserve the original behavior. Native errors
 * after dispatch restore confirmed output via completion, which can return0;
 * inspect trace.stage_status and trace.completion, not just the return value.
 * Unsupported stages return HB_PREP_UNSUPPORTED WITHOUT success completion.
 * Prior stage writes remain; discard/reinitialize that working state. Invalid
 * arguments and initial mode>=2 reject before touching caller buffers/trace. */
uint32_t hb_run_automatic(unsigned char*,unsigned char*,unsigned char*,
                        const hb_automatic_inputs*,hb_automatic_trace*);
/* Composition boundary for the verified prefix. Trace must be initialized
 * (failed_stage=STAGE_COUNT); appends stage bits and completion provenance.
 * Refresh:scene/history/atmos/post/passive REAWB/debug/shading/completion.
 * Reuse:post/debug/completion. Error:completion only. */
uint32_t hb_automatic_tail(unsigned char*,unsigned char*,unsigned char*,
                         const hb_automatic_inputs*,enum hb_auto_tail,
                         uint32_t preceding_status,hb_automatic_trace*);
#endif
