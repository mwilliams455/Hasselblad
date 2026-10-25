# Stage79: shutter integration

Normal PHOTO capture now attempts the validated Stage78 preparation / Stage77
demosaic / automatic profile colour path. The integration runs before
Camera2ApiAutoFix.ApplyRes, frame packing and fp16 conversion. The resulting sRGB
pixels do not pass through Photon colour.

## First phone check

Install HasselbladPhoton-0.1-hb-shutter79-27219.apk over Stage78. Keep the imported
Stage56 automatic .hbc profile. Select standard RAW, 4:3, no digital zoom, and
RAW + JPEG, then take one normal PHOTO.

Open **Saved DNG colour → Stage79 · shutter colour and last capture report**.
The status should be HASSELBLAD_SHUTTER_RENDERED. Export its private comparison ZIP.
If it says PHOTON_FALLBACK, send that ZIP; its reason identifies the unsupported
capture condition. Do not repeat the earlier demosaic fixtures.

For a successful capture, also render **that capture's saved DNG** through Stage78
and export the scene comparison ZIP. We can compare decoded JPEG pixels and
orientation, and independently check the RGB16 windows. EXIF differs, so whole-file
JPEG hashes need not match. Exports exclude the complete DNG and profile.

After that roundtrip, check JPEG-only, RAW-only, a second queued shot,
portrait/landscape rotation and any other intended lens. These are capture
integration acceptance checks, not a repeat of the demosaic investigation.

## Contract and ownership

- One original RAW_SENSOR RGGB image, no crop/binning/packing/fp16, 128–8192
  sites per dimension and at most 16,777,216 sites.
- The observed stride and copy geometry are checked. Only row padding is removed
  for staging; the caller's buffer bytes, position and limit remain untouched.
- Existing evidence must prove the RAW surface, physical sensor, request, frame
  and timestamp. Its camera-ID proof currently requires API31+. The renderer
  never uses the mutable current-camera setting to select metadata.
- Both original active rectangles must equal the delivered RAW rectangle.
  Offset/scaled domains and digital/aspect crops use Photon.
- Dynamic white/black levels are preferred, static levels otherwise. Fractional
  black levels are rejected because the existing DNG writer accepts integers.
  Missing matrices, neutral or shading are rejected, never replaced by guesses.
- The existing DNG writer uses the matched original still directly, bypassing
  Photon Parameters/preview substitutions and sensor-specific colour overrides.
  Stage78's strict DNG checks still apply, including equal forward/calibration
  matrices when two are present. No new CFA or GainMap domain is claimed.

RAW+JPEG publishes the same staged DNG used by the headless renderer, plus JPEG95.
JPEG-only removes the private DNG. RAW-only needs no colour profile or renderer.
JPEG storage remains in sensor order with explicit EXIF orientation and sRGB.
The existing 32-site edge crop (33 at odd trailing edges) remains.

Before publication, unsupported inputs or ordinary rendering errors preserve the
input for Photon and record PHOTON_FALLBACK. Cancellation/memory exhaustion stop
the capture. Once publication starts, failures never retry Photon, preventing a
duplicate RAW when JPEG saving fails. Complete sibling temporary files are moved
without replacement. Owned frames and staging files are cleaned on completion or
failure; the next process removes staging directories left by process death.

## Verification

The focused host check compares 3,338,768 automatic ARGB pixels against independent
Stage76 preparation/scheduling with the Stage78 colour expression, across ten
synthetic DNGs and 1/4 workers. 491,520 exported RGB16 codes match Stage74.
Padding, immutability, orientation, cancellation, save-mode mapping and prevention
of incomplete/overwritten output files are checked.

The actual metadata adapter also runs against JVM API/writer/allocator spies to
check matrix order, original neutral, dynamic/static levels, orientation units,
shading bounds, padding and resource cleanup after injected write failure.
This does not test Android/native DNG IO; that roundtrip is a phone acceptance test.
CI compiles the Android app and retains the existing native/preparation regressions.

Stage79 is not device accepted until the shutter exports return. Phone performance
must include its new staging/saving costs. Functional parity does not prove physical
Hasselblad sensor colour equivalence. Only code and synthetic fixtures are public.
