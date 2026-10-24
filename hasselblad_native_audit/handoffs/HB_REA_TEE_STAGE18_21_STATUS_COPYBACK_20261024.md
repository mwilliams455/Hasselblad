# Hasselblad X2D II — REA TEE status/copyback audit, Stages 18–21
Prepared 24 October 2026. Isolated research branch: `research/rea-tee-20261024`.

## Original source and scope
Firmware: official X2D II 100C 1.3.16.2, exactly 364,814,336 bytes, SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`. Original normal-world ELF `system/lib64/libfw_util.so`, SHA-256 `3e56db44845b23905355b6ef8550ff618d6b786be9de1057588d6de53db9e24d`.
All analyses read original code statically in transient GitHub Actions; no camera access, TA/DSP execution, user photographs, proprietary instruction bytes, secure keys or decompiled vendor pseudocode published. REA's original AArch64 GNU-objdump provider and bounded independent Capstone control-flow/ABI probes ran; REA/Ghidra's separate prior analyses remain verified. The exact firmware was removed from each runner after use.

## Validated source checkpoints
- Stage 18: https://github.com/mwilliams455/Hasselblad/actions/runs/40110394844 — `HB_REA18_ORIGINAL_SAFE.json`. First attempt was a Python identifier-shadowing error, corrected; no vendor inconsistency.
- Stage 19: https://github.com/mwilliams455/Hasselblad/actions/runs/40110698058 — `HB_REA19_ORIGINAL_SAFE.json`.
- Stage 20: https://github.com/mwilliams455/Hasselblad/actions/runs/40111028739 — `HB_REA20_ORIGINAL_SAFE.json`, **superseded for path-specific return values by Stage 21** because whole-function SSA merged early exits that bypass the secure call.
- Stage 21: https://github.com/mwilliams455/Hasselblad/actions/runs/40111368807 — `HB_REA21_ORIGINAL_SAFE.json`. First attempt's preflight imported Capstone before dependency installation; repaired; original-code stage passed.
- Final safe artifact: `Hasselblad-REA-TEE-Memrefs-Stage12-Safe` on Stage21 run (contains stages 12 through 21, all prior original-only receipt files).
- New code: `hasselblad_native_audit/tee_mem_stage12/inspect_post_return18.py`, `inspect_return_status19.py`, `inspect_status_provenance20.py`, `inspect_return_branches21.py`. Workflow: `.github/workflows/hb-rea-tee-mem12.yml`.

## Proven original host-side return/copy control
The normal-world `plt_fw_verify_load2mem_with_heap_mask` wrapper (AArch64) calls `fw_util_verify_load2ion` at 0x2344, which dispatches TEE command **2** in the CA library, not command1 that is used for direct firmware loading.

- `0x2348` saves the secure-service return register into `w8`.
- `0x234C` `CBZ w8`: zero branches to 0x237C, nonzero falls to 0x2350.
- **Both** branch successors can reach the post-service `memcpy` at 0x23DC. On the bounded CFG, neither result path can return ordinarily without crossing that copy.
- The later `B.LO` at 0x23B4 also has both successors reaching the output copy. Its local comparison at 0x23B0 is `CMP x2, #51`, but the original semantic source of `x2` was not established. Do **not** label this a general output-capacity gate or a security check without new data.
- Exactly one normal `RET` at 0x2418 is reachable after the TEE call in the original CFG, and 0x23DC copy dominates that observed normal return. At 0x23F8 the wrapper sets public return `w0 ← w19` **before restoring saved x19**.
- The output length `SP+20` is directly written before the secure call (from w24, 0x2220), read before service (0x2320), passed as an address into the service, and read afterward (0x23CC) for the final copy size. No further **direct SP-relative** stores to that field were observed after the call; indirect alias writes and secure-service updates were not excluded.
- **Stage21 path-rooted register analysis:** On the zero-service-status branch, the sole reaching definition of `w19` at its return-value assignment is `MOV w19, wzr` at 0x237C, so the modelled normal return value is zero. On the nonzero-service-status branch, the sole last definition is `ADD w19, w19, #32` at 0x2360. This computes a separate status; its earlier w19 input is not proven to be the raw secure-service status, and may reflect prior wrapper error mapping. Both branches still reach the host output copy.

## Correct conclusions and limits
**Architectural finding:** The normal-world command2 model verification/load-to-memory interface can copy a shared buffer into its caller's output pointer on normal returns even when the secure-service status is nonzero. This aligns with earlier third-party device observations where failure did not necessarily zero the apparent returned length, but it is NOT evidence the copied payload had been accepted or decrypted.

**Do not conflate command2 with command1**: original DSP firmware loader `fw_util_load` uses command1 with declared input-only memrefs. Proving host output for command2 does not prove the secure service would decrypt the X2D II DSP firmware through it, that another camera's signed models would be accepted, or that MAIN hardware CCM arithmetic lies in the secure program.

The original trusted application `vendor/ta/09db16c0-873b-4fed-b87ea5d2b86293a2.ta` and DSP images remain encrypted IMaH-v2/PRAK/TBIE containers. Prior signature verification and failed TBIE candidates remain settled. **No valid TBIE decryption key, TA plaintext, DSP plaintext or photographic CCM pixel equation has been recovered.** Ghidra can decompile the accessible normal-world client, not encrypted secure-world instructions.

## Next meaningful evidence gate
Generic static REA or repeated header/key-family analysis of these same host libraries is now unlikely to identify the hardware/private TBIE key. The next evidentiary breakthrough would require legally obtained original TA plaintext, a proven independent decryptor/key derivation route, or an owner-authorised, non-destructive test against a functioning compatible original secure service, with no unapproved firmware writes, device patching or plaintext exports. Until one of these exists, keep this branch frozen and continue the independent Photon/Phocus demosaic and colour-renderer work.

Production `main`, original camera, Stage62+ experimental renderer and normal Photon saved-photo colour remained unchanged.
