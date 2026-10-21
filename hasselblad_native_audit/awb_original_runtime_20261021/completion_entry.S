/* SPDX-License-Identifier: MIT
 * Test-only ABI adapter for prepared entries into the UNMODIFIED controller.
 * x0 = entry address, x1 = live context, w2 = preceding status, x3 = globals.
 * Rebuilds the controller's saved-register / TLS-canary frame so its normal
 * epilogue returns directly to our caller. Sensor is always initialized slot 0.
 * This does not exercise the omitted prefix or replace any original function. */
.text
.global hb_original_prepared_completion
.type hb_original_prepared_completion,%function
hb_original_prepared_completion:
    sub sp,sp,#0x150
    str d8,[sp,#0xe0]
    stp x28,x27,[sp,#0xf0]
    stp x26,x25,[sp,#0x100]
    stp x24,x23,[sp,#0x110]
    stp x22,x21,[sp,#0x120]
    stp x20,x19,[sp,#0x130]
    stp x29,x30,[sp,#0x140]
    add x29,sp,#0x140
    mov x16,x0
    mov x26,x1
    mov w20,w2
    mov x27,x3
    mov w19,wzr
    mov x21,xzr
    mrs x24,tpidr_el0
    ldr x8,[x24,#0x28]
    str x8,[sp,#0x40]
    br x16
.size hb_original_prepared_completion,.-hb_original_prepared_completion
.section .note.GNU-stack,"",%progbits
