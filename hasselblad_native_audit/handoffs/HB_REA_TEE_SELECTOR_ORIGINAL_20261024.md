# Hasselblad X2D II REA — original key-selection wrapper trace
24 October 2026. Isolated branch `research/rea-tee-20261024`. Not a Photon app change.

## Original-only verification
- Exact firmware: X2D II 100C 1.3.16.2, SHA-256 9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6. Downloaded temporarily, decrypted with already-established outer-CIM procedure and file hashes recorded. No new key recovery.
- REA with verified Ghidra 12.1.4 and original AArch64 Capstone static callgraph successfully exercised. [Stage5 CI](https://github.com/mwilliams455/Hasselblad/actions/runs/40104077601), [Stage6 CI](https://github.com/mwilliams455/Hasselblad/actions/runs/40104490663), [Stage7 corrected entrypoint CI](https://github.com/mwilliams455/Hasselblad/actions/runs/40104765683).
- Source/output only sanitized ELF symbol names, direct-call site identities and bounded register provenance. No vendor assembly, pseudocode, firmware bytes or decryption material published.

## Corrected actual X2D II call graph
1. Original `system/bin/dji_fw_verify` calls `plt_fw_verify_file` via dynamic PLT at ELF VA 0xb30.
2. This function is defined in `system/lib64/libfw_util.so` at 0x1ce8 (1,260 bytes). **It is not named `dji_fw_verify_file` in this X2D II release.**
3. `plt_fw_verify_file` invokes `fw_util_verify_init_ext` from `libfw_util_ca.so` at 0x1de4; it also contains a separate call to `fw_util_verify_init` at 0x1e30. The branch decision is not yet proved.
4. `fw_util_verify_init_ext` in `libfw_util_ca.so` invokes `TEEC_InvokeCommand` command **6** at 0x1ef8, after memory allocation and copy steps.
5. Original wrapper direct argument assignments to the *extended* function at 0x1de4:
   - X2 from X25
   - W3 from W23
   - X4 from X24
   - W5 from W23
   The two selector version argument positions share the identical original register W23; this is a local straight-line instruction finding, **not** proof of the TA's internal key-version interpretation.
6. Separate original X2D II memory model verification path: `plt_fw_verify_load2mem_with_heap_mask` calls `fw_util_verify_load2ion` at 0x2344, which sends TEE command **2**, not command 6. No evidence that the command 6 version settings determine command 2's selection.
7. `system/lib64/libfw_verify_util.so` has a **different** normal-world software signature route: `plt_fw_verify_file_soft` invokes `sec_cipher_ecc_sha256_verify` at 0x1960. Do not confuse this with the original secure-world TBIE DSP loader; its algorithm/acceptance conditions differ.

## What was NOT achieved
No decrypted TA, DSP, valid TBIE key, interpreted secure-world selector default, plaintext dump or original MAIN CCM per-pixel equation. Passing a name or version into TEE command 6 does not make its decryption material readable, and cannot be used to extrapolate directly to the DSP load command.

## Next proof
Trace the provenance of W23 and the other callee-saved selector registers to the original wrapper's ABI inputs, and resolve the condition choosing extended command-6 initialization versus ordinary command-3 initialization. Continue with exact TEEC_Operation paramTypes and output-buffer ownership after that. Do not repeat outer CIM and IMaH authentication/key-family inventories.

## Safe source
- hasselblad_native_audit/tee_rea_20261024/inspect_key_selectors5.py
- hasselblad_native_audit/tee_rea_20261024/rea_selectors5.py
- hasselblad_native_audit/tee_rea_20261024/inspect_verifier_topology6.py
- hasselblad_native_audit/tee_rea_20261024/prove_version_alias8.py
- .github/workflows/hb-rea-tee-audit.yml

No app code, production main, real capture images or phone settings were modified.
