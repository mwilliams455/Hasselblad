# Stage68: independent colour-site RAW gradients (bounded scalar path)

Stage68 reconstructs the eight RAW16 directional gradient codes computed **inline** before both `GetGreenAtRedFirst` calls at the red and blue CFA sites in the original scalar `InterpolateRGB` path. This closes the mathematical distinction left open in Stage67. It is **not yet an independent complete demosaic**, an original-CPU execution check, a device build, or evidence of physical phone-to-Hasselblad colour matching.

Source baseline: [Stage67 `b4f26057`](https://github.com/mwilliams455/Hasselblad/commit/b4f26057f53d0f20a14ef5ca65c2908ad5f92018). Earlier native-verified Stage63 components remain the upstream contract; Stage64/65 original-CPU tests and the Stage66 pixel-loop integration are still outstanding. The phone baseline remains Stage58 (`0.1-hb-rawprep58` / `27197`), with normal capture unchanged and no HDR, stacking, or video.

## Reconstructed operation

`colour_gradient68.c` / `.h` use standard C11 only, with no vendor code, LUTs, calibration, or photograph-dependent constants. Output is ordered **N,E,S,W,NE,SE,SW,NW** as eight signed 16-bit codes. `hb_inline_raw_gradient67` is reused for N/E/S/W because those equations are the same at the studied green and colour CFA sites. However, at the colour sites **each diagonal combines six unsigned two-pixel absolute differences, then divides by eight via a right shift**. Stage67's green-site diagonals instead combine four. Reusing those four-term diagonals at the R/B sites is incorrect.

The independent six-pair diagonal equations were recovered using synthetic single and paired impulse graph reconstruction and then checked against two private original-ARM64 opcode-listing interpreters. The two original colour-site blocks have different non-pixel bookkeeping but yielded the same eight direction codes in the tested bounded input contract. The source preserves the final original low-sixteen-bit narrowing without replacing it with ordinary signed saturation.

One intentionally synthetic negative control: on a zero-valued 9x23 RAW tile, place one 8000-code impulse one row **above** the centre. The Stage68 colour-site route returns NE=2000 and NW=2000. The Stage67 green-site route returns NE=0 and NW=0. The four cardinal gradients remain equal. This witnesses why the two branches cannot be conflated; it says nothing about a particular real photograph.

## What was actually checked

- **5,740 distinct synthetic RAW patches**, across strides 9, 17, 23, 41, including 5,600 seeded random patches and constant, edge, impulse boundaries.
- Two *private opcode-listing interpreters* plus register-poison repetitions: **12,440 comparisons / 99,520 exact direction output codes**, maximum difference zero. These are separately interpreted static instruction sequences, **not actual original ARM64 executable runs under Unicorn**.
- The incorrect green-site diagonal implementation disagreed with the colour-site route on **19,919 diagonal output codes** among those 5,740 patches. This is an arithmetic discrimination count, not an image-quality or scene-frequency measurement.
- Independent Python spatial reference vs C11: **8,132 patches / 65,056 exact direction codes**.
- A bounded composition adapter `hb_colour_site_green68` calls Stage61 edge directions, the new RAW colour-site gradients, then the already independently validated Stage63 green estimator, with **caller-owned threshold floors**. Its **2,048-case binding test** uses a conspicuously labeled **mock** for Stage63; it establishes correct argument wiring, not that the green output matches the original executable.
- GCC `-std=c11 -O1 -Wall -Wextra -Werror -fno-fast-math -ffp-contract=off`, with AddressSanitizer and UndefinedBehaviorSanitizer in the standalone C test. Source immutability, output canaries, invalid-argument rejection, random/full-code extremes and the negative control passed.
- The private extracted `libcrosssdk.so` was byte-checked against the original locally attached Phocus APK in the working environment. Its bytes, hashes, disassembly, original profiles and private photographs were not exported.

All checks are host-only and on bounded 5x5 halo-compatible RAW16 neighbourhoods. The tested scalar code does not prove full-frame CFA phase alignment, an image-edge extension policy, Android/JNI parity or Phocus-equivalent colour rendering.

## Sources and tests

- `colour_gradient68.[ch]`: new independently implemented colour-site gradient, linked against canonical Stage67 `raw_gradient67.c`.
- `colour_site68.[ch]`: composition of Stage61 signed-edge directions, Stage68 RAW directions, and Stage63 `hb_green_at_colour63`. The real Stage63 implementation is **linked by consumers**; no synthetic replacement is used by the production adapter.
- `test_colour_gradient68.c`: sanitizer-friendly deterministic RAW16 tests and a positive failure witness against the wrong green-site diagonal route.
- `test_colour_gradient68.py`: independent scalar Python spatial reference for all eight direction codes.
- `mock_green_stage63_68.c` + `test_colour_site68.py`: explicitly mock-only argument binding tests. The mock must **never** be linked into a renderer.
- `audit_native_colour68.py`: prepared, **not executed** original-CPU operand parity runner that plugs into the Stage63 Unicorn harness. It samples the actual second direction operand supplied to `GetGreenAtRedFirst`, tests the independent RAW gradients, and can substitute them in the remaining original loop. It does not skip or independently replace the original inline SIMD.

For a full repository checkout on the Stage68 branch:

```sh
python3 hasselblad_native_audit/phocus_coloursite_stage68/test_colour_gradient68.py \
  --work /tmp/hb68 --safe-receipt /tmp/hb68-gradient.json
python3 hasselblad_native_audit/phocus_coloursite_stage68/test_colour_site68.py \
  --work /tmp/hb68-binding
```

For original-CPU parity **when the same private original APK and Unicorn/Capstone/pyelftools dependencies are present**:

```sh
python3 hasselblad_native_audit/phocus_coloursite_stage68/audit_native_colour68.py \
  --apk /private/locally-supplied-phocus.apk \
  --work /private/stage68-audit \
  --safe-receipt /private/stage68-native-aggregates.json \
  --sanitize
```

The native parity receipt MUST NOT be marked passing until this executes and checks its image channels. Other already pending original-CPU audits from Stages64–67 remain separate.

## Next gates

1. Run original-CPU audits of Stages64–68 in the native-capable environment; investigate differences before any promotion of the supported contract.
2. Wire both Stage67 and Stage68 original-direction operands into the Stage66 scalar work scheduler, replacing its mocked pixel callbacks with the independently implemented Stage61–63 helpers. Preserve the three work margins (4, 6, 8 pixels) and original output-plane ownership.
3. Independently port all remaining active `InterpolateRGB` inline pixel operations and resolve the supported `ColorNoise` flags/strength contract. No original executable pixel operations may remain when declaring a complete port.
4. Validate connected linear RGB16 on synthetic, nontrivial strides and private held-out DNG interior tiles; then original full-frame alignment/halos/CFA; Android/JNI and exported device pixels; only **afterward** build an opt-in saved-DNG comparison APK.

The Stage58 baseline remains unchanged. Do not scene-fit the existing tungsten image or publish original binary/profile/pixel data as evidence.
