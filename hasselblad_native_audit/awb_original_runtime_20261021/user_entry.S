/* SPDX-License-Identifier: MIT
 * Test-only ABI adapter into unmodified scene_awb_user_proc at 0x4b1624,
 * 0x4b162c, 0x4b16a8 or 0x4b16d4 (after CT/tint/gain requests).
 * x0 entry address. Rebuilds its saved-register/TLS frame, slot zero.
 * Original remainder returns directly to our caller; no code is patched. */
.text
.global hb_original_user_remainder
.type hb_original_user_remainder,%function
hb_original_user_remainder:
    stp x28,x27,[sp,#-0x60]!
    stp x26,x25,[sp,#0x10]
    stp x24,x23,[sp,#0x20]
    stp x22,x21,[sp,#0x30]
    stp x20,x19,[sp,#0x40]
    stp x29,x30,[sp,#0x50]
    add x29,sp,#0x50
    sub sp,sp,#0x1b0
    mov x16,x0
    mrs x25,tpidr_el0
    ldr x8,[x25,#0x28]
    stur x8,[x29,#-0x58]
    mov w26,wzr
    br x16
.size hb_original_user_remainder,.-hb_original_user_remainder
.section .note.GNU-stack,"",%progbits
