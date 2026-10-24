# Stage48 — general colour-domain and metadata audit

Date: 2026-10-24. Following the owner's concern about scene-specific tuning,
this stage freezes the Stage47 highlight trials and tests the current colour
path using synthetic colour targets, independent standard colour mathematics
and metadata fixtures. No photographic hue, exposure, tone or saturation fit is
made. The recovered C colour core, profile payloads and current look selection
are unchanged.

## General finding: normal-table coordinate limits

A 17×17×17 lattice of linear-sRGB colours spanning 0.005–0.9 is transformed into
the room DNG's camera coordinates. All 4,913 targets fit inside the accepted
camera-RGB input range. The diagnostic removes the LUT look, film tone and
shadow shaping, leaving an identity chroma table and companding-only curve.
It compares the result with direct DNG-to-D50-to-sRGB conversion of the same
quantized samples.

| Control | Table-edge clamps | Maximum displayed channel error | Mean absolute channel error |
| --- | ---: | ---: | ---: |
| Current normal coordinate range, all 4,913 targets | 27 | 42/255 | 0.10489/255 |
| Current range, 4,886 in-range targets only | 0 | 1/255 | 0.03636/255 |
| Enlarged coordinate control, all targets | 0 | 1/255 | 0.03759/255 |

The affected targets are saturated blues and nearby blue-magenta directions.
The displayed outputs for the in-range subset are exactly unchanged by the
enlarged-coordinate control. The large discrepancy therefore comes from finite
table-coordinate coverage, not a scene-dependent colour fit. It is present even
when the look is disabled, so the table boundary must not be mistaken for an
intended LUT hue correction.

The enlarged control uses the previously verified Stage41X table-expansion
operation with the current space0 matrices and transfer. Original initialization
selects expansion together with other working-space changes. Consequently this
mixed control is **not a verified native Phocus mode**, and it is not deployed.
The current C routine still reproduces the recovered bounded algorithm. This
finding concerns the suitability of that bounded route for the general phone
adaptation; it does not prove that the original algorithm is defective.

On the two retained phone scenes, switching only this diagnostic coordinate
range has small average effects: 0.00204/255 in the room and 0.00017/255 in the
earlier indoor scene. Table clamps fall from 6,330 to 2,182 and from 544 to 151,
respectively. It therefore does not explain the room's overall appearance and
does not establish broad photographic improvement.

## Input/output structure checks

- 256 synthetic DNG calibrations agree with an independent NumPy implementation
  of the ForwardMatrix equation to 4.45e-16. They include non-diagonal camera
  calibration, analog balance and arbitrarily scaled neutral vectors.
- The saved room DNG transform agrees with that independent construction to
  2.23e-16. The standard D50-to-sRGB transform agrees to 1.34e-15.
- The stored input/output basis matrices close to 1.34e-15. The actual recovered
  pixel routine uses an implicit unit coefficient for Y; accounting for this
  produces a small 0.000226 matrix discrepancy and 0.000260 maximum neutral-white
  channel discrepancy. The identity controls above include this real behaviour
  and integer lookup/encoding. No recovered coefficient is edited to hide it.
- The same 4,913 XYZ targets are represented through eight camera encodings:
  two retained phone metadata transforms and six synthetic encodings. With each
  of the two recovered film curves and the same real LUT, the maximum displayed
  channel difference between encodings is one level. Worst mean difference is
  0.00543/255. This checks composition and quantization, not eight physical cameras
  or the spectral accuracy of the phone under eight illuminants.
- Two 512-step neutral ramps have at most one level of displayed channel spread.
  A pre-colour ×2 exposure scalar agrees exactly with doubled input codes across
  12,288 channels. This verifies the port's placement; it does not resolve all
  upstream native Phocus source-gain state.
- Intentional missing transfer decode, transposed output matrix and duplicated
  WB controls are detected. Their mean channel errors exceed 32/255, while the
  valid in-range identity control remains within one level per channel.

The current mathematical composition is internally consistent within its tested
domain. These checks cannot establish that the DNG's calibration is spectrally
accurate for a real scene, or that replacing the Hasselblad sensor-specific
input with phone DNG D50 values reproduces complete HNCS rendering.

## General metadata fixes

The Java reader previously used `CameraCalibration1/2` without checking the
camera/profile calibration signatures. The DNG specification requires matching
signatures; otherwise identity calibration is used. Both missing signatures
default to empty and therefore match. This selection is now applied before
reading/validating calibration matrices in both the tile and whole-preview
paths. In particular, unequal calibration matrices belonging to a mismatched
profile no longer trigger a false dual-illuminant rejection.

Both readers also reject nonzero `ColorimetricReference` values because their
pipeline assumes scene-linear input. The Python metadata path applies the same
selection, accepts the specified SHORT form of `AsShotNeutral`, and checks the
normalized neutral rather than incorrectly assuming its largest component is
already one.

Fourteen synthetic DNG fixtures cover missing, equal, unequal, one-sided and
empty signatures; BYTE and ASCII signatures; ignored unequal calibration
matrices; scaled and SHORT neutrals; output-referred input; and an unterminated
BYTE signature. The old compiled Java reader fails 14 of the 28 tile/preview
checks; the updated source passes all 28. Python passes all 14 cases. The prior
65-check Stage43 Java/JNI suite also passes. These synthetic fixtures and checks
are added to the existing Stage43 build workflow; that workflow has not been
dispatched for this research branch.

After compiling the updated reader, the room DNG is read and rendered again
through host JNI. All 13 retained binary/PNG outputs agree byte-for-byte with
Stage46, including 2,359,296 prepared RGB16 channels, camera/output matrices,
the neutral baseline, and all three private profiles' RGB16 and displayed PNGs.
The room has neither signature tag and uses the default scene-referred input,
so these fixes are not presented as a correction to its appearance. Source DNG
and profile bytes remain unchanged. No new APK or device test is claimed.

## Remaining work and order

1. Establish the correct native working-space/output route and how it handles
   colours outside the normal table. Compare its matrices, expanded LUT and
   transfer together; do not enable the mixed enlarged-grid control as a fix.
2. Resolve exposure normalization and native source-gain ownership across inputs.
   The room omits BaselineExposure and profile exposure offsets; that does not
   establish a universal exposure normalization rule for other DNGs.
3. Validate real phone colour accuracy and full rendering across illuminants,
   using controlled targets and known-settings Phocus references where possible.
   Equivalent synthetic XYZ and earlier camera JPEGs are insufficient for this.

The original Phocus APK is absent locally and was not retrieved. This audit
uses retained private profiles and previously verified reconstruction source.
No new original ARM64 replay or complete GPU-path equivalence is claimed.
Differing dual-illuminant forward/calibration matrices still require a separate
interpolation implementation; the current reader explicitly rejects that case.
The actual pipeline still clips negative/output-over-range values at its stated
boundaries and does not implement a general floating-point gamut mapper.

## Reproduction and source references

`make_metadata_fixtures48.py --out <scratch-directory>` generates synthetic DNGs
and checks Python metadata against independently calculated matrices.
Compile `Metadata48Check.java` with the existing host reader/JNI classes, then
run it with that directory. `--allow-old-failures` is only for reproducing the
old binary's failures and must not be used as a passing test.

`audit_boundaries48.py --help` lists the retained private inputs needed for the
colour-domain checks. Its `--out` directory contains the private input ledger
and synthetic diagnostic image; only its explicit `--safe-receipt` is public.
Assertions must remain enabled. The normal host environment and existing native
compiler/JNI setup are used. No new calibration or photographic look is fitted.

- [Adobe DNG 1.7.1 specification](https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf): printed pp.36–37 (neutral/exposure), 47–48 and 100 (calibration signatures), 103 (ForwardMatrix mapping).
- [ICC sRGB registry](https://registry.color.org/rgb-registry/srgb): standard primaries, D65 white and piecewise output transfer.

Public evidence contains aggregate errors, counts and flags. Private profiles,
matrices, pixel buffers, input hashes and photographs remain outside public git,
CI and APK assets. The diagnostic colour-strip image is saved privately and is
explicitly labelled synthetic; it is not a photograph or a Hasselblad reference.
