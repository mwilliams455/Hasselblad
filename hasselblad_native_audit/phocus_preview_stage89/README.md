# Stage89 — optional live tone guide

The selected profile's film curve now has an approximate live viewfinder
representation. Settings → Hasselblad rendering → **Preview tone curve
(approximate)** switches it off/on. It defaults on when the existing automatic
profile and matching Stage83 tone pack are available. Missing, incompatible or
invalid data leaves the original feed visible. Existing imports are reused;
no vendor profile, tone table, photograph or original binary is bundled.

This is a **tone guide**, not full colour matching to the saved JPEG. The camera
HAL has already applied colour, white balance and device-dependent tone mapping
to the preview. Stage89 does not undo those unknown operations or apply the RAW
colour matrices/LUT to that feed. Clipped preview highlights cannot be recovered.
Phone visual agreement and frame rate still require a device check.

## Mapping

Build two 65,536-point neutral responses using the unchanged native finishing:
the imported no-film curve 7 and the selected curve. Curve 7 retains the native
companding; substituting an identity table would double-apply that encoding.
For display-encoded luminance, compose the selected response with the inverse
no-film response. Store 1,024 samples as packed RGB16 values in a 4 KiB RGBA8
texture. No phone photograph is sampled or retained to build this transform.

The shader decodes assumed sRGB preview values, maps luminance through that
relative table, then applies one common linear RGB gain. Limit the gain before
any channel exceeds the display gamut. This preserves RGB ratios rather than
adding colour calibration. Neutral black/white remain bounded. Curve 1 maps
below curve 0 in the owner's profiles, but this does not prove either matches
the HAL's absolute brightness or the captured JPEG. The curve 7 control bypasses
the tone guide entirely.

The same treatment precedes backdrop blur. Focus peaking is measured on the
original feed and overlaid after the tone treatment. Orientation, mirroring,
crop placement, focus coordinates and camera requests retain their old paths.
The guide is bypassed outside Photo mode, for RAW-only/HEIC, 16:9, Quad Bayer,
and cameras without RAW capability. Final still eligibility remains separately
verified by the unchanged capture path; a preview is never proof of eligibility.

## Ownership and fallback

Profile/pack snapshots are read together; expensive table construction occurs
off the GL/UI threads and outside the profile storage lock. A loader has one
worker and at most one pending request. Generation checks reject stale results
after another selection or pause. Resume/attachment refreshes the profile;
detachment shuts down its loader. Only an immutable 4 KiB table reaches GL.
Each rendered frame snapshots one table for both sharp and blurred views.
Texture upload happens on a table change or context recreation, not every frame.
No full-resolution bitmap, RAW readback or per-frame JNI call is added.

Shader compilation rejection falls back to the original-feed shader. Upload
failure disables the treatment until another table/context is available. The
preview preference is separate from diagnostics and sharpening. All Stage88
capture, native, calibration, output and save sources are pinned unchanged.

## Checks and phone use

```sh
python3 hasselblad_native_audit/phocus_preview_stage89/pins89.py
python3 hasselblad_native_audit/phocus_preview_stage89/check89.py --work /tmp/hb89
```

Host checks cover analytic identity/dark curves, invalid/non-monotonic responses,
plateaus, real Java/JNI finishing, profile immutability, preference independence,
missing data, cancellation and stale loads. Private profile/pack pairs can be
passed with repeated `--private-pair profile.hbc pack.hbt` locally only.

Mesa EGL compiles and links both production external-OES shaders and their
fallback variants. Numerical execution uses an explicit 2D camera-texture adapter:
disabled sharp and blur pixels must equal Stage88, including rotation/mirror
and focus-peaking cases; enabled sharp pixels must be within one RGB8 code of
an independent CPU calculation. These are not Android SurfaceTexture lifecycle
tests and do not establish phone preview/JPEG matching. CI builds both ARM ABIs,
checks the signing identity and native alignment, and rejects private payloads.
No completed demosaic or sharpening oracle work is repeated.

On the phone, keep the existing curve 1 profile and matching tone pack. Use
ordinary 4:3 Photo/JPEG mode. Compare the preview toggle, then take one photo and
judge whether preview brightness is useful relative to the saved JPEG. Also
check that returning from settings or switching lenses keeps the viewfinder
live. Diagnostics and DNG export are unnecessary for this first visual check.
