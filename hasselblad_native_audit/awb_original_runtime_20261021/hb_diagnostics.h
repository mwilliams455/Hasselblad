/* SPDX-License-Identifier: MIT */
#ifndef HB_DIAGNOSTICS_H
#define HB_DIAGNOSTICS_H
#include <stddef.h>
#include <stdint.h>
#define HB_DEBUG_WORKSPACE_BYTES ((size_t)0xc04)
/* Pinned-firmware research ABI: initialized 920560-byte context. Metadata
 * lengths A <= 510, A+B <= 1015; dimensions <= 64 and n == width*height.
 * Workspace must be separate from context. No original callbacks or file I/O.
 * Unsupported inputs return HB_PREP_UNSUPPORTED without modifying buffers. */
uint32_t hb_debug_encode(unsigned char *ctx);
uint32_t hb_debug_userdump_no_file(unsigned char *ctx);
uint32_t hb_debug_process(unsigned char *ctx,unsigned char *workspace,size_t bytes);
#endif
