/* SPDX-License-Identifier: MIT */
#include "hb_automatic.h"
#include "hb_white_lut.h"
#include "hb_user_finish.h"
#include "hb_roi.h"
#include "hb_stat_prepare.h"
#include "hb_sensor.h"
#include "hb_parsing.h"
#include "hb_detect.h"
#include "hb_face.h"
#include "hb_scene_controller.h"
#include "hb_history.h"
#include "hb_atmosphere.h"
#include "hb_post_controller.h"
#include "hb_diagnostics.h"
#include <string.h>
static uint32_t u32(const void*p){uint32_t v;memcpy(&v,p,4);return v;}
static int inputs_ok(const unsigned char*c,const unsigned char*k,
                     const hb_automatic_inputs*i,const hb_automatic_trace*t){
 return c&&k&&i&&t&&i->temperature&&i->temperature->isotemperature_31x4&&
  i->roi&&i->debug_workspace&&i->debug_workspace_bytes>=HB_DEBUG_WORKSPACE_BYTES;
}
static uint32_t observed(hb_automatic_trace*t,enum hb_auto_stage stage,uint32_t s){
 t->stages|=UINT64_C(1)<<stage;if(s){t->failed_stage=stage;t->stage_status=s;}return s;
}
uint32_t hb_automatic_tail(unsigned char*c,unsigned char*k,unsigned char*r,
 const hb_automatic_inputs*i,enum hb_auto_tail path,uint32_t s,hb_automatic_trace*t){
 if(!inputs_ok(c,k,i,t)||(unsigned)path>HB_AUTO_ERROR_TAIL)return HB_PREP_UNSUPPORTED;
 if(s==HB_PREP_UNSUPPORTED)return s;
 if(!s&&path!=HB_AUTO_ERROR_TAIL){
  if(path==HB_AUTO_REFRESH_TAIL){
   s=observed(t,HB_AUTO_SCENE,hb_scene_process(c,k,i->temperature,0));if(s)goto finish;
   s=observed(t,HB_AUTO_HISTORY,hb_history_process(c,k));if(s)goto finish;
   s=observed(t,HB_AUTO_ATMOSPHERE,hb_atmosphere_process(c,k,i->temperature));if(s)goto finish;
  }
  s=observed(t,HB_AUTO_POST,hb_post_process(c,k,i->temperature,r));if(s)goto finish;
  if(path==HB_AUTO_REFRESH_TAIL){s=observed(t,HB_AUTO_REAWB,hb_reawb_passive(c,r));if(s)goto finish;}
  s=observed(t,HB_AUTO_DEBUG,hb_debug_process(c,i->debug_workspace,i->debug_workspace_bytes));if(s)goto finish;
  if(path==HB_AUTO_REFRESH_TAIL){
   /* Original shading's return does not replace the successful debug status. */
   observed(t,HB_AUTO_SHADING,hb_shading_temperature(c));
  }
 }
finish:
 if(s==HB_PREP_UNSUPPORTED)return s;
 t->stages|=UINT64_C(1)<<HB_AUTO_COMPLETION;t->completed=1;
 return hb_outer_complete(c,s,&t->completion);
}
uint32_t hb_run_automatic(unsigned char*c,unsigned char*k,unsigned char*r,
 const hb_automatic_inputs*i,hb_automatic_trace*t){
 if(!inputs_ok(c,k,i,t)||u32(c+0x194)>=2)return HB_PREP_UNSUPPORTED;
 memset(t,0,sizeof *t);t->failed_stage=HB_AUTO_STAGE_COUNT;
 uint32_t s=observed(t,HB_AUTO_ENTRY,hb_run_entry(c,k,&t->entry));if(s)return s;
 if(t->entry.action==HB_RUN_RETURN)return t->entry.status;
 s=observed(t,HB_AUTO_WHITE_LUT,hb_white_lut_prepare(c,k));if(s)return s;
 s=observed(t,HB_AUTO_USER,hb_user_process(c,k,i->temperature));if(s)return s;
 s=observed(t,HB_AUTO_DISPATCH,hb_run_dispatch(c,k,r,&t->dispatch));if(s)return s;
 s=t->dispatch.status;if(s){t->failed_stage=HB_AUTO_DISPATCH;t->stage_status=s;}
 if(t->dispatch.action==HB_DISPATCH_RETURN)return s;
 if(t->dispatch.action==HB_DISPATCH_MANUAL||t->dispatch.action==HB_DISPATCH_CUSTOM)
  return observed(t,HB_AUTO_DISPATCH,HB_PREP_UNSUPPORTED);
 if(t->dispatch.action==HB_DISPATCH_COMPLETE_ERROR)goto finish;
 s=observed(t,HB_AUTO_SYNC,hb_roi_sync_process(c,k,i->roi));if(s)goto finish;
 s=observed(t,HB_AUTO_ROI,hb_roi_process(c,k));if(s)goto finish;
 if(t->dispatch.action==HB_DISPATCH_AUTO_REFRESH){
  s=observed(t,HB_AUTO_STATISTICS,hb_stat_auto_complete(c,k));if(s)goto finish;
  s=observed(t,HB_AUTO_SENSOR,hb_sensor_process(c,k));if(s)goto finish;
  s=observed(t,HB_AUTO_PARSING,hb_parsing_process(c,k));if(s)goto finish;
  s=observed(t,HB_AUTO_DETECT,hb_detect_process(c,k));if(s)goto finish;
  s=observed(t,HB_AUTO_FACE,hb_face_process(c,k));if(s)goto finish;
 }
finish:
 return hb_automatic_tail(c,k,r,i,t->dispatch.action==HB_DISPATCH_AUTO_REFRESH?
  HB_AUTO_REFRESH_TAIL:t->dispatch.action==HB_DISPATCH_AUTO_REUSE?
  HB_AUTO_REUSE_TAIL:HB_AUTO_ERROR_TAIL,s,t);
}
