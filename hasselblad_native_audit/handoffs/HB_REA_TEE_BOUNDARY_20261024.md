# Hasselblad X2D II — REA TEE Boundary Result (24 October 2026)

This checkpoint resumes *after* the October 23 outer-CIM extraction and client loader tracing. This is read-only static research, not a DSP/TA decryption claim.

## Runs and source
- Original official X2D II 100C firmware 1.3.16.2, 364,814,336 bytes, transiently fetched and original digest verified.
- Research branch: research/rea-tee-20261024
- Initial CI: https://github.com/mwilliams455/Hasselblad/actions/runs/40100986300
- Refined CI: https://github.com/mwilliams455/Hasselblad/actions/runs/40101253381
- Exactly 1,617 system/vendor files, 714,585,896 bytes scanned.
- REA CLI GNU-objdump provider genuinely executed and returned parseable JSON for five original AArch64 host binaries (ss_dsp_manager, libdsp_frwk.so, libfw_util.so, libfw_util_ca.so and libteec.so). This is not secure-world disassembly.

## TEE findings
- system/lib64/libfw_util_ca.so: 68,112-byte AArch64 ELF, directly depends on libteec.so and imports eight TEEC symbols: AllocateSharedMemory, CloseSession, FinalizeContext, InitializeContext, InvokeCommand, OpenSession, RegisterSharedMemoryFileDescriptor, ReleaseSharedMemory.
- TA UUID 09db16c0-873b-4fed-b87e-a5d2b86293a2: within the scanned original content, the raw TEEC little-endian UUID occurs only in libfw_util_ca.so.
- vendor/ta/09db16c0-873b-4fed-b87ea5d2b86293a2.ta: 207,360 bytes; IMaH encrypted container.
- vendor/ta/e91c9402-64a0-470f-88e7bf5d3c606b6a.ta: 272,128 bytes; IMaH encrypted container.
- Four encrypted original DSP assets retain IMaH magic: ask_dsp.img 140,928 bytes; ss_dsp0.fw 6,100,480 bytes; ss_dsp1.fw and ss_dsp2.fw 5,838,336 bytes each.

## Interpretation and block
The earlier stubbed-TEE trace already established that the normal-world loader passes full encrypted DSP firmware to the identified TEE UUID without exposing a decrypted output buffer to Android. This new original-firmware REA audit confirms the true client-side dependency and identifies the corresponding encrypted TA on disk. Neither TA nor DSP payload is decrypted; published TBIE keys previously failed validation. RSA signature verification is separate from decryption.

The TA executable instructions are unavailable until valid plaintext or sanctioned original-device secure-world evidence exists. REA/Ghidra can analyse real decoded code but cannot solve AES encryption on its own. The MAIN CCM may be a separately implemented Eagle2 hardware block, so DSP decryption alone would not establish its per-pixel maths.

## Reproduction and confidentiality
- Original-only read-only scanner: hasselblad_native_audit/tee_rea_20261024/inspect_tee_boundary.py
- GitHub workflow: .github/workflows/hb-rea-tee-audit.yml
- Refined safe artifact: Hasselblad-TEE-REA-Safe-20261024 (Actions run 40101253381)
- The workflow removes original files and publishes only sanitized status/paths/byte sizes/import names; never firmware bytes, keys, source disassembly or private photographs.
- Normal Photon photographs, production main and experimental Stage61–62 renderer code are unchanged.

**Result: TEE container identified, REA executed, secure-world plaintext not recovered.**

## Final original IMaH header audit (run 40101683377)
Third successful REA/static runner: https://github.com/mwilliams455/Hasselblad/actions/runs/40101683377

The independently parsed, bounded, cleartext 192-byte IMaH-v2 headers in **both** TA files and **all four** DSP assets are internally size-consistent:
- encryption FourCC: TBIE (six of six)
- signature/authentication key FourCC: PRAK (six of six)
- signature length: 384 bytes (six of six)
- IMaH header version field: 2 (six of six)
- TA files: one chunk each, header 224 bytes, payload lengths 206,752 and 271,520 bytes.
- DSP assets: four chunks each, header 320 bytes.
- Exactly matching file/declared-header-plus-signature-plus-payload lengths on all six.

These fields verify the *declared key family* and coherent container framing. They are not decrypted TA or DSP code and do not establish a known available TBIE instance. Do not repeat public TBIE key guesses that failed prior validation, and do not mistake the PRAK public signing key for a decryption key.

Safe third run artifact: Hasselblad-TEE-REA-Safe-20261024, containing only metadata and REA invocation receipts.
