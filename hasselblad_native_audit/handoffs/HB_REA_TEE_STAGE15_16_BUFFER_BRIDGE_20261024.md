# Hasselblad REA — Stage15 to Stage16 original TEE buffer bridge

**Date:** 24 October 2026. Isolated research branch `research/rea-tee-20261024`. Original X2D II 100C firmware **1.3.16.2**, exact-hash verified and extracted transiently. This continues after Stage13–14 fully established command6 input sources/versions; no repeat RSA signing, outer-CIM decryption, or public TBIE key guessing.

## Provenance
- Stage15 CI: https://github.com/mwilliams455/Hasselblad/actions/runs/40109053189, report `HB_REA15_ORIGINAL_SAFE.json`.
- Stage16 CI: https://github.com/mwilliams455/Hasselblad/actions/runs/40109355818, report `HB_REA16_ORIGINAL_SAFE.json`.
- Both original code inspections ran without executing original vendor code, and REA GNU-objdump provider completed on original `libfw_util_ca.so`.
- Independent Stage15 Capstone AArch64 control-flow register-alias fixed point; Stage16 direct-call/parameter trace. Published receipts omit original instruction bytes, pseudocode, cipher keys and private photo data.

## Stage15 — normal-world TEE_Operation backing objects

The original client assigns the following `TEEC_Operation` parent-pointer fields by stack-address aliases, with unique matching object offsets at the selected call sites. Original machine stores to the parent fields and the +8 size and +16 offset fields were recorded structurally, but a complete across-path memory-store proof is **not** established; they are verified original static relationships/candidates, not secure-world execution results.

| Command | TEE operation slot | Parent stack object | Local object acquisition | Declared direction |
|---|---|---|---|---|
| 6 | p0 | SP+120 | TEEC_AllocateSharedMemory at 0x1d50 | PARTIAL_INPUT |
| 6 | p1 | SP+72 | TEEC_AllocateSharedMemory at 0x1db4 | PARTIAL_INPUT |
| 6 | p2 | SP+24 | TEEC_AllocateSharedMemory at 0x1e0c | PARTIAL_INPUT |
| 2 | p0 | SP+64 | TEEC_RegisterSharedMemoryFileDescriptor at 0x17dc | PARTIAL_INOUT |
| 2 | p1 | SP+16 | TEEC_AllocateSharedMemory at 0x1838 | PARTIAL_INPUT |
| 1 | p0 | SP+80 | TEEC_RegisterSharedMemoryFileDescriptor at 0x1528 | PARTIAL_INPUT |
| 1 | p1 | SP+32 | TEEC_AllocateSharedMemory at 0x158c | PARTIAL_INPUT |

All seven parent-pointer candidates were recovered from original pointer-alias instructions and matched uniquely to the actual stack object offsets. For command 6, original stores are at 0x1ec8, 0x1ed8, 0x1ee8 (with associated param size/offset stores). For command 2, p0 parent 0x18b8 and p1 parent 0x18c4. For command 1, p0 parent 0x160c and p1 parent 0x1618. Actual TEE buffer allocation flags were not yet decoded and runtime results were not observed.

### Meaning of command2 PARTIAL_INOUT
p0's caller-side parent is an FD-registered shared-memory object. The TEE may write to it according to the declared param type. **Permission is not proof of successful decrypted output**. This is also not automatically the DSP firmware loading path; the verified file `fw_util_verify_load2ion` command2 must be distinguished from `fw_util_load` command1.

## Stage16 — outer verifier's post-service memcpy

Original outer `system/lib64/libfw_util.so` function `plt_fw_verify_load2mem_with_heap_mask` (entry 0x21d8) has three verified direct callsites:
1. `memcpy` at 0x2330: destination pointer loaded from `[x22+16]`, source `x23`, length `w24`.
2. `fw_util_verify_load2ion` at 0x2344: FD from `[x22+8]`, output-length pointer `SP+20`, third pointer `x23+64`.
3. `memcpy` at 0x23dc: destination `x20`, source loaded from the **same** `[x22+16]` field, copy length loaded from `[SP+20]`.

The CFG permits the output copy after the secure service call; additional conditional branches at 0x234c (CBZ w8) and 0x23b4 (B.LO) must be analysed before treating every call as successful. The post-TEE wrapper proves a **host-visible copy mechanism** is in the normal-world binary, but neither its runtime execution nor the returned data's plaintext/decryption identity is proved.

We should correct earlier overly general phrasing: the original normal-world interface is not entirely “TEE in with status out”; at least the command2 software-model verification wrapper has an explicit copy-back mechanism. This does **not** establish the separate DSP command1 firmware path returns decoded plaintext or that the original Eagle2 hardware MAIN CCM math is present in secure software.

## Next target

Stage17: independently trace `x20` (output-copy destination) to the original outer wrapper's public ABI input, `x22` to the ION registered buffer object, and the branch tested after the secure call to determine whether copy-back is gated by successful status and bounds. Maintain exact source SHA and truthful failure/unknown markers. No decrypted TA/DSP bytes have been obtained.

## Source checkpoints
- `hasselblad_native_audit/tee_mem_stage12/inspect_stack_aliases15.py`
- `hasselblad_native_audit/tee_mem_stage12/inspect_post_tee_copy16.py`
- `.github/workflows/hb-rea-tee-mem12.yml`

Phone camera, original X2D II hardware, Phocus Stage62+ renderer and production `main` are unchanged.
