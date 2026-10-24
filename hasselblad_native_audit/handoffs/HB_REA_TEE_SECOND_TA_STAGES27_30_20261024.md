# Hasselblad X2D II — REA second-TA eFuse ABI, Stages 27–30
**24 October 2026 | Isolated branch:** `research/rea-tee-20261024`

## Objective and provenance
Continue from the definitive [Stage 22–26 handoff](HB_REA_TEE_SECOND_TA_STAGES22_26_FINAL_20261024.md), which independently proved `efuse_pro`, `pro_state` and `sec_debug_state` open secure sessions with protected trusted application `e91c9402-64a0-470f-88e7-bf5d3c606b6a.ta`. The objective here was to determine **what the three original host-side TEE commands expose**, without inferring key recovery from names, headers or the presence of secure-world calls.

Original X2D II 100C **1.3.16.2** firmware (exact official SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`) was verified and extracted only in ephemeral GitHub Actions. Target original AArch64 ELF: `system/lib64/libamt_util.so`, SHA-256 `63a4addc9179587363bdc8f045d9cb4686855aa413873db8b5fdcd15bdab5902`. No device, eFuse operation, secure-world program or vendor firmware was executed. No key bytes or vendor pseudocode published.

### Independent verification
- **Stage 27:** [successful original-firmware run 40116207698](https://github.com/mwilliams455/Hasselblad/actions/runs/40116207698), report `HB_STAGE27_ORIGINAL_SAFE.json`.
- **Stage 28:** [successful original-firmware run 40116541394](https://github.com/mwilliams455/Hasselblad/actions/runs/40116541394), report `HB_STAGE28_ORIGINAL_SAFE.json`.
- **Stage 29:** [successful original-firmware run 40116851667](https://github.com/mwilliams455/Hasselblad/actions/runs/40116851667), report `HB_STAGE29_ORIGINAL_SAFE.json`.
- **Stage 30:** [final successful original-firmware run 40117098729](https://github.com/mwilliams455/Hasselblad/actions/runs/40117098729), report `HB_STAGE30_ORIGINAL_SAFE.json`. **Its safe artifact ZIP also includes every Stage27–29 report.**
- All four runs used bounded independent original AArch64 Capstone/ELF analysis. The REA GNU objdump provider also verified the actual original binary and emitted parseable JSON on the focused workflow. Earlier Stage23 Ghidra 12.1.4 decompiled `efuse_pro` successfully, privately.

## Verified TEE operation types
All original `TEEC_InvokeCommand` sites take `x2` pointing to an operation structure beginning at **SP+72**. This is a normal-world ABI observation, not TA implementation.

| Host function | Original invoke VA | TEE command | Original `TEEC_Operation.paramTypes` | Proven declared direction |
| --- | --- | --- | --- | --- |
| `efuse_pro` | 0x2b6c | 0 | **UNRESOLVED** | Do not invent absence or input/output direction |
| `pro_state` | 0x2ca0 | 3 | **0x0002** | p0 `VALUE_OUTPUT` (32-bit words); p1–p3 `NONE` |
| `sec_debug_state` | 0x2e0c | 32 | **0x0002** | p0 `VALUE_OUTPUT` (32-bit words); p1–p3 `NONE` |

The original `pro_state` function stores the literal `0x0002` into paramTypes at `SP+76` at VA **0x2c98**. `sec_debug_state` likewise stores `0x0002` at **0x2e04**. These are actual constant stores, not inferences from function labels.

### Command 0 is not proved to be paramTypes=0
- Stage27: direct SP scalar writes did **not** identify a write to the operation's `SP+76` paramTypes field.
- Stage28: widened to AArch64 scalar pairs, wider SIMD and vector-zero candidates; none were identified overlapping the operation region before the original InvokeCommand.
- Stage29: tracked SP address aliases, recognised host `memset`/`bzero`/explicit zeroing calls and indirect stores. **No overlapping operation writes could be proven**. Two other opaque host calls with pointer arguments remained in scope.
- Therefore **do not** claim the structure is zero-initialised, that command0 has no parameters, or that it accesses TBIE secrets. Static code-analysis coverage and possible library side effects still limit the proof.

## What the normal-world state queries do with outputs (Stage30)
Stage30 checked direct accesses after the exact original `TEEC_InvokeCommand` sites to the first 32-bit p0 `VALUE_OUTPUT` word at `SP+80`:
- `pro_state`: original 32-bit read `w19 ← [SP+80]` at VA **0x2cc8**. The original normal return writes `w0 ← w19` at **0x2d08** before return at `0x2d1c`. This is a strong structural returned-state-value path; runtime success/actual value still not observed.
- `sec_debug_state`: reads `w3 ← [SP+80]` at **0x2e30**, but normal return writes `w0 ← w20` at **0x2e8c** before return at `0x2ea0`. The output value and public return status are distinct in the directly observed instructions. Do not assume they are equal.
- `efuse_pro`: no direct post-invocation load of `SP+80`/`SP+84` found. Normal return register receives `w19` at **0x2bac**, return at `0x2bc0`. No TEE plaintext or key output demonstrated.

All three functions perform `TEEC_CloseSession` and `TEEC_FinalizeContext` after the secure request. None of the two query operations advertises a memory buffer for carrying firmware images or substantial decrypted cryptographic output.

## Decryption relevance

The second TA is **confirmed as the target of eFuse/security state functions**, but nothing in the readable host ABI proves a hardware-root-key export, TBIE key derivation, decrypted TA memory path, DSP processing or MAIN CCM reconstruction. Commands 3 and 32 have only a small value-output ABI. Command0 remains unspecified by this static evidence. Neither command0 nor the other two functions were ever invoked on a physical camera, and **they must not be invoked speculatively**, because eFuse/OTP operations can be irreversible.

The earlier **first TA** at UUID `09db16c0-873b-4fed-b87e-a5d2b86293a2` handles firmware verification/loading. Its secure-world instructions remain encrypted and its known TBIE attempts unsuccessful. The separate normal-world command2 copyback mechanism from Stages 12–21 does not prove original DSP command1 returns plaintext.

**Research conclusion:** Stage27–30 substantially narrows the second TA normal-world contract and makes it a poor demonstrated path to TBIE plaintext. No valid decryption key, TA/DSP plaintext, camera-side capture evidence or pixel-equivalent Hasselblad MAIN CCM has been recovered. Without genuinely new secure-world evidence, further reconstruction of the same normal-world call sites is unlikely to solve the encrypted key.

## Recommended next meaningful dependency
1. If new trustworthy, owner-authorised secure-world evidence or a decrypted original TA becomes available, compare its **actual** key-provisioning and firmware-verification code with the two established UUID/command interfaces.
2. Otherwise, reserve this track and prioritise the **independent Stage62+ Photon/Phocus renderer** and hardware-independent colour reconstruction, which can progress without exposing protected secrets. Do not repeat the prior CIM, PRAK, TBIE signature/marker or public key-candidate tests.

### Scripts and workflow
- `hasselblad_native_audit/tee_provision_stage22/inspect_efuse_contract27.py`
- `hasselblad_native_audit/tee_provision_stage22/inspect_wide_zero28.py`
- `hasselblad_native_audit/tee_provision_stage22/inspect_op_alias29.py`
- `hasselblad_native_audit/tee_provision_stage22/inspect_return_values30.py`
- `.github/workflows/hb-rea-efuse-contract27.yml`

Original firmware, camera, Photon production main, APK and Phocus Stage62 source are unchanged.
