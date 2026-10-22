# Stage5 source-only colour-basis checkpoint — 22 October 2026

- Public scoped implementation under `hasselblad_native_audit/phone_input_20261021/shader_basis_stage5/`.
- Source-only host GCC O0/O2/Clang independent numerical oracle: PASS; 15 negative/nonmutation cases per host configuration; ASan/UBSan positive+negative probe PASS.
- Private hash-bound Domain3 original RAW replay: PASS; original RAW and hypothetical Photon-normalised FP16 map interpretations separately retain Stage4 ABSTAIN; no render neutral.
- Android ARM64 API28 with NDK27: PASS, 16KB LOAD alignment `[16384,16384,16384]`.
- No Android JNI/Camera2/GL GPU parity test, no APK, no render or WB change.
- `main` and production Photon colour files unchanged; recovery branch only.
- Next: bounded GPU readback under identical shader/RAW frame, then actual measured neutral+nonneutral target training, automatic controller, and independent HNCS photographic rendering.
