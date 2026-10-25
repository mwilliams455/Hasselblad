# Stage75: saved-DNG Android demosaic + colour/LUT test

This is an installable diagnostic, not a replacement camera renderer. It uses the exact
Stage74 native sources from `1b7078f206ece1ca224cb6f99eff0be988b6796f` and the existing
Stage43–58 colour/profile and finishing route. No vendor binaries or private profiles
are bundled. The APK supports arm64-v8a and armeabi-v7a without a manufacturer lock.

## Phone test

1. Install `HasselbladPhoton-0.1-hb-device75-27215.apk` as an update to the existing
   Hasselblad Photon development app. Existing signing identity, app ID and profile retained.
2. Open the existing **Saved DNG colour** screen. Import the existing private Stage56
   `.hbc` profile if not already imported. Open **Stage75 · demosaic + colour tile test**.
3. Tap **Run device check**. Three bundled synthetic inputs are rendered through Android
   JNI and compared against host RGB16 output: 26,715 unsigned channel values. Each
   fixture is rendered twice, input immutability is checked, and malformed JNI calls
   must reject without modifying buffers. A mismatch disables saved-DNG testing.
4. If the check passes, select a standard-resolution saved DNG. Five 64×64 output
   crops are rendered (centre and four near-corner interior regions). Each input is
   a 128×128 RGGB Bayer region containing actual sensor samples and a 32px halo.
5. Use **Next crop** and **Next colour / LUT view** to compare neutral DNG colour,
   the profile's manual LUT, and metadata-selected automatic LUT. The screen enlarges
   tiny crops; it does not display a complete 12MP rendered photograph. Missing profile
   or unsupported automatic-selection metadata is explicitly labelled. No highlight
   reconstruction or double pre-demosaic WB is applied.
6. Export the **private comparison ZIP** and send it back for host comparison. Export
   the synthetic ZIP first if you want that evidence retained separately; opening a
   DNG replaces the in-memory report/export. Copy the report for a quick text summary.
7. Reopen the screen, repeat the test, and check that ordinary Photon capture still
   works on your phone. Cancellation/reopen, UI behaviour and real handset capture
   have not been verified by host or build tests.

The ZIP includes actual prepared Bayer and RGB16 bytes. It is private photo evidence:
never post it to public CI or a public repository. No profile, matrices, DNG filename,
full RAW, device serial, or private image hashes are exported. Physical camera identity
is not guessed from the current Camera2 session: it is explicitly unestablished.
Provide the lens/mode alongside the ZIP if testing more than one.

## Scope and interpretation

Synthetic device parity can be determined on the phone. Saved-DNG device parity is
**pending until its exported input/output are replayed on the host**. Colour/LUT
views before that comparison are exploratory. This does not establish original
Phocus DNG preparation, physical Hasselblad sensor colour matching, full-frame edge
handling, arbitrary CFA/modes, live preview, or 12MP performance.

The importer retains the strict standard 16-bit uncompressed RGGB strip-DNG,
full active area/crop, ForwardMatrix and same dual-matrix constraints of Stage58.
It normalizes `(raw-siteBlack)/(WhiteLevel-maxBlack)`, clamps, applies ordered
GainMaps with existing float rounding and clamp semantics, then truncates each
Bayer site to uint16 **before** native interpolation. Stage58 instead quantizes
its float bilinear RGB after interpolation; those inputs must not be conflated.

The new reader shares metadata helpers but does not alter Stage58 preview code.
Its five regions avoid outer-frame extension entirely. Export layout is uint16 LE,
RGB interleaved, tightly packed, in sensor orientation; the on-screen bitmap alone
is rotated. Native output remains pre-colour internal linear RGB16. Colour outputs
are identified separately (manual native-finished output is sRGB16 when finishing
is present; older profiles use their existing display adapter).

## Host verification

```bash
python3 hasselblad_native_audit/phocus_device_stage75/check75.py \
  --work /tmp/hb75-tests --jni "$JAVA_HOME/include"
python3 hasselblad_native_audit/phocus_device_stage75/device75.py compare /private/device.zip
```

The test suite checks exact synthetic JVM/JNI output, independent preparation of
20 tiles across little/big-endian DNGs, multistrip rows, unequal black levels,
spatially varying four-phase GainMaps, ordered clipping/attenuation, orientations,
malformed files, cancellation, repeatability, and export comparator corruption.
Five synthetic end-to-end colour cases also exercise the neutral adapter, manual
LUT, automatically selected LUT, native finishing and display conversion.
The exported-input comparison checks input layout first, then every unsigned RGB16
channel. It stops on the first failing tile and reports the first pixel/channel.
It proves execution parity for those exported inputs, not an independently
validated phone-to-Phocus RAW preparation contract.

CI additionally runs Stage74 ASan/UBSan and output arithmetic tests, compiles both
Android app ABIs, verifies 16KiB ELF load alignment, signing identity, version and
packaged synthetic fixture bytes. None of those checks substitutes for a handset run.
