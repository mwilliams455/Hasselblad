# Stage83: fixed-input tone comparison

Stage82 shutter and saved-DNG renders matched pixel-for-pixel on the device.
Stage83 adds a separate saved-DNG experiment: current profile, recovered film
codes 0 and 1, and the code 7 no-film control. The active profile, shutter
renderer, storage publication path, RAW preparation and demosaic are unchanged.

## On the phone

1. Install the Stage83 APK over Stage82; keep the current automatic `.hbc` profile.
2. In **Saved DNG colour**, open **Tone curve comparison**.
3. Import the separately supplied private `Hasselblad_Stage83_Tone_Comparison.hbt`.
4. Open the same saved DNG used for the Stage82 comparison.
5. Use **Next tone curve**; export the private tone comparison ZIP.

Each view has a full-resolution JPEG, and **Save displayed curve** exports the
selected view. Importing a tone pack does not replace the active `.hbc` profile.
One recovered view intentionally duplicates the current curve; it must match
exactly before JPEG encoding. A pack/profile mismatch stops the comparison.

## What stays fixed

One preparation and demosaic pass feeds a private RGB16 intermediate. Every
curve reads that same intermediate with the same DNG white balance, camera
matrix, automatically selected LUT, unit exposure, default SDR gradation and
sRGB finishing. The 32-site sensor-edge crop remains. Curve 7 retains the
companding needed by the pipeline; it is not an identity table or linear display.
The historical reconstruction is reused without brightness fitting or scaling.
Codes 0 and 1 are implementation labels, not claimed camera/film product names.

Only one full-resolution bitmap is allocated at a time. Four sparse previews
are kept for switching. Private intermediates are deleted before export; the
ZIP allowlist contains exactly four JPEGs, four PNGs and a JSON report. It never
includes DNG, profiles, curve tables or the intermediate RGB. A report records
source/intermediate hashes, current film code, LUT temperature, timings, exact
duplicate-view agreement and per-view display-code differences and endpoint
counts. White-channel counts are output endpoints, not proof of RAW clipping.

The phone's current profile remains the baseline. Curve 0 was substantially
brighter in earlier fixed-exposure trials; brightness alone is not proof of
better colour. Compare highlight detail, midtones, skin/neutrals and saturation
before deciding whether to expose a persistent curve selector. Custom curve
editing and changes to the capture default are later work.

## Validation and privacy

`python3 hasselblad_native_audit/phocus_tone_stage83/check83.py --work /tmp/hb83`
checks pack bounds/checksum/order, malformed floats and monotonicity, profile
compatibility, defensive copies, RGB stream truncation and numerical comparison
metrics. No demosaic fixture rerun is needed. CI preserves the Stage82 renderer,
capture and storage sources, compiles Android, and checks signing identity,
version, native ABI alignment and absence of private payloads.

The owner can generate the pack locally with `prepare_tones83.py --apk ...
--out /private/Hasselblad_Stage83_Tone_Comparison.hbt`. This reuses Stage41y's
previously verified `curve_oracle` on the pinned original library. The pack and
its receipt stay private; no curve arrays, original APK/libraries or photos go
into this repository or CI artifacts. A SHA-256 checksum checks integrity, not
publisher authenticity. Host/build success does not mean the Stage83 screen has
been tested on a phone or that phone sensor colour matches a Hasselblad sensor.
