# Stage77: faster saved-DNG scene rendering

Stage76 completed a real 4032x3008 scene render on the test phone in 21.832s
before ZIP packaging: 12.042s demosaic, 5.252s three-view colour/bitmap work,
3.373s preparation/calibration, 0.240s setup/copy and 0.920s verification/encode.
Its three exported assembled-band windows matched Stage74 on the host exactly
(36,864 RGB16 channel values). This is one scene, not broad device/colour validation.

Stage77 changes scheduling and preview work. It does not change the colour
profile, DNG preparation, interpolation/ColorNoise/output kernels, ordinary
camera capture or Stage74/76 reference implementations.

## Changes

- Use 256x64 output blocks where width permits, with the same real 32-site
  Bayer halo. Narrow images use 64x64. At 4032x3008 this is 752 blocks versus
  2961 old tiles, reducing the repeated horizontal halo calculation.
- Use compact scratch strides of 320 or 128 instead of 1024. Allocate one
  isolated workspace per worker per band, reset it between blocks, and reuse
  it across assigned blocks. Up to four workers write disjoint output regions.
  Thread-creation failure executes the same assigned work synchronously.
- Select neutral/manual preview samples before their pointwise colour
  transform. At preview step 4 those two views process 1/16 as many pixels;
  the automatic-colour output still processes every pixel at full resolution.
- Keep the original 32-site crop, full-resolution automatic JPEG, three
  bounded previews, private samples/export, cancellation and rejection rules.
  The report separates automatic-output and comparison-preview colour timing.

The 256x64 geometry is a new integration contract compared against Stage74/76,
not a claim of direct vendor validation for that larger geometry. Stage74's
bounded API and evidence scope are unchanged. The app automatically compares
three small Stage77 bands to Stage76 before rendering on each phone.

## Validation

- JVM/JNI comparisons: 2,411,928 exact RGB16 codes across narrow, wide, odd,
  trailing partial bands, one/four workers, with immutability and rejection checks.
- Preview sampling: 277,578 exact manual/automatic RGB16 codes compared with
  transforming first and sampling afterwards; neutral pixels/placement exact.
- Eight synthetic spatial patterns: 1,831,104 exact codes.
- Full spatially varying 4096x3072 synthetic input: all 36,384,768 output
  RGB16 codes equal Stage76, separately with one and four workers.
- ASan/UBSan: widths through 8192, partial/error bounds and output guards pass.
- Initial local host native-call totals: Stage76 14.383s, Stage77 one worker
  8.920s, four workers 2.938s. These are host measurements, not phone forecasts.
  CI records its own timings in STAGE77_HOST_VALIDATION.json.

## Phone test

Install `HasselbladPhoton-0.1-hb-speed77-27217.apk` over the current app.
Open **Saved DNG colour → Stage77 · faster full-scene colour and LUTs**.
Use the same saved DNG and imported automatic `.hbc` profile as Stage76.
The Stage76 screen remains available for direct comparison.

Render once, inspect the automatic/manual/neutral views, then export
`Hasselblad_Stage77_Scene_Comparison.zip`. Compare its samples with:

```bash
python3 hasselblad_native_audit/phocus_speed_stage77/compare77.py /private/scene.zip
```

For the same DNG/profile, also compare decoded JPEG and PNG pixels to the
Stage76 ZIP and compare total/demosaic/colour timings. Phone speed, thermals,
repeated-render/lifecycle behaviour and broader daylight colour quality remain
unmeasured until tested. No repeated manual demosaic fixture procedure is needed.

Keep private photos, samples, profiles, calibration and identifying metadata
out of public GitHub. Ordinary camera photos still use Photon.

```bash
python3 hasselblad_native_audit/phocus_speed_stage77/check77.py --work /tmp/hb77 --jni "$JAVA_HOME/include"
sh hasselblad_native_audit/phocus_speed_stage77/run_sanitizers77.sh /tmp/hb77-asan
```
