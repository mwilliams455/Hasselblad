# Hasselblad Photon — Domain3 signed APK handoff (21 October 2026)

## Canonical checkpoint

- Project repository: https://github.com/mwilliams455/Hasselblad
- Working branch: `recovery/awb-rebuild-20261021`
- APK build source commit: `6d43460b418bb921fad5c5abe665d36019881dae` (documentation commits may advance the recovery branch; check its current HEAD before another change)
- Main unchanged: `929f523aa02ae5b224be39b9c36cce5975691a10`
- Signed Domain3 checkpoint documentation commit: `c0f95168fa189ed80918abab0a5ccfca1c1b7697` (subsequent doc corrections may advance it further)
- Last source-only Domain2 checkpoint: `8c9060f4cf28f6745fb3c7123299dda36823a18f`
- Domain3 Java/JNI host validation: https://github.com/mwilliams455/Hasselblad/actions/runs/39674585517 — PASS, 40 assertions (synthetic inputs) using the *actual* owned phone temperature, domain and JNI sources.
- Domain3 signed APK build and verification: https://github.com/mwilliams455/Hasselblad/actions/runs/39674679198 — PASS.

## Deliverable

- File: `HasselbladPhoton-Domain3-27184-debug.apk` (standalone APK within this conversation's artifacts; not the GitHub Actions ZIP)
- Application ID: `com.mwilliams.hasselbladphoton`
- Version: `0.1-hb-domain3`, code `27184` (upgrade from installed Scene1B 27183)
- Bytes: **70819597**
- APK SHA-256: `43c8814dd16f6547ab1824ea2f11c59df2c11fb9763c35d0d3a1eb8139b8b9d3`
- Signing certificate SHA-256: `255cb09eaddd26a9cc680786e4985372cf24d0e54bb120fc44d48f3273ff3956` (matches Scene1B)
- JNI library: `lib/arm64-v8a/libhasselblad_domain_jni.so`, SHA-256 `4b83fbb60f9bdec765b46ac066f7f95ca145d9181c8ac9bf2ab732e4ffe91e1b`
- Domain JNI ELF LOAD alignments: [16384, 16384] bytes. `libhasselblad_scene_jni.so` from Scene1B remains present.
- Public-safe build report: `Hasselblad_Domain3_APK_Verification_20261021.json`; private APK and full capture metadata must **not** be committed to public Git.
- APK and report were extracted from the GitHub Action artifact; the APK SHA was independently recomputed and matches the CI report.

## New capability, precise boundary

**Domain3 is a diagnostic-only on-demand upgrade.** The complete bounded automatic AWB controller reconstruction and AWB atmosphere/post sequence were previous firmware research milestones; neither a complete phone automatic profile nor Hasselblad HNCS photographic rendering is yet active.

- A new separate ARM64 shared library exposes `HasselbladDomainDiagnostics.nativeEvaluate`, calling the owned `hb_phone_domain_evaluate`/`hb_phone_temperature` routines (not vendor `libaaa.so`).
- The existing capture evidence path saves only a compact, verified original Camera2 A/D65 physical-camera calibration snapshot in volatile app-session memory. It clears that snapshot when a new capture begins and on invalid evidence. The 729-point work is **not** performed when pressing the shutter.
- Under **Hasselblad Development Check** (not the normal shooting screen), `Run Domain1 temperature/tint coverage` explicitly starts work on a background thread; its `Copy Domain1 JSON` button exports a summary, full per-point grid and exclusion provenance.
- The fixed explicit test grid is 2000–10000 K at 100 K intervals, tint −100 to +100 at 25-unit intervals, 81 × 9 = 729 entries. It reports valid points, converter exclusions, signed-gain-domain exclusions and adjacent duplicate points. There is **no calibrated policy or accepted photographed neutral**.
- The result labels original physical sensor ID, frame and sensor timestamp, and sets `render_applied=false`, `shipping_policy_selected=false`, `full_automatic_controller=false`, `selection_uses_hal_neutral=false`.
- Photo rendering, existing six Scene1B native acceptance tests, DNG/JPEG/JSON save code, original HAL white balance and Phone camera capture settings are left unchanged. The original JPEG colour still comes from Photon.
- The new code does not infer or transfer X2D II sensor calibration, introduce stack/HDR, widen scene radii, silently drop out-of-domain points, or apply white balance twice.

## Tests complete

1. Domain1 synthetic tests and O0/O2 real temperature-leaf host checks passed (previous Domain2). Real capture saved-model replay matched 2,187 per-point results across three captures sharing one phone profile: 707 valid, 19 clipped, 3 signed-gain exclusions, zero mismatches. These are model consistency, not physical photographic calibration.
2. Domain3 Java/JNI host harness passed **40 checks** with synthetic Camera2-like matrices: no-verified-capture result, bound identity, full 729-point ordered wire, reproducibility, non-mutation, model rejection, and native input guards.
3. Signed Android application Gradle build succeeded on GitHub Actions. `apksigner verify` returned PASS with previous certificate; `aapt` verified package name/version 27184; signed APK contains both the old Scene1B and new Domain1 ARM64 JNI libraries; Domain1 ELF LOAD alignment >=16 KB.
4. The new APK was **not yet installed or exercised on the user's phone**. Actual device duration/memory, UI behaviour, various sensors/ROMs, colour correctness and continuous capture reliability remain unverified.

## Next immediate test — user device

1. Install `HasselbladPhoton-Domain3-27184-debug.apk` over installed Scene1B; **do not uninstall** first (same app ID and signer). If installation fails, preserve Scene1B and share the exact message.
2. Open Hasselblad Development Check **before** a capture. Run Domain1 once: expected `skipped (no_verified_capture_this_app_session)`, not a crash or unexpected success.
3. In PHOTO mode, take one ordinary standard RAW+JPEG photograph, using a simple subject. Ensure DNG and matching `.capture.json` save as before. The image is still Photon rendering; no reference target or lamp Kelvin needed for this diagnostic-execution test.
4. Open Hasselblad Development Check again. Tap **Run Domain1 temperature/tint coverage**. Expected `completed`, `729` total points, real physical sensor ID, frame, timestamp, `render_applied=false`; `Copy Domain1 JSON` should copy a complete report.
5. Share the copied Domain1 JSON and, when needed, the paired original capture `.capture.json`. Compare exact sensor identity and coverage to the already verified saved profile. On the previously tested sensor, 707/729 was the saved-host result, **not a universal or hard-coded expectation**. Check whether its actual capture profile matches before claiming equivalent counts.
6. Check 3 consecutive photographs for normal saves, existing six-policy Scene1B diagnostic, app stability and responsiveness; then repeat on another physical camera if supported.

## After hardware validation

Complete phone-specific illumination/neutral acceptance calibration across controlled neutral captures, bounded automatic initialization/history/recovery, then integrate a validated Hasselblad neutral **once** into a coherent RAW-to-linear path (with headroom, no double white balance). The separate saved-photo HNCS rendering (CCM, tone/gamma, 3D LUT) still needs reconstruction/integration/photographic validation. Neither stage is closed by Domain3.

## Working instructions

Continue on `recovery/awb-rebuild-20261021`; don't merge to main without approval. Preserve private phone photos/Camera2 calibration and debug APK separately. Don't redo verified firmware reconstruction merely because an older handoff is stale. If code changes, use a new version code > 27184 with the same signer. Don't assert photo colour is Hasselblad based only on these diagnostics.