# Hasselblad X2D II REA — confirmed second eFuse/secure-debug TEE application
**Definitive research handoff — 24 October 2026, Stages 22–26**  
**Repository:** https://github.com/mwilliams455/Hasselblad  
**Isolated branch:** `research/rea-tee-20261024`  
**No changes to production `main`, original camera, Photon photography or experimental Phocus Stage62+ renderer.**

## 1. What we investigated and why

Do **not** restart the completed October 23 and October 24 work on outer-CIM extraction, RSA signature verification, IMaH v2 PRAK/TBIE envelope parsing, failed published TBIE key trials, or the first TEE client's commands 0–6. Those earlier stages accurately establish the encrypted TA/DSP boundary but did **not** recover decrypted secure-world instructions.

An independent DJI firmware-tools note for an older m0801 platform describes TrustZone CryptoCell key derivation needing material not entirely contained in packaged TZOS; this motivated checking the X2D II, **not** assuming the same hardware implementation. Reference: https://github.com/o-gs/dji-firmware-tools/wiki/Firmware-m0801

The new original-firmware objective was to find independent **eFuse / secure key provisioning** software and verify whether it truly invokes a protected TEE service.

## 2. Original input provenance

- **Firmware:** official Hasselblad X2D II 100C 1.3.16.2, 364,814,336 bytes.
- **Firmware SHA-256:** `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.
- Original extracted `system/lib64/libamt_util.so`: SHA-256 `63a4addc9179587363bdc8f045d9cb4686855aa413873db8b5fdcd15bdab5902`, 134,368 bytes, AArch64 ELF.
- Original `system/bin/amt_test_cmd`: SHA-256 `a634bc6759cde58af940bd168ce5c923577096e105cdcf354a25f60e9301927d`, 68,392 bytes, AArch64 ELF.
- All original firmware files transiently downloaded, checked, extracted and deleted in GitHub Actions. Manufacturer code and devices were never executed or modified.

## 3. Stage22 — careful original system/vendor provisioning inventory

Original official firmware scan: **1,616 / 1,617 files**, 636,407,776 bytes. The lone excluded file by 64 MiB per-file bound is a 78,584,752-byte grain-data file `system/etc/rand_grain_8bit_part1.bin`. Negative observations apply only to scanned bytes.

Refined scan corrected a noisy `efuse` substring search that also matched `refuse`:
- **11** files with credible bounded eFuse literal markers (previous 71 unfiltered hits were NOT valid evidence).
- No literal `CryptoCell`, `CC310/312/630/712` or `key_ladder` markers found.
- Generic `root_key`, `HKDF`, `keymaster` strings do not establish original TBIE/hardware key derivation.
- `libamt_util.so` exports `efuse_pro`, depends on `libteec.so` and `libcrypto.so`, and imports seven standard TEEC functions. `amt_test_cmd` imports `efuse_pro`.

Refined original CI and archive: https://github.com/mwilliams455/Hasselblad/actions/runs/40114639665 (a newer final archive also includes Stage25/26).

## 4. Stage23 — actual eFuse function invokes TEE

Genuine REA/Ghidra 12.1.4 and Capstone static original ELFs: https://github.com/mwilliams455/Hasselblad/actions/runs/40114059705.
- `efuse_pro` is a real defined `STT_FUNC`, function entry `0x2aa0`, 296 bytes.
- It directly calls `TEEC_InitializeContext` at `0x2aec`, `TEEC_OpenSession` at `0x2b28`, `TEEC_InvokeCommand` at `0x2b6c`, `TEEC_CloseSession` at `0x2b90`, and `TEEC_FinalizeContext` at `0x2b98`.
- REA/Ghidra successfully decompiled this **normal-world client function** privately; neither original pseudocode nor any key material was published.
- The `libamt_util.so` ELF includes two TEEC little-endian copies of encrypted trusted-application UUID `e91c9402-64a0-470f-88e7-bf5d3c606b6a`, at file/virtual addresses `0xf120` and `0x10560`.

## 5. Stage24 — original TEE command IDs and stack UUID argument

Original static audit: https://github.com/mwilliams455/Hasselblad/actions/runs/40114639665

| Function | TEEC_OpenSession VA | TEEC_InvokeCommand VA | Command ID | UUID argument |
|---|---|---|---:|---|
| `efuse_pro` | 0x2b28 | 0x2b6c | **0** | x2 = SP+48 |
| `pro_state` | 0x2c50 | 0x2ca0 | **3** | x2 = SP+48 |
| `sec_debug_state` | 0x2db8 | 0x2e0c | **32** | x2 = SP+48 |

The three session calls have a stack-resident UUID, not a direct pointer to the original literal. Stage24 alone did **not** prove the literal's relationship to that stack memory.

## 6. Stages25–26 — original UUID copy and CFG dominance proved

- Stage25 original CI: https://github.com/mwilliams455/Hasselblad/actions/runs/40115045565
- **Stage26 final original CI: https://github.com/mwilliams455/Hasselblad/actions/runs/40115428599**. Final sanitised archive: `Hasselblad-REA-Key-Provisioning-Stage22-Safe`; contains `HB26_ORIGINAL_SAFE.json` and prior Stage22/24/25 receipts.

Exact original `LDR q0` of the known public TA UUID, 16-byte `STR q0` into SP+48 and TEEC session call:

| Function | Literal UUID load | SP+48 store | Open session | CFG proof |
|---|---|---|---|---|
| `efuse_pro` | 0x2ae4 | 0x2ae8 | 0x2b28 | PASS |
| `pro_state` | 0x2c0c | 0x2c10 | 0x2c50 | PASS |
| `sec_debug_state` | 0x2d70 | 0x2d74 | 0x2db8 | PASS |

For **all three**, Stage26 established:
- The original 16-byte literal exactly matches the encrypted TA's filename UUID `e91c9402-64a0-470f-88e7-bf5d3c606b6a`.
- The literal load dominates the corresponding stack write.
- The stack write dominates the `TEEC_OpenSession` call.
- There is **no intermediate store overlapping the 16-byte UUID structure**.
- `TEEC_OpenSession` receives the SP+48 structure via its standard UUID ABI argument x2.

**Definitive normal-world conclusion:** The original X2D II `efuse_pro`, `pro_state` and `sec_debug_state` functions specifically target the second protected TA **e91c9402...ta**; this is no longer merely a shared filename or accidental matching literal. It remains static source evidence, not a physical-device runtime session.

## 7. What this does NOT prove

- The second encrypted TA's plaintext, semantics, hardware APIs or presence of a TBIE decrypting key are **not** recovered.
- The labels eFuse/provision/state/debug and their standard TEE calls **do not prove** that secure-app command 0 reads, leaks, derives or even manages the TBIE key. It may belong to manufacturing/security-state controls.
- The first protected DSP firmware-verification TA `09db16c0-873b-4fed-b87e-a5d2b86293a2.ta` remains **separate**, with its own encrypted code and loading protocol. Nothing here proves the two trusted applications share key material.
- No `CryptoCell` literal in readable scanned files does **not** prove CryptoCell absence inside encrypted TOS, silicon, or secure-world code.
- No decryption, fuse programming, authentication bypass, firmware modification, camera access, or Photoshop/Photon photo pipeline update was performed.

## 8. Specific next work

**Priority 1, remaining software-only:** Static-inspect original `efuse_pro` command 0 `TEEC_Operation` parameter types, input/output direction, and return semantics, together with `pro_state` command 3 and `sec_debug_state` command 32. Establish whether this is **eFuse programming**, **security-state query**, or key retrieval. Never execute `efuse_pro` on physical hardware: changing OTP/eFuses may be irreversible.

**Priority 2, evidence gate:** To determine a TBIE key derivation formula inside secure world, obtain legally available, independently validated TA plaintext or owner-approved device-secure-world evidence. REA can decompile the already readable Android-side functions; it cannot decompile encrypted TA bytes or recover unknown hardware root secrets on its own.

**Separate priority:** Continue active Phocus Stage62+ portable image renderer for an APK independently. Eagle2 hardware MAIN CCM pixel semantics are not guaranteed to be inside either protected TA.

## 9. Reproducible scripts and CI
- `hasselblad_native_audit/tee_provision_stage22/audit_key_provisioning22.py`
- `hasselblad_native_audit/tee_provision_stage22/audit_efuse_tee23.py`
- `hasselblad_native_audit/tee_provision_stage22/trace_efuse_session24.py`
- `hasselblad_native_audit/tee_provision_stage22/trace_stack_uuid25.py`
- `hasselblad_native_audit/tee_provision_stage22/prove_uuid_cfg26.py`
- `.github/workflows/hb-rea-tee-provision22.yml`
- `.github/workflows/hb-rea-tee-efuse23.yml`

**Final current status:** Both TA client targets are mapped from original firmware. The eFuse-related second TA is identified and its host session calls structurally proved. **TBIE decryption still unavailable**.
