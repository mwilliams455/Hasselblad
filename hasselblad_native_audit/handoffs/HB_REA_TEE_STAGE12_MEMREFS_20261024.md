# Hasselblad REA — Stage12 original secure-memory contract

**Prepared:** 24 October 2026 (UK). This report continues from the verified Stage9–11 TEE selector analysis; it does not restart IMaH header decryption, RSA validation or failed TBIE key tests.

## Execution and provenance

- Firmware: original official X2D II 100C 1.3.16.2, outer CIM verified against the existing exact SHA-256 and extracted transiently.
- Research branch: `research/rea-tee-20261024`.
- Completed original run: https://github.com/mwilliams455/Hasselblad/actions/runs/40108045571
- Safe artifact: `Hasselblad-REA-TEE-Memrefs-Stage12-Safe`, reports `HB_REA12_ORIGINAL_SAFE.json` and `HB_REA12_EXECUTION_SAFE.json`.
- Source: `hasselblad_native_audit/tee_mem_stage12/inspect_memrefs12.py`.
- Original source library: `system/lib64/libfw_util_ca.so`, exact SHA-256 `96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b`.
- REA GNU objdump JSON inspection and independent Capstone ELF instruction analysis both passed. Vendor binaries, raw instructions, strings, disassembly, key material, and camera images are not exported.
- The first Stage12 run halted because an **unverified expected copy count for command 1 was incorrect**. The script was changed to retain observed counts and flag discrepancies, rather than discard real measurements. The corrected original-firmware run completed successfully.

## Native TEEC function comparisons

| Command | Function | Operation SP | FD registration | Memory allocations | strncpy | ParamTypes |
|---|---|---:|---|---|---|---|
| 1 | fw_util_load | +184 | x1 = SP+80, fd = w24, at 0x1528 | SP+32 at 0x158c | 0x15d8 | 0x11DD |
| 2 | fw_util_verify_load2ion | +168 | x1 = SP+64, fd = w23, at 0x17dc | SP+16 at 0x1838 | 0x1884 | 0x11DF |
| 3 | fw_util_verify_init | +120 | none found | SP+16 at 0x1acc | 0x1b08 | 0x000D |
| 6 | fw_util_verify_init_ext | +192 | none found | SP+120 at 0x1d50; SP+72 at 0x1db4; SP+24 at 0x1e0c | 0x1d8c, 0x1df0, 0x1e98 | 0x1DDD |

All four commands have independently established TEE_Operation paramTypes from original Stage9 code.

### Command 6
- Three distinct 48-byte-spaced TEEC_SharedMemory stack structures are passed to consecutive `TEEC_AllocateSharedMemory` calls.
- Three `strncpy` calls have source registers `x23`, `x22`, `x21`, respectively. The destination `x0` is loaded via `ldp` and not yet proven to be the exact corresponding buffer pointer; Stage13 will check the original instruction operands.
- Fourth TEE_Operation parameter (VALUE_INPUT) receives 32-bit words from `w20` and `w19` at operation offsets +80/+84 (original stores 0x1ef0 and 0x1ef4).
- Stage12 did **not** find direct-SP store instructions to first three operation parameter slots. This is a coverage boundary of the simple direct-store scanner, **not** evidence that the memrefs are uninitialized, missing or inaccessible.
- No decrypted key, TA or DSP was recovered.

### Command 2
- Original `TEEC_RegisterSharedMemoryFileDescriptor` takes the registration object at SP+64 and an fd in w23.
- A separate `TEEC_AllocateSharedMemory` takes SP+16.
- p0 is declared PARTIAL_INOUT; p1 PARTIAL_INPUT; p2 and p3 VALUE_INPUT.
- The observed p3 first word at operation SP+248 is literal 1; the p2 first word is stored from w20. These are bounded static caller facts, not yet mapped to secure-world status/results.
- Which object actually becomes p0 versus p1 **is not yet proved**. Presence of PARTIAL_INOUT alone is not evidence decrypted plaintext was returned.

### Command 1
- Registers an FD-backed object at SP+80 and allocates SP+32.
- Both p0 and p1 are PARTIAL_INPUT; thus its operation's declared memory parameters are input-only.
- One original `strncpy` call at 0x15d8 is verified, correcting the earlier zero-copy expectation.
- As in command 2, object-to-parameter parent assignments require separate validation.

### Command 3
- Allocates SP+16 and uses one PARTIAL_INPUT.
- Unlike commands 1/2/6, the simple direct-SP scanner observed the original p0 parent and size writes at VA 0x1b50: the parent comes from a pointer formed with SP+16, and the size from SP+24. This is a direct structural match for the allocated object.

## Interpretation and next milestone

This closes the original normal-world **allocation topology** but not the secure-world data ownership graph. The next useful proof is the ABI-argument mapping for command6’s three `strncpy` sources and p3 version words; then resolve the original `TEEC_Operation` p0/p1/p2 parent references, potentially built through non-SP aliases, before making any claim about whether command2 returns decrypted data. Continue to distinguish main hardware CCM from DSP software.

Normal Photon saved photographs, Stage62 experimental renderer, original X2D II camera, and production `main` unchanged.
