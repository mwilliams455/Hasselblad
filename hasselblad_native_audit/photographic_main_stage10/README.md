# Stage10 — MAIN_3DLUT pixel-format discrimination (no photographic rendering)

## Scope

This owned, synthetic-only research tool is **not** a Hasselblad photographic LUT decoder. It was created after the Stage8 Android JNI profile preparation returned PASS on the phone. It is designed to specify what *future* ISP pixel measurements would need to discriminate between alternative interpretations of a 6,144-word packed 3D LUT.

**Do not infer camera MAIN = display.** Stage9 established the **display** `libduml_hal.so` decoder and trilinear sampler against original native synthetic test outputs. Previous camera research established that the **MAIN** `librcam.so` profile preparation produces 6,144 packed uint32 words, which the kernel submits without reordering. The equality of size is not proof of identical layout, sampling, transfer domain or rounding.

Current MAIN photos also use `MAIN_CCM` and `MAIN_GAMMA` in the audited still configurations. Their parameter preparation has independently verified original-code references, but the complete pixel equations, scale and composition order are not proved. `MAIN_HNCS` is bypassed in the explicitly examined reprocessing segments; that does not mean the camera lacks a Hasselblad natural colour treatment.

## Reproducible results

Run from repository root:

```sh
python3 hasselblad_native_audit/photographic_main_stage10/src/main_format_discriminator.py --self-test
python3 hasselblad_native_audit/photographic_main_stage10/src/main_format_discriminator.py \
  --stage9-source hasselblad_native_audit/photographic_pixel_stage9/src/hb_display_lut16.c \
  --output /tmp/stage10-main-format-probes.json
```

The script requires a C11 compiler to compile the unchanged, portable Stage9 DISPLAY reference. It validates all 4096 display nodes and all 32 chosen RGB inputs against the portable C implementation before comparing alternatives. The artifact SHA pins the deterministic **synthetic** table; it contains no X2D IQ data or photographs.

The model alternatives are deliberately hypothetical:

1. `display_planar_b_fast_trilinear` — the independently proved display decoder and trilinear implementation.
2. `node_interleaved_rgb_trilinear` — a possible 16-bit-per-component interleaved packed representation of the same extent.
3. `display_planar_r_fast_trilinear` — a different axis stride/parity choice.
4. `display_planar_bgr_banks_trilinear` — a different bank/component order.
5. `display_planar_b_fast_tetrahedral` — the display storage interpreted with tetrahedral rather than trilinear interpolation.

The four alternative implementations are mathematical counterexamples, not claims that the original MAIN hardware uses any one of them. Any of these formats might be physically implausible once the real MAIN interface is found; they are included to demonstrate why a 24 KiB size match does not determine the colour result.

The 32 inputs include exact cube corners, on-grid points, off-grid fractional points, and near endpoints. The generated report includes an eight-probe subset chosen to produce large cross-model differences on the synthetic table.

## Mandatory next evidence gate

Before choosing a MAIN implementation, obtain **at least one MAIN-linked pixel oracle** that provides all of:

- Exact submitted 6144-word LUT table, its source hash and the selected camera mode, output gamut and profile-preparation state.
- Evidence that those words were submitted to the MAIN LUT register/block (historical register ID 2998, physical address 0xf3208000), not a display colour controller.
- Precisely known RGB input values **at the MAIN LUT input stage**, with gamma/CCM effects either disabled under a proven instrumented mode or numerically resolved, and verified output samples after the LUT at the correct quantization stage.
- Exact input code range, coordinate normalization, endpoints, interpolation or dither state and any clipping/rounding.
- Multiple asymmetric test nodes plus off-grid inputs that distinguish the candidate layouts and interpolation rules.

A photo that merely looks Hasselblad-like or a pair of CAMERA/JPEG images under different light is not an acceptable LUT hardware oracle. Natural-photo matching can be used later for broader validation, after the pixel stages and phone sensor adapter have independently established domains.

## Boundaries

- No vendor firmware bytes, library, hardware table or user photo are included or committed.
- No sensor-to-Hasselblad calibration is asserted.
- No renderer, RAW, DNG, JPEG, native camera hook or app code is changed by Stage10.
- No phone test is necessary for this host-only discriminatory mathematics.
- The Stage8 phone PASS is preserved separately as private evidence; this source-only research does not change build 27186.

## Evidence provenance

- `hasselblad_native_audit/photographic_path/PHOTOGRAPHIC_PATH_FINDINGS.md`
- `hasselblad_native_audit/main_colour_20261019/MAIN_COLOUR_CHECKPOINT.md`
- `hasselblad_native_audit/pixel_contract_20261019/PIXEL_CONTRACT_FINDINGS.md`
- `hasselblad_native_audit/pixel_contract_20261019/display_sampler_native_execution.json`
- `hasselblad_native_audit/photographic_pixel_stage9/STAGE9_STUDY_MANIFEST.json`

These references contain archived earlier **original vendor native executions** and the explicit absent MAIN pixel evidence. Stage10 does not rerun a vendor binary.
