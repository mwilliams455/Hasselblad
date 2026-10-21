# Hasselblad Photon — Work Mode Resume Checkpoint (public-safe)

Date: 21 October 2026

## Scope

Next task: restore **actual Android 9 / API 28 / ARM64 execution** of the original Hasselblad X2D II 100C AWB library and resume original-vs-owned comparisons, rather than adding synthetic approximations.

## Recovered source/evidence, private binaries withheld

The original X2D II 100C firmware 1.3.16.2 was re-extracted and checked against the historical Native1A manifest:

- Original `.cim` SHA-256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`
- Original `libaaa.so` (7,423,736 bytes) SHA-256: `7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`
- 3 companion AWB configuration files matched their original hashes.
- 9 direct Android 28 native dependencies were extracted and verified.
- 28 exported AWB functions matched exact name/address/size; 11 internal addresses contain executable code, but the internal stage names are historical labels, not exported names.
- `scene_awb_result_recalib_unit` at `0x4a39a0`: 56-byte unsigned Q12 gain recalibrator; original zero calibration return `89`, valid `0` (static instruction evidence, not runtime equivalence).

**The private binaries are retained outside this public repository.** User-facing Work handoff and binaries are in the user's private ChatGPT Library; use those sources only with authorization and appropriate Library file access. Do not commit binaries, vendor calibration or private image pixels here.

## Current reconstruction

Portable, host-tested scaffolds/source for bounded result recovery, RAW 32x32 statistics, candidate accumulation, explicit-fixture classification, optimizer caller-side updates and seven-frame comparison are in Rebuild01–05. Latest owned Rebuild05 source checkpoint commit: `0aa24fcf26d2a80e31837f4da69893f19f0d609d`.

**Still missing:** original library execution and full exact optimizer/statistics/history/atmosphere/post AWB numerical equivalence. Previous original-code test counts from the 20 October conversation are historical findings, not newly executed tests. The vendor original scene optimizer is a historical internal mapping at `0x4a8c48` (1,452 bytes). Context is 920,560 bytes, configuration is 1,502,800 bytes, passive REAWB handle is 1,000 bytes.

## Mandatory next sequence

1. Confirm access to private AWB bundle and Android 28 runtime dependencies in the user's Library; validate hashes. No proprietary uploads to GitHub.
2. Set up an ARM64 Android API 28 execution/runtime harness for original `libaaa.so`, resolve dependencies and original initialized state.
3. Execute original recalibration helper and compare it against portable code, including error/status/overflow; record genuinely new original execution cases.
4. Rebuild initialized frame/statistics/scene input, original scene optimizer and caller-side count behaviour.
5. Restore same-execution seven-frame original-versus-owned context + REAWB + status comparisons (opaque pointer identity matters).
6. Continue through historical AWB stages using the mega handoff and conversation research ledger as specifications.
7. After each bounded, fresh original-firmware comparison: immediately commit owned source, harness, test definitions, numeric outcomes and safe reports to `recovery/awb-rebuild-20261021`, then read back verified tree/blobs.

Keep `main` unchanged and maintain installed Native1C (version code 27179) until a genuinely better signed APK is validated. Full HNCS photographic colour rendering, phone calibration, and signed/headroom RAW-to-linear insertion remain separate future tasks.