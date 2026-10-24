# X2D II REA Stage13–14 — original TEE command 6 input provenance

**24 October 2026 — completed, isolated research branch:** `research/rea-tee-20261024`.

## Original source and independent execution
The official firmware was exact hash-verified (X2D II 100C 1.3.16.2), extracted ephemerally and static-analysed without executing vendor code. Source ELF `system/lib64/libfw_util_ca.so`, SHA-256 `96e605e3940856eec88e6d17e698cebdedde0b5d26ccc2da7088ce2707d4d84b`.

- Stage13 original CI https://github.com/mwilliams455/Hasselblad/actions/runs/40108405556: private input remains private, public `HB_REA13_ORIGINAL_SAFE.json`, original `strncpy` destination and saved-source metadata verified.
- Stage14 original CI https://github.com/mwilliams455/Hasselblad/actions/runs/40108730054: 199 original AArch64 instructions and 209 CFG edges analysed to a reaching-definition fixed point; each of five selected source sites has one unique original ABI argument identity. Public `HB_REA14_ORIGINAL_SAFE.json`.
- REA original-AArch64 GNU objdump analysis also completed with parseable JSON, and no raw vendor symbols beyond the limited selected functions, instructions, plaintext, key material or photograph pixels exported.
- Scripts: `hasselblad_native_audit/tee_mem_stage12/inspect_input_chain13.py` and `inspect_cfg_sources14.py`. The latter addresses Stage13’s conservative whole-text-definition ambiguities through path-sensitive CFG reachability.

## Original command-6 argument source graph

Original `fw_util_verify_init_ext` receives three pointer/string sources and two version-word inputs:

| Purpose | Incoming ABI register | Saved register in callee | Original copy/value-write site | Allocated buffer/SP or operation slot |
|---|---|---|---|---|
| First source string | x0 | x23 | `strncpy` at 0x1d8c | `TEEC_SharedMemory` buffer from SP+120, verified first field via `ldp` at 0x1d84 |
| Second source string | x2 | x22 | `strncpy` at 0x1df0 | buffer from SP+72, verified `ldp` at 0x1de8 |
| Third source string | x4 | x21 | `strncpy` at 0x1e98 | buffer from SP+24, verified `ldp` at 0x1e90 |
| First version value | w3 | w20 | `str` at 0x1ef0 | `TEEC_Operation` p3.a, SP+272 |
| Second version value | w5 | w19 | `str` at 0x1ef4 | `TEEC_Operation` p3.b, SP+276 |

Each saved-register copy is uniquely sourced from the original incoming argument on the control-flow path reaching the referenced instruction. No original secret value or input string content was exported. Parameter type is the already-proved `0x1DDD`: three PARTIAL_INPUT memrefs plus VALUE_INPUT.

In the earlier Stage8 original *outer* `plt_fw_verify_file` wrapper the function itself passes distinct name pointers in the callee’s `x2` and `x4` positions but duplicates **the same incoming `w6` version** into both `w3` and `w5` positions. The normal-world argument contract is therefore reconstructed end-to-end for this call path; actual secure-world interpretation, key provisioning/default, whether absent names are treated specially and firmware/DSP acceptance remain unknown.

## Remaining byte-level/secure-world boundary
- Before claiming authenticated/decrypted DSP payload, must prove the actual memref parent and extent identities for command6 p0,p1,p2 and command2 p0,p1. Stage12 only established allocations and selected basic stack stores.
- The command2 declared first memref is PARTIAL_INOUT; this **does not** prove decrypted bytes return to a normal-world buffer. Its return-path read semantics remain to be investigated.
- The protected TA at UUID `09db16c0-873b-4fed-b87e-a5d2b86293a2` and original DSP images remain encrypted IMaH-v2/PRAK/TBIE containers. No valid TBIE key, secure-world plaintext or Eagle2 MAIN hardware CCM equation recovered.
- Avoid repeating known DJI PRAK signature, TBIE key list, CIM outer decryption or completed host selector discovery. Preserve Phocus Stage62+ renderer progress separately.

No original camera/phone accessed, no normal Photon output modified, no new APK and no production-branch merge.
