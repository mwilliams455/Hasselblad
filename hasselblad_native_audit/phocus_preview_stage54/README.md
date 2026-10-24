# Stage54: isolated saved-DNG highlight comparison

This integrates the Stage53 portable CPU highlight operation into the saved-DNG
viewer. It prepares both the original colour preview and an experimental
highlight version from identical prepared samples and the same imported `.hbc`
profile. The viewer starts on the original preview; its comparison button cycles
through highlight reconstruction, the neutral baseline, and the original view.
Capture processing is unchanged.

## Domain and white-balance ownership

The input is the existing Stage43 reader's RGB16 output: black-level normalized,
gain-map corrected, bilinearly interpolated, sampled and clipped to 0..65535.
The Stage53 constructor therefore receives 65535 for all three clipping levels.
These are the **prepared encoding ceilings**, not measured physical sensor
saturation thresholds. The original Phocus fast-interpolation, highlight,
remosaic and final-demosaic graph is not reproduced. Lost upstream headroom is
not recovered. This placement is an explicitly labelled experiment.

Only the selected DNG provides the neutral and colour matrix. The bridge uses
`gainRatios = min(AsShotNeutral) / AsShotNeutral` and divides each column of the
existing camera-to-D50 matrix by the corresponding gain ratio. Thus simple
linear gain application followed by the factored matrix equals the original
matrix operation, before integer quantization. The nonlinear highlight stage
replaces that simple gain application. The LUT temperature remains the imported
profile's explicit setting; it is not inferred or fitted to the photograph.

The new comparison explicitly enables Stage53's analytic equal-lower-gain
limit. The JNI API rejects that singular case without permission. Reports
identify whether the limit was used. No separate white-balance multiplier,
exposure correction, saturation adjustment or scene-dependent coefficient is
added to the colour core.

## Validation

- Actual Java/JNI integration: 64 synthetic cases, all 159,168 compared RGB16
  channels exact against independently calculated NumPy fixtures. White-balance
  factorization error is below `5e-16`.
- Existing Stage42 JNI, Stage43 DNG/profile and Stage48 metadata checks pass.
  Rejection tests include null/invalid arrays, over-limit previews, nonfinite
  gains, invalid neutrals and unapproved singular inputs.
- The retained 786,432-pixel DNG produces exactly the same original prepared
  RGB, camera matrix and original colour result as before. All 2,359,296 final
  highlight-render channels match the complete independent calculation exactly.
  A stratified subset also passes the original native CPU highlight filter.
- The original input files and private profile are unchanged. No coefficient
  is selected using the scene. Host timings are not phone benchmarks.

See `../../evidence/stage54/STAGE54_PREVIEW_VALIDATION.json` for aggregate
metrics, including differences from the original view. Image differences are
not accuracy scores against a real Hasselblad or Phocus export.

Run synthetic checks from the repository root with Python, NumPy, the Stage43
fixture dependencies, Java 17, JNI headers and GCC:

```sh
python hasselblad_native_audit/phocus_preview_stage54/check_host54.py --work /tmp/hb54
```

The optional private `audit_preview54.py` accepts explicit local DNG, profile,
original APK, host build and previous reference-directory paths. Its working
directory contains private arrays. Only its `--safe-receipt` may be published.
Neither original vendor bytes, private camera calibration, imported profiles
nor photographs enter CI or the APK.

The Stage54 workflow builds both existing Android ABIs with the same application
ID and signing identity. An APK build does not establish device correctness or
cross-camera colour fidelity. Full Phocus equivalence remains unverified.
