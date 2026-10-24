# Hasselblad X2D II — REA secure key-path checkpoint, 24 October 2026

## What is new (beyond the completed October 23 IMaH/TBIE work)

Original X2D II 100C 1.3.16.2, size and SHA-256 verified in GitHub Actions, privately extracted and analysed without executing or publishing original firmware. This stage did not repeat signing-key guesses, extract a new key, modify the camera, or change Photon.

- First actual REA disassembly plus independent bounded Capstone call-site analysis: [run 40102692860](https://github.com/mwilliams455/Hasselblad/actions/runs/40102692860).
- All seven command IDs, including the zero register proof: [run 40102917167](https://github.com/mwilliams455/Hasselblad/actions/runs/40102917167).
- Pinned official Ghidra 12.1.4, SHA-256 checked, Java 21: REA/Ghidra decompiled the original normal-world functions named fw_util_verify, fw_util_load and fw_util_verify_init_ext, with three successful JSON evidence outputs: [run 40103185730](https://github.com/mwilliams455/Hasselblad/actions/runs/40103185730).
- REA/Ghidra analyses refer to the normal-world **libfw_util_ca.so**, *not* the encrypted trusted application or hardware cryptography. No original decompilation or vendor source bytes were published.

## Recovered real direct TEEC_InvokeCommand dispatch table

These values were read from original AArch64 W1 register-setting instructions at the call sites. All mapped to actual ELF functions; zero is set from the WZR architectural zero register. The proof is local straight-line static register assignment, not a successful secure-world execution.

| Host symbol | TEEC command ID | Original call site (ELF VA) |
| --- | ---: | --- |
| fw_util_verify | 0 | 0x1244 |
| fw_util_load | 1 | 0x162c |
| fw_util_verify_load2ion | 2 | 0x18d8 |
| fw_util_verify_init | 3 | 0x1b5c |
| fw_util_verify_update | 4 | 0x20a8 |
| fw_util_verify_final | 5 | 0x2380 |
| fw_util_verify_init_ext | 6 | 0x1ef8 |

The same original normal-world library has 65 direct TEEC_* call sites including session setup, memory registration/allocation and cleanup (not 65 decryption commands). Zero direct imports matching selected host-side crypto function names were recorded; this does not rule out statically linked algorithms or secure-world cryptography.

## Original boot-area / TOS classification

The existing official OTA actually contains:
- bootarea.img, 557056 bytes, two embedded IM*H headers at byte offsets 1024 (0x400) and 233472 (0x39000), no ELF magic discovered within that file.
- tos.img, 462272 bytes, beginning with IM*H, no embedded ELF magic discovered.

This does not prove absence of raw executable code or keys; it establishes that no ordinary, immediately decompilable ELF is exposed in these two stored images. Boot-area RSA *public verification* material previously recovered is not a TBIE decryption key.

## Independent cross-generation lead (unverified for this exact X2D II procedure)

A third-party static study of X2D generation 1 versus X2D II original host tools reports that command 6 can carry authentication and decryption **material names and versions** into the TEE initialization operation. It independently records command 2 for verify/load-to-ION, its parameter types 0x11df and that same session UUID across the two generations. It also warns that version arguments in one generation's outer wrapper are not necessarily forwarded independently. These are **external claims**, not our direct new X2D II semantic or key-version proof.

Reference: https://github.com/radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions/blob/main/x2d/object-recognition/research/ORIGINAL-NATIVE-ADAPTATION.md

## Next efficient investigation

1. X2D II-specific original-code review of how fw_util_verify_init_ext receives and copies material FourCC and explicit/default version numbers, and which public caller reaches it. Separate command 6's *file verification initialization* from command 2's *memory loading* and command 1's *firmware loading*.
2. Recover the TEE_Operation paramTypes and returned buffer-direction semantics from the **original**, where statically derivable; don't assume userland ever sees plaintext.
3. If the original normal-world selection path is fully mapped, report exact unknown secure-world key source. A protected .ta cannot be decompiled without legitimate plaintext. A real X2D II may still be needed for authorised secure-world measurements, but this is not yet logically proven necessary.
4. MAIN CCM hardware equation remains distinct from DSP/TA encryption. Continue Phocus Stage62+ separately.

## Reproducible research source

- hasselblad_native_audit/tee_rea_20261024/trace_tee_keypath.py
- hasselblad_native_audit/tee_rea_20261024/rea_decompile_tee.py
- .github/workflows/hb-rea-tee-audit.yml

Original binaries, private calibration and pseudocode are only handled ephemerally by Actions and are removed before the safe ZIP is published. App, main and camera untouched.

**Status: real REA/Ghidra function analysis succeeded; original TA and DSP still encrypted; valid TBIE plaintext key material was NOT recovered.**
