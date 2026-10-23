# Stage42: experimental Phocus-derived portable colour renderer

The independently written C core now processes real phone RAW pixels. It matches
the original ARM64 colour routine on all 72 Stage41Y configurations (61,344/61,344
channels, zero tolerance), and on 512 stratified samples from the private phone
DNG (1,536/1,536 channels). This does not establish complete Phocus, camera ISP,
or phone-sensor look equivalence.

The Android change is an explicit saved-RAW preview under the existing native
development screen. Open a privately prepared `.hb42` file, render through JNI,
compare with the same-RAW neutral baseline, and copy the device report. The app
checks its RGB16 output against the host reference hash. Camera capture, existing
JPEG processing and diagnostics remain available. No device whitelist is added.

## Validation completed locally

- Eight analytical synthetic tests: neutral/dark values, both truncations, grid
  boundaries, output clipping, gain ownership, non-finite inputs and overlap.
- Original Stage41Y replay with the C core substituted as its comparator: zero
  differing output channels. Original code allowlist and memory guards retained.
- One complete 4096 x 3072 RAW processed with the new core (about 0.42 seconds for
  the C colour operation on the host; not phone or end-to-end timing).
- Private 1024 x 768 preview bundle and full-size images generated. Original DNG
  is unchanged and SHA-bound to the capture sidecar. Private outputs stay outside
  GitHub. The Android build workflow adds host Java/JNI/format checks and verifies
  both packaged ABIs and the existing signing identity.

## Input and gain ownership

`hb42_params` owns the two matrices, LUT, curve and shadow settings. `wb_owner`
distinguishes separate gain, matrix-owned WB and input-owned WB; the latter two
require separate gains to be unity. Exposure has a distinct positive scalar.
The core consumes bounded RGB16 and retains double arithmetic without contraction.
It reproduces the verified zero-gray-threshold/null-calibration SDR fragment.

The phone experiment reuses Stage24's DNG ForwardMatrix/CameraCalibration/
AsShotNeutral mapping to D50, including its unsupported-profile rejection. Stage30
applies the DNG GainMaps before its reference RGGB float demosaic. WB occurs once
inside the DNG camera-to-D50 transform. The Phocus input composition becomes
`B * A * phone_camera_to_D50`; the X2D sensor matrix `P` and its WB gains are absent.
The LUT temperature is manually fixed at 4000 K for this experiment; it is not a
new calibrated phone temperature estimate. Model 0, film 1, working-space code 0,
unity exposure, standard LUT and recovered shadow/gradation are used.

The current preparation helper rejects unsupported CFA, crop and opcode layouts;
it is not a universal phone decoder. The already-tested DNG has a full active area,
matching illuminant matrices, equal site black levels and GainMap-only OpcodeList2.
For this frame 1,227 negative demosaic channel samples are clipped at the RGB16
input boundary; no input channel exceeds unity. This RGB16 experiment does not
preserve floating-point scene headroom. Future capture integration must address
that explicitly. Source RAW bytes remain intact.

## Display and evidence boundary

Numeric Phocus space names are still unbound. The display adapter explicitly
decodes the recovered code-1 companding exponent and maps the internal basis
through the inverse recovered XYZ-to-internal transform, then the existing
Stage19 D50-to-sRGB conversion. This defines an experimental sRGB preview; it
does not relabel the vendor working-space code as sRGB or claim Android GPU parity.
Film 1's tone shaping remains in the decoded result.

The same-RAW neutral control uses the same prepared, quantized RGB and DNG matrix
with ordinary sRGB display encoding. The separate identity-chroma control keeps
the recovered tone/shadow behaviour. A private panel includes the existing Photon
JPEG, explicitly unregistered: its exposure, demosaic, noise reduction, sharpening
and geometry are not controlled. Inspecting the frame showed increased contrast
and deeper shadows; this is a cat/indoor scene, not a skin or foliage validation.
The calibrated LUT changes mean display-channel values by about 0.49/255 relative
to the tone-only control, with a maximum change of 36/255. Tone accounts for much
of the visible difference in this frame.

## Photon boundary inspected

`PostPipeline.BuildDefaultPipeline()` assembles Bayer2Float, demosaic, ABLC,
AutoExposureCurve and Initial/ModernInitial, then local contrast and sharpening.
Bayer2Float's `tofloat` shader uses the channel neutral in normalization/recovery;
Initial later combines neutral, sensor-to-intermediate, colour conversion, lens
shading, exposure and tone. Post-demosaic input cannot simply be treated as untouched
camera RGB. The Stage42 activity therefore does not hook that texture yet. A live
replacement must bind the actual WB/regeneration state and bypass the replaced
tone/exposure operations; adding another colour transform would apply them twice.

## Private data and build

The APK contains the core and import UI, not the Phocus binary or profile arrays.
`prepare_preview42.py` reads the separately supplied hash-pinned APK locally and
writes the private `.hb42`, JPEGs and receipt to an explicit output directory.
The bundle contains private calibration and pixels; do not upload it to public
GitHub, CI artifacts or releases. Inputs are bounded, format-length checked and
SHA-256 checked on import. The checksum provides integrity, not authentication.
The UI only reads a user-selected document and does not save over photographs.

Build: `.github/workflows/hb-photon-render42.yml`, application ID
`com.mwilliams.hasselbladphoton`, version `0.1-hb-render42` / `27191`, both
`arm64-v8a` and `armeabi-v7a`. Successful build is distinct from device testing.

```bash
python hasselblad_native_audit/phocus_port_stage42/test_core42.py -v
python hasselblad_native_audit/phocus_port_stage42/compare_native42.py \
  --apk /private/supplied.apk --receipt /private/native-comparison.json \
  --build-dir /private/build
python hasselblad_native_audit/phocus_port_stage42/prepare_preview42.py \
  --apk /private/supplied.apk --dng /private/input.dng \
  --sidecar /private/input.capture.json --out /private/preview
```

The next device test is to import the supplied bundle and confirm
`PASS_EXACT_RGB16`, inspect the baseline toggle, and report timing. The next
implementation step is direct saved-DNG preparation/import on Android, followed
by the explicitly bound single-frame capture integration. Stage42 is a working
renderer preview milestone, not a switch that changes newly captured JPEGs.
