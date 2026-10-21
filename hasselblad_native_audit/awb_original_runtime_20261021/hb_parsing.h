/* SPDX-License-Identifier: MIT */
#ifndef HB_PARSING_H
#define HB_PARSING_H
#include <stdint.h>
/* Initialized research ABI: context920560/config1502800 bytes. Config is
 * writable: the original disables parsing for a wrapped grid area>1024.
 * Active supported bounds: dimensions/count<=1024, area<=1024, four zones,
 * eight density/weight rows, and1..8 exposure rows. Shape guards precede
 * numerical writes. Empty selected density/weight tables retain status177.
 * Model data is caller supplied; logging is omitted. */
uint32_t hb_parsing_process(unsigned char*,unsigned char*);
#endif
