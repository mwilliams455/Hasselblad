# Stage87 — optional sharpening for normal camera JPEGs

Install as an update. In **Settings → Hasselblad rendering**, **Sharpen saved
JPEGs** defaults off. Turn it on to use the recovered CPU defaults already
exercised by the Stage86 saved-DNG phone comparison. Fine detail is crisper, but
low-light grain can become more visible. The existing curve/profile and diagnostics
preference are retained. No extra profile or tone pack is needed.

The setting applies only to compatible Hasselblad JPEG captures. RAW-only output
is unchanged; RAW + JPEG sharpens only the JPEG. JPEG-only still removes the private
temporary DNG after rendering. Diagnostics remain an independent opt-in. The
live viewfinder is unchanged and does not yet show the Hasselblad rendering.

The preference is copied into the existing immutable capture evidence when
processing begins. A later toggle does not change that in-progress render. The
JPEG EXIF image description records sharpening off/recovered even when diagnostic
files are disabled. When diagnostics are enabled, the Stage87 capture report
separates requested sharpening from applied sharpening and records the defaults
(amount 100, radius 1, noise limit 0, dark limit 10). RAW-only does not claim applied
sharpening. The colour/bitmap timing includes sharpening when enabled.

The off branch retains the combined finishing method. The on branch inserts the
unchanged Stage86 bounded stream after film/default gradation and before sRGB
output. It uses one pending band plus neighbouring rows, with no full-frame RGB
sharpening buffer and no comparison spool files. The final pending band is flushed
before returning; cancellation or sink failure aborts the stream. Demosaic,
calibration, colour/LUT kernels, profile bytes and publication helpers are unchanged.
Original Phocus outer-image boundary parity remains unverified.

## Focused checks

```sh
python3 hasselblad_native_audit/phocus_capture_stage87/check87.py --work /tmp/hb87
```

The actual scene renderer, settings, Java stream, JNI sharpening and colour/finishing
code run on the host. Explicit adapters supply deterministic prepared RAW/demosaic
bands and illuminant selection: this is an integration test, not another demosaic
or sensor calibration validation. Compare the off path against the former combined
finishing operation and on against the Stage86 comparison sequence partitioned
into 7-row bands. Sizes include 65×65, 256×192 and 4032×130. Check nontrivial changes,
band order, a partial final band, one preparation/demosaic pass, default-off,
independent settings, failed preference writes, changes during a render,
diagnostic on/off, cancellation and failed sinks. Optional private curve0/curve1
profiles are checked locally only, never uploaded to CI or bundled.

The Stage86 diagnostic adapter is updated only to compile against the added
scene-renderer overload; its existing off-path assertions remain usable. Original
Stage85/86 native and streaming proofs are retained; the old demosaic/native-oracle
suites are not rerun.

The Stage86 phone comparison established that the saved-DNG sharpening path ran
with curve1, with no obvious broad colour/exposure change in the inspected scene.
It also showed increased grain; this is why the new setting defaults off. Its
199 ms render/encode difference was one sequential comparison, not a measured
normal-shutter overhead. Stage87 ordinary camera capture still needs phone checking.

## Minimal phone check

Keep **Save → JPEG** and diagnostics off. Take an ordinary photo with **Sharpen
saved JPEGs** on, confirm it saves and opens, and inspect detail/noise. Switch off
for the established rendering. No DNG re-comparison suite is needed. If capture
fails, enable diagnostics for one fresh capture and export **Last photo details
and export → Export last shutter comparison ZIP**.
