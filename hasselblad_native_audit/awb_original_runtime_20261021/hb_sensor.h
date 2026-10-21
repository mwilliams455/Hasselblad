/* SPDX-License-Identifier: MIT */
#ifndef HB_SENSOR_H
#define HB_SENSOR_H
#include <stdint.h>
/* Research ABI: initialized 920560-byte context, 1502800-byte configuration.
 * All calibration, spectral and classifier data are caller supplied.
 * Supported: two gain rows, three classes, 256 support vectors, 15 nodes,
 * three adjustment records with 1..8 rows at each interpolation level.
 * Unsupported shapes return HB_PREP_UNSUPPORTED before writes. Logging is
 * excluded. This is not a phone sensor calibration or production ABI. */
uint32_t hb_sensor_calibration(const unsigned char*,uint32_t,void*);
uint32_t hb_sensor_parameter_pass(unsigned char*);
uint32_t hb_sensor_process(unsigned char*,const unsigned char*);
#endif
