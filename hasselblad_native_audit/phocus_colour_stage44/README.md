# Stage44 — why Stage43 looks mostly like a tone change

The owner reported that the Stage43 phone conversion did not yet convey the
intended Hasselblad character. This stage measures that concern rather than
adding saturation or claiming that an exact core replay proves a photographic
match. No Android or capture code changes; Stage43 remains the installed APK.

## Phone isolation

Use the earlier Stage42 cat DNG bundle, not the newer children's-room screenshot
scene. All five independent vectorized traces match the unchanged C renderer
exactly, covering 11,796,480 channel evaluations. The full render also matches
the prior bundle hash. Each effect below holds the other stated stages fixed.

| Isolated effect | Mean absolute displayed channel difference, 0–255 |
| --- | ---: |
| Adapter/quantization round trip versus neutral baseline | 0.009 |
| Shadow chroma weighting | 0.496 |
| Film curve 1, identity LUT held fixed | 14.282 |
| Real LUT, curve 1 held fixed | 0.509 |
| Real LUT without the film curve | 0.394 |

These are nonlinear counterfactual comparisons, not additive percentages of a
look. The film curve is the dominant change in this image. The LUT is active:
8.33% of pixels change by more than two levels in at least one channel when it
is added to the tone-only control; maximum channel change is 24 levels.

Changing only the LUT look temperature from 4000 K to fixed alternatives
2500/3100/5550/6500/9100 K changes the mean displayed channel value by at most
0.371 levels in this image. WB remains owned by the DNG matrix throughout.
This does not validate a 4000 K choice or a phone temperature-to-LUT mapping.

The D50-to-internal white has relative channel spread 1.43e-5. The inverse
adapter differs from the separately stored original inverse by at most
4.14e-6. These checks and the near-identity no-look round trip show no gross
transpose/white-axis error; they do not validate camera colour fidelity.

The trace separately counts internal pre-curve clipping, curve endpoints and
final linear-sRGB clipping. For full curve1 rendering of this earlier RAW,
1,655 channels exceed the internal 16-bit limit and 1,867 exceed linear-sRGB
unity after display conversion. The old device input-clipping counter measures
an earlier stage. These counts do not diagnose the newer TV screenshot's RAW.

## Matched camera references

The four existing 3FR/preview/JPEG pairs are camera-output references from
capture software 1.1.6.3, not verified Phocus exports. Embedded previews use the
frozen Stage41K empirical P3-to-sRGB conversion; tagged sRGB JPEGs are scored
separately. Both references agree in direction on the curve comparison.

Two bounded paths are evaluated:

1. The current experimental D50 adapter on the existing conventional LibRaw
   linear-sRGB caches. That is a common-colour-space diagnostic, not a native
   Phocus sensor render. Positive exposure fitting can clip this cache before
   RGB16 quantization; primary masks and preparation remain explicit.
2. The recovered sensor22/filter6 profile on those actual X2D II RAWs. Preparation
   is explicit black/white normalization, half-size RGGB cell reduction with
   mean green, linear-area resize and the previous similarity registration.
   CFA is checked with LibRaw. AsShotNeutral supplies gain ratios; the previously
   verified CCNC=false converter supplies profile temperature. The live Android
   debug state and prepared arguments remain unobserved. No Hasselblad sensor
   coefficient is applied to a phone image.

The second path changes preparation as well as sensor calibration, so its
improvement on the red car cannot be attributed solely to a matrix swap.
Neither path implements the complete original RAW or Android GPU pipeline.

One scalar exposure is fitted separately for each fixed curve on calibration
image tiles; disjoint guarded tiles are scored. Both tile phases are retained.
No colour coefficients or tone curves are fitted. These same four scenes have
already guided prior research; this is reference-assisted diagnosis, not blind
new-scene validation or a universal exposure rule.

### Fixed recovered curve alternatives on the sensor-profile path

Phase-0 mean absolute displayed RGB error; lower is better:

| Scene | Curve 1 (current choice) | Curve 0 | No-film control |
| --- | ---: | ---: | ---: |
| A, red car | 2.950 | 2.150 | 9.131 |
| B, tower | 6.077 | 3.155 | 6.900 |
| C, portrait | 8.757 | 6.251 | 6.863 |
| D, cathedral | 5.412 | 5.032 | 6.467 |

Curve 0 improves primary RGB error on all four scenes in both tile phases and
against both references. Phase-0 improvements versus curve1 are 27.1%, 48.1%,
28.6%, 7.0%. On portrait skin patches, RGB error falls 4.65→3.04 and a/b error
4.66→2.62. Shirt RGB error falls 24.03→15.19 but remains large. Dark-background
chroma error worsens slightly (2.71→2.83). There is no all-region accuracy pass.
This comparison does not identify which curve the camera or live Phocus uses.

## Reversible curve0-only trial

`prepare_profile43.py` now accepts `--film 0` or `--film 1` (default remains 1).
The private trial `.hbc` works in the existing Stage43 APK. Only its film-code
field, curve payload and checksum differ from the delivered curve1 profile.
LUT, manual look temperature 4000 K, D50 adapter, shadow settings, WB ownership
and exposure remain byte-identical. It contains no photo or phone-sensor matrix.

The trial's 512 photographic samples / 1,536 channels match the original ARM64
pixel routine exactly. A full 786,432-pixel comparison through Stage43's Java
DNG preparation and JNI matches the generated private RGB16 reference exactly;
display and baseline RGB8 also agree. Three synthetic diagnostic tests cover
clamped coordinates, nonpositive luminance, stage-specific clipping and unsigned
differences. No Stage44 device result is claimed.

At unchanged phone exposure, curve0 is substantially brighter: average absolute
channel change 30.288 levels versus curve1 on the earlier RAW. Linear-sRGB
above-one channels rise 1,867→2,030 (0.0791%→0.0860%); displayed 255-valued channels
rise 2,198→3,061. Thus the brightness-fitted reference advantage is not proof of
an improvement at the phone's fixed exposure. This is a diagnostic profile,
not a replacement default or a solved Hasselblad colour match.

The owner can import the trial profile in Stage43 and reopen the same saved DNG;
`film_code` should be 0. Importing the original `.hbc` restores curve1. Normal
capture remains Photon. Next work is to establish the actual source film/working
space selection and validate the phone colour mapping against a complete,
known-settings Phocus render. Keep sensor calibration, WB, tone and LUT effects
separate; do not strengthen the LUT to compensate for unverified input mapping.

## Reproduce and preserve privacy

Use Python 3.12 with NumPy, SciPy, Pillow, OpenCV, tifffile, rawpy and the sibling
Stage41W–Z/Stage42 dependencies. Panels use DejaVu Sans. Arguments are in each
script's `--help`; input paths are supplied privately. Retain the Stage41J
manifest/caches and Stage41K reference-encoding policy. Run:

```
python -m unittest discover -s hasselblad_native_audit/phocus_colour_stage44 -p test_trace44.py -v
```

`audit_colour44.py` performs phone isolation and the common-D50 reference test.
`check_sensor44.py` performs the bounded sensor-profile/curve test.
`prepare_trial44.py` validates profile isolation and creates a private `.hb42`
reference for the existing `Stage43PrivateCheck`. Use the owner APK only locally.
Only source and aggregate receipts go to public git. APKs, profiles, private
input ledgers, matrices, arrays, photo caches and panels remain private.
