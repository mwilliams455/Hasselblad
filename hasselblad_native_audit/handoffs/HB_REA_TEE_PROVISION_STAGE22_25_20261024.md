# Updated: this provisional Stage22–25 handoff is superseded

The conclusive Stage26 original-ELF CFG validation is in [HB_REA_TEE_SECOND_TA_STAGES22_26_FINAL_20261024.md](HB_REA_TEE_SECOND_TA_STAGES22_26_FINAL_20261024.md). **Use that final checkpoint for future work**; the Stage25 task described below is now completed, and the e91c TA is statically proved to be the session target of efuse_pro, pro_state and sec_debug_state. No TBIE key or secure-world plaintext was recovered.

---

# Hasselblad X2D II — REA secure-key provisioning Stage 22–24 handoff
**Research date:** 24 October 2026. **Branch:** `research/rea-tee-20261024`. Original camera, Photon production branch and Phocus Stage62 experimental colour renderer unchanged.

## Why this is a new line of investigation
Stages 1–21 already established outer-CIM decryption, RSA signature verification, IMaH-v2 PRAK/TBIE header family, seven firmware-verifier TEE commands, command6 selector/version forwarding, and normal-world command2 shared-memory copyback/status. All published TBIE candidates failed to produce validated DSP/TA plaintext. Repeating those stages cannot recover new cryptographic information.

Independent upstream DJI firmware-tools research on an **older m0801 platform** reports that many TBIE-family keys are derived inside TrustZone from ingredients including master material, public verification material and key-label descriptions; not every input necessarily resides in packaged TZOS. https://github.com/o-gs/dji-firmware-tools/wiki/Firmware-m0801

**This is a motivating hypothesis, NOT evidence of identical key derivation on Hasselblad X2D II 100C.** The aim here is to find original Hasselblad normal-world evidence without executing any eFuse or TEE operations.

## Stage 22 — entire readable system/vendor surface
Official original X2D II 100C **1.3.16.2**, 364,814,336-byte firmware SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`. Exact original transient extraction, 1,616 of 1,617 system/vendor files (636,407,776 bytes) scanned; one 78,584,752-byte file `system/etc/rand_grain_8bit_part1.bin` excluded by bound. Thus negative marker claims are restricted to **scanned bytes**.
Validated refined run: https://github.com/mwilliams455/Hasselblad/actions/runs/40114639665.
- **0** literal CryptoCell markers; **0** ARM CC310/312/630/712 string identifiers; **0** key-ladder strings in scanned files.
- A first scan's 71 eFuse hits included false matches with the English word `refuse`. A corrected boundary-aware scan returned **11** matching files. This is the authoritative refined scan.
- There are normal-world `keymaster`, generic cryptography and secure TEE references, but these do not prove an original TBIE key derivation scheme. The presence of the marker `root_key` in a generic libcrypto is not evidence of recoverable hardware root key bytes.
- The unusually interesting original eFuse interface is `system/lib64/libamt_util.so`, exact SHA-256 `63a4addc9179587363bdc8f045d9cb4686855aa413873db8b5fdcd15bdab5902`, which exports `efuse_pro`, links `libteec.so` and `libcrypto.so`, and imports TEEC client APIs.
- `system/bin/amt_test_cmd` exact SHA-256 `a634bc6759cde58af940bd168ce5c923577096e105cdcf354a25f60e9301927d` imports `efuse_pro`. The name suggests a hardware test/provisioning utility, but **its execution, meaning or connection to TBIE is not established by a name alone**.

## Stage 23 — direct eFuse/Tee callgraph, real Ghidra
Successful REA/Ghidra 12.1.4 and Capstone original-firmware run: https://github.com/mwilliams455/Hasselblad/actions/runs/40114059705.
- Original public `efuse_pro` is **STT_FUNC**, 296-byte function, ELF VA **0x2aa0**.
- The function **directly** calls `TEEC_InitializeContext` 0x2aec, `TEEC_OpenSession` 0x2b28, `TEEC_InvokeCommand` 0x2b6c, `TEEC_CloseSession` 0x2b90 and `TEEC_FinalizeContext` 0x2b98. This is a real normal-world TEE client, not simply text saying “efuse.”
- REA/Ghidra `efuse_pro` decompilation completed with valid JSON and TEEC function references; **no original decompilation/pseudocode is committed**.
- This library contains the TEEC little-endian byte representation of a **second** protected TA filename UUID, `e91c9402-64a0-470f-88e7-bf5d3c606b6a`, at original ELF file/virtual offsets **0xf120** and **0x10560**. This is not the DSP verifier UUID `09db16c0-873b-4fed-b87e-a5d2b86293a2`.
- The separate UUID match is strong evidence of a candidate TA relationship, but literal presence alone does NOT prove the original `efuse_pro` session uses this UUID.

## Stage 24 — original command IDs and OpenSession argument
Successful original-hash validation: https://github.com/mwilliams455/Hasselblad/actions/runs/40114639665.
- The `TEEC_OpenSession` **third ABI argument** `x2` is an `SP+48` stack structure in `efuse_pro`, `pro_state`, and `sec_debug_state`. The copy of actual UUID bytes into this stack structure still requires dataflow proof.
- `efuse_pro` directly sends **TEE command ID 0** (`w1=wzr`) at 0x2b6c.
- `pro_state` directly sends **TEE command ID 3** at 0x2ca0.
- `sec_debug_state` directly sends **TEE command ID 32** at 0x2e0c.
- These commands have **not** been executed on a device and have no proven relationship to the first TA's firmware/DSP decode commands (1/2/3/6). Names are insufficient to conclude that any operation reveals or programs the TBIE key.

## Stage 25 to finish
`trace_stack_uuid25.py` is committed for a focused original-ELF static analysis of the 16-byte UUID copied into the first eFuse session's `SP+48`. It should compare reconstructed public UUID bytes against the second protected TA **without reading, touching, or executing an eFuse**. Report results separately, distinguishing a path-insensitive byte match from full control-flow dominance.

## Key boundaries
- The second TA is encrypted, not decompiled; even if its UUID is matched, TEE code/key material remains protected.
- The previous normal-world first-TA transport work does not imply the second service derives TBIE.
- Original DSP firmware images are still encrypted, and *Eagle2 hardware* MAIN CCM per-pixel rendering is a separate evidence problem.
- No camera hardware access, writes, key guessing, eFuse programming, auth bypass, DRM circumvention of user content, firmware flashing, photodata export, or Photon app changes performed.

## Source & workflows
- `hasselblad_native_audit/tee_provision_stage22/audit_key_provisioning22.py`: refined bounded original software marker/symbol inventory.
- `hasselblad_native_audit/tee_provision_stage22/audit_efuse_tee23.py`: actual ELF efuse_pro/TEE callgraph and known UUID comparison.
- `hasselblad_native_audit/tee_provision_stage22/trace_efuse_session24.py`: exact x2 session argument and command IDs.
- `hasselblad_native_audit/tee_provision_stage22/trace_stack_uuid25.py`: staged public-UUID memory matching.
- `.github/workflows/hb-rea-tee-provision22.yml` and `.github/workflows/hb-rea-tee-efuse23.yml`.
