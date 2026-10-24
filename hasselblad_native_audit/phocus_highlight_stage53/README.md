# Stage53: bounded native highlight reconstruction

Stage52 placed scalar highlight reconstruction before the SDR colour and film
stages. Stage53 supplies an independently written portable C implementation of
that operation, a NumPy reference, and comparisons with the original AArch64 CPU
filter and original fragment shader. No photographic scene is used for tuning.

This is research source, not an Android renderer integration. The existing APK,
capture renderer, LUT and film core are unchanged. The aggregate receipt is in
`../../evidence/stage53/STAGE53_NATIVE_HIGHLIGHT.json`.

## What the operation does

The constructor sorts channels by gain, normalizes gains by their maximum, and
uses per-channel clipping levels to map sensor values into its calculation
domain. It constructs two piecewise correction segments from the gain ratios.
Clipped samples use the appropriate boundary correction. Interior samples blend
the corrections at three hypothetical clipped boundaries, with weights
proportional to the eighth power of channel brightness. The result returns to
the original sensor channel order and clipping scale.

This is a nonlinear operation, including changes to some unclipped samples. A
linear white-balance matrix alone does not reproduce it.

Reciprocal multiplication during input scaling is intentional. Replacing it
with an algebraically equivalent division changes branch decisions at some
exact clipping levels. CPU and GPU references must also retain their respective
precision: the CPU uses doubles, while shader parameters and arithmetic are
float32. The shader additionally suppresses interpolation weights when their
sum is at most `1e-6`; the CPU handles the zero-sum case.

## Validation

The 38 regular cases cover all channel orders for synthetic gains, three sets
of clipping levels, equal upper gains, nearly equal lower gains, and eight
gain sets constructed privately from the original profile. Each case includes
full-range and clipping-scaled cubes, a neutral ramp, seeded random samples,
and samples one code below, at, and above each clipping level.

- Portable C versus the complete native CPU filter: all 233,928 RGB16 channel
  values agree exactly. The NumPy reference differs by one code in one channel.
- Portable C float output agrees exactly with the float32-rounded NumPy
  reference over the regular cases.
- Original native GPU uniform construction agrees exactly with float32-rounded
  independently constructed parameters.
- The unchanged original shader agrees with the independent float32 reference
  to about `0.000489` linear using the selected RGBA16F storage, and within one
  code after the audit's 8-bit encoding. RGBA32F diagnostic error is below
  `3e-7` linear.
- Native exposure-scalar checks cover 72 combinations. Synthetic DNG
  white-balance factorizations cover 100 matrices/neutral values.
- Guarded buffers, in-place operation, parameter immutability and 17 rejected
  input checks pass. GCC builds with warnings treated as errors and floating
  point contraction disabled; Python audit warnings are also treated as errors.

The CPU and GPU are validated against separate references. They are **not**
asserted equal: maximum differences between the original paths reach about
`0.0537` linear on this adversarial grid, including clipping-boundary decisions.
RGBA16F input quantization and the dark threshold also matter. These metrics
are arithmetic comparisons, not perceptual colour scores or measurements of
a real photograph.

## Equal lower gains

The original scalar construction is singular when its two lower gains are
equal, including unity gains. The original double routine produces nonfinite
values in the bounded test; the CPU integer wrapper and software GPU handle
those values differently. This does not establish what an entire production
Phocus import would do with such an input.

The default C preparation rejects this case with `-2`. An explicit opt-in
returns `1` and uses a separately derived analytic limit. Unity gains then
produce the identity up to sensor clipping. Native calculations converge to
this limit from both lower-channel orders as the gain difference approaches
zero. Twelve portable limit cases exercise all four gain configurations and
all three clipping sets. This extension is labelled separately from faithful
native regular-domain reconstruction; it does not copy platform-specific NaN
handling.

## Portable API and phone boundary

`highlight53.h` / `highlight53.c` contain no camera calibration or vendor shader.
Preparation accepts three finite positive gains and nonzero uint16 clipping
levels. Tiny absolute gains, numerical degeneracy and invalid inputs are
rejected. Callers must pass successfully prepared, unchanged parameters and
valid buffers. Identical input/output pointers are supported; partial overlap
is not supported. Negative or nonfinite float input is rejected before any
output is written. Samples above their clipping levels are capped.

The C primitive reproduces the **CPU** arithmetic path. It is not a drop-in
replacement for the original GPU path, and its host build is not a phone
performance benchmark. Extreme gain ratios outside the tested domain remain
unvalidated.

An isolated DNG preview integration must use the phone's own sensor neutral
and clipping model. If `M` is the existing camera-to-D50 transform and
`g = 1 / AsShotNeutral`, factor white balance as
`M_after = M * diag(max(g) / g)`. Applying `M_after` after simple
`raw * g / max(g)` preserves the existing transform algebraically. Applying
the nonlinear highlight operation in that location is a subsequent experiment,
not something proved by that identity. Demosaic and gain-map placement, physical
phone sensor adaptation, highlight clipping provenance and end-to-end output
validation remain necessary. Private Hasselblad sensor gains must not be
applied directly to phone sensor samples.

The original tool-4 exposure scalar is independently checked as the maximum
processed WB gain times the three source-description factors and the enabled
exposure multiplier. That scale must not be silently applied again inside this
primitive.

## Reproduce privately

From the repository root, using the dependencies of the Stage52 audit plus
GCC and software EGL/GLES:

```sh
python -W error hasselblad_native_audit/phocus_highlight_stage53/audit_highlight53.py \
  --apk /private/original.apk \
  --work-dir /private/stage53-build \
  --safe-receipt /private/STAGE53_NATIVE_HIGHLIGHT.json
```

The audit inherits explicit host allocation, ownership, configuration and
profile-cache fixtures. The original CPU constructor/pixel loop, GPU parameter
body and unmodified shader execute. Shader execution uses Mesa llvmpipe with
actual stored input readback; RGBA32F is a diagnostic, not the selected native
format. No phone GPU or full application import is exercised.

Keep the original APK, extracted shaders, profile matrices/LUTs, derived private
gain arrays, private source hashes and photographic inputs outside public git,
CI and distributable APKs. Only independently authored source and aggregate
receipts belong here. Full Phocus equivalence and physical cross-camera
fidelity are not claimed.
