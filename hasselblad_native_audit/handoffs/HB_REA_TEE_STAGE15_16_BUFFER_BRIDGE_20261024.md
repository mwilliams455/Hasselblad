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

## Stage17 — confirmed actual caller output-copy destination

Successful original-firmware CI: [run 40109612443](https://github.com/mwilliams455/Hasselblad/actions/runs/40109612443). Saved safe artifact `Hasselblad-REA-TEE-Memrefs-Stage12-Safe`, report `HB_REA17_ORIGINAL_SAFE.json`. Source `hasselblad_native_audit/tee_mem_stage12/inspect_host_return17.py`.

The original `plt_fw_verify_load2mem_with_heap_mask` wrapper at `0x21d8` contains **146 AArch64 instructions**. New branch-sensitive reaching-definition analysis, invalidating incoming ABI caller-saved registers across external calls, proves:

- The pre-service `memcpy` source `x23` has a single true reaching definition `mov x23,x0` at 0x2204, sourcing the original wrapper's incoming **x0** argument (the input pointer).
- The post-service `memcpy` destination `x20` has a single true reaching definition `mov x20,x2` at 0x222c, sourcing the original wrapper's incoming **x2** argument (the caller-supplied output pointer).
- The two `memcpy` calls share the same mapped-memory field at `[x22+16]`, and the secure call receives the corresponding file descriptor field at `[x22+8]`. `x22` is assigned from a return-register `x0` at 0x2298; the precise producing allocation symbol has **not** been independently tied by this report.
- The secure call `fw_util_verify_load2ion` at 0x2344 receives a pointer to `SP+20` as its second argument. The subsequent output `memcpy` at 0x23dc reads its copy length from that same `SP+20` stack cell. The static path does not establish whether that value was modified by the service, nor identify the bytes' actual contents.
- A `CBZ w8` at 0x234c follows a `mov w8,w0` from the secure call's returned register, but **both branches** have some CFG path to the output copy. Consequently we do NOT claim that this one test gates copying exclusively on success. Another `B.LO` at 0x23b4 appears before the copy; full path outcome and error semantics remain open.
- The source length `w24` at the initial input copy was unresolved by bounded path analysis; do not claim a particular public ABI length slot from Stage17 alone.

**Conclusion:** A normal-world software wrapper can structurally copy potentially TEE-modified FD-backed shared-memory content into an explicit caller-provided output pointer. This is a meaningful architectural result for command2 **memory model verification/loading** and corrects any general claim that every TEE request returns status only. It is NOT evidence that encrypted `ss_dsp0.fw`, other DSP images, or the separate encrypted TA have been decrypted; it does NOT show command1 original firmware load returns plaintext or disclose the TBIE secret.

This is a static proof of a potential transfer mechanism, not physical-camera validation. No decrypted output bytes were observed, no camera contacted, and no binary or key material released to GitHub.

### Decision and next dependency

Original normal-world command6 selectors, versions and p0–p2 input allocations are sufficiently mapped. Command2's host-visible copy path is likewise located. Without the target original secure application or an authorised working X2D II that accepts an exact firmware/model file, **REA static analysis cannot prove the protected key material or decrypt the TA/DSP**. Any future live test would require explicit user/device-owner permission, a non-destructive plan and controls prohibiting unintended firmware installation; no such test was performed. The Phocus renderer continues independently from these secure-firmware findings.

Do not repeat outer CIM key discovery, existing RSA verification, IMaH key-family inventory or older failed TBIE key trials.
