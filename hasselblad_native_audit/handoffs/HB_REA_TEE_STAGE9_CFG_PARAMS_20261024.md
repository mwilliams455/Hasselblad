# Hasselblad REA — Stage9 original command 3/6 branch and TEEC ABI

Research date: 24 October 2026, United Kingdom.
Isolation: `research/rea-tee-20261024`; Photon production main, original camera, and Stage62 experimental demosaic untouched.
Authoritative original X2D II 100C firmware: **1.3.16.2**, official CIM exact SHA-256 `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.

Successful original-firmware CI: [run 40106335670](https://github.com/mwilliams455/Hasselblad/actions/runs/40106335670), sanitised Actions artifact `Hasselblad-TEE-REA-Safe-20261024`, record `HB_REA_STAGE9_ORIGINAL_SAFE.json`. Tooling: hash-pinned original AArch64 ELF, Capstone CFG/stack provenance, REA/GNU objdump and REA/Ghidra 12.1.4. No vendor binaries or pseudocode retained in public source. First Stage9 attempt failed before reaching real analysis due only to a typo in an independent synthetic test; corrected and preflight moved ahead of firmware download.

## New verified original facts

### Branch that selects normal/extended initialization
Original `system/lib64/libfw_util.so`, `plt_fw_verify_file` at `0x1ce8`:
- `cbz x8` at **0x1dd0** discriminates the two call paths.
- Zero `x8` takes `fw_util_verify_init` at **0x1e30**, which sends command **3**.
- Nonzero `x8` reaches `fw_util_verify_init_ext` at **0x1de4**, which sends command **6**.
- Earlier `cbz x21` at **0x1d94** can exit before either initialization call; the tested CFG does not prove its full semantic predicate.
- Stage8 already established extended-path versions in the wrapper's call are both copied from original incoming `w6`. This Stage9 branch result does **not** establish where `x8` originates. Stage10 must trace it.
- Static CFG reachability does not prove any specific path was executed on hardware.

### Original TEE Client API paramTypes
Original `system/lib64/libfw_util_ca.so`. Each has exactly one detected static 32-bit store at `TEEC_Operation` offset +4, with one directly reconstructed constant. These represent standard TEE Client API parameter direction/type, **not** vendor crypto key values.

| Command | Function | TEE paramTypes | p0 | p1 | p2 | p3 |
|---|---|---|---|---|---|---|
| 1 | fw_util_load | **0x11DD** | partial input | partial input | value input | value input |
| 2 | fw_util_verify_load2ion | **0x11DF** | partial in/out | partial input | value input | value input |
| 3 | fw_util_verify_init | **0x000D** | partial input | none | none | none |
| 6 | fw_util_verify_init_ext | **0x1DDD** | partial input | partial input | partial input | value input |

The actual original `TEEC_InvokeCommand` sites are `0x162c`, `0x18d8`, `0x1b5c` and `0x1ef8`, respectively. Their stack-located TEEC_Operation pointers and paramtype stores are independently found from the original instructions. Shared-memory flags, memory sizes, contents, secure-world behaviour and possible returned plaintext require separate analysis; `PARTIAL_INOUT` is a permission/contract, not proof the TEE returned decrypted bytes.

### Relevance to original TBIE question
- The difference `0x11DD` (command1) versus `0x11DF` (command2) is real and likely explains differing memory-buffer intent; it does **not** itself establish decryption.
- Command6 has three declared input memrefs and a value input; the matching extended initialization is conditioned on `x8 != 0`.
- The actual trusted application and DSP files are still inner encrypted IMaH v2/PRAK/TBIE containers. No new signing/encryption key, secure-world code, original MAIN CCM per-pixel equation or decrypted DSP resulted.
- The software verifier `plt_fw_verify_file_soft` and embedded boot public RSA key remain separate from this protected key derivation question.

## Reproduction

- `hasselblad_native_audit/tee_rea_20261024/inspect_branch_operation9.py` (independent CFG and TEEC paramTypes verifier)
- `.github/workflows/hb-rea-tee-audit.yml` (read-only transient original firmware CI)
- Stage8 `prove_version_alias8.py` and earlier provenance handoff `HB_REA_TEE_SELECTOR_ORIGINAL_20261024.md` remain valid.

Next is the `x8` predicate provenance (Stage10), then mapping command6's three input buffer identities and actual command2/1 output-buffer ownership without exporting vendor bytes or inferring any hardware key.
