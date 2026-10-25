# Stage74 — Bounded independent final linear RGB16 and Android NDK/JNI candidate

**Scope:** an independent, self-contained C11 CPU path from an *already prepared*
RGGB Bayer tile with a 32-pixel supplied halo, through Stage69 interpolation,
corrected Stage65 ColorNoise, and a newly reconstructed post-YCC final RGB16
encoding. The normal Stage58 Photon capture path is unchanged. No APK, full DNG
import, physical camera colour comparison, live preview, LUT, sharpening or HDR.

## Native output observations

The original Phocus `GGDirInterpolator` converts post-ColorNoise planes to
three final linear RGB16 codes using the integer path reconstructed in
`output74.c`. In the bounded observed graph, output gain is unity, luminance
caps at 65534 before encoding, and the 32-bit red/blue multiplications wrap
before signed arithmetic shifts. The green channel uses signed subtraction and
truncation toward zero. Applying an ordinary floating-point RGB conversion or
post-hoc saturation is **not** equivalent on extreme codes. The scalar and
SIMD native paths were both sampled and independently checked.

`frame74.c` joins existing independent components without using any native
intermediate values. Its output is internal **linear RGB16**, not the final
Hasselblad look, Phocus sRGB output, or a colour-calibrated phone photograph.
`hb74_render_final_bounded` accepts a Stage73 plan, the same bounded 32px
RGGB input halo, explicit input stride, destination and capacities. Output is
interleaved R/G/B unsigned sixteen-bit codes, with a measured native
`scale_threshold=1.0`, floors 32/200, graph flags 0xFFFF, optimized view off,
noise strength zero and unity output gain.

Supported output sizes are the exact nine Stage73 sizes; no arbitrary tile
scheduler, global CFA phase or full-frame border handling is provided. Extra
native alignment-tail cells remain unresolved, so the diagnostic uses an
explicit fill value and tests output invariance to it. Failed API calls are
rejected without modifying the caller's output buffer.

The Java wrapper
`com.particlesdevs.photoncamera.hasselblad.HasselbladFinalRaw74` executes the
real host JNI method. `CMakeLists.txt` builds an Android NDK shared library for
the enabled ABIs; it is a research binary and is **not** wired into the normal
Android capture path. Device pixel output has not yet been captured/compared.

## Reproduce public tests

From the repository root (Linux with GCC and a JDK):

```sh
hasselblad_native_audit/phocus_output_stage74/run_host74.sh /tmp/hb74-tests
hasselblad_native_audit/phocus_output_stage74/run_jni_host74.sh /tmp/hb74-jni
python3 hasselblad_native_audit/phocus_output_stage74/test_output74.py
```

The host runner links the canonical C source from Stages61–69, 73 and the
corrected 64–65 implementations. GCC ASan/UBSan validate the all-independent
pipeline. The public GitHub workflow also cross-compiles the exact source with
an Android NDK and checks the resulting ARM64 ELF class/machine.

## Private native checks (not CI)

The original Phocus APK and saved DNG are user-supplied local private test
fixtures. The original CPU was executed through Unicorn on the local host,
separately from the independent C implementation, and only aggregate counts
are shared. The private runner and its raw source/original outputs never
enter GitHub. An exact native RGB16 comparison does not mean the camera
sensor colour basis, white balance or display pipeline match Hasselblad.

## Next

1. Validate the final C path on additional held-out DNG tiles and non-unity
   exposure gains before expanding the supported parameter set.
2. Run the NDK library on an Android device, export raw RGB16 output and
   compare byte-for-byte to the same saved-DNG host reference.
3. Validate tile seams, global CFA phase, input opcodes/GainMaps, original
   edge extension and performance before enabling a full ~12MP render.
4. Keep existing Stage58 preview/normal capture untouched until real phone
   results justify a separate optional saved-DNG diagnostic build.
