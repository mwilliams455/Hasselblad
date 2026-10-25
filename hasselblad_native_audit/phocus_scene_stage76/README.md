# Stage76: a full-scene interior render with colour/LUT comparison

Stage75 passed on a real ARM64 phone: five saved-DNG crops / 61,440 final
linear RGB16 channel values matched the independent host byte for byte.
Stage76 keeps that exact Stage74 64×64 renderer and assembles a complete
sensor-interior image from real overlapping Bayer neighbourhoods.

## What to test

Install `HasselbladPhoton-0.1-hb-scene76-27216.apk` over the current app.
Open **Saved DNG colour → Stage76 · full-scene colour and LUTs**. Use the
already imported Stage56 automatic `.hbc` profile and select the saved DNG.
The band-integration check runs automatically; no repeated manual Stage75
fixture procedure is required.

After rendering, use **Next colour / LUT view** for neutral DNG colour,
manual LUT and automatic LUT. All three previews cover the same scene.
**Save full-resolution automatic-colour JPEG** saves the automatic LUT plus
native gradation/finishing/sRGB route. The manual and neutral views are scene
previews capped at 1,048,576 pixels. The app explicitly identifies which
view is saved in the full-resolution JPEG.

Export the private comparison ZIP to assess the complete image. It includes
that JPEG, the three oriented PNG previews, timings/report and up to three
small Bayer/RGB16 samples taken from the assembled bands, including windows
crossing horizontal tile joins. Do not publish the ZIP, pixels or identifying
metadata to public GitHub. It excludes the original DNG, colour profile and
calibration matrices. The source DNG is opened read-only and its private copy
is checked for changes then removed. Ordinary shutter capture remains Photon.

## Border and geometry contract

No padding is invented for outer sensor edges. Output crops 32 sites on the
top/left and 32 sites on the bottom/right (33 on an odd trailing dimension),
so every Stage74 input has its real 32-site halo. A 4096×3072 input produces
**4032×3008 = 12,128,256 pixels**, with stored JPEG orientation copied from the
DNG. This is an explicit small crop, not native Phocus outer-border parity.

The existing standard-resolution uncompressed 16-bit RGGB DNG import
restrictions remain. All tile origins retain the global RGGB phase. Partial
trailing bands/tiles select a crop within another valid 64×64 Stage74 output,
without adding arbitrary shapes to that renderer's contract. Finishing runs
on bounded strips under the existing colour JNI pixel limit. Full-frame
linear RGB buffers and three full-resolution bitmap copies are avoided:
keep one prepared Bayer frame, one full-resolution automatic-colour bitmap,
small strip buffers and three bounded scene previews. Cancellation is checked
between bands and colour stages. Memory exhaustion and unsupported metadata
fail explicitly; no alternative renderer silently substitutes for Stage74.

## What the evidence establishes

- Existing Stage75 preparation, JNI and colour regression checks remain.
- Independent prepared-Bayer fixtures are also decoded as whole images and
  compared to the already checked Stage75 tiles.
- Band output is checked against separate Stage74 calls across minimum, odd
  and partial dimensions. Eight synthetic spatial patterns exercise shifted
  horizontal/vertical overlaps and windows spanning tile joins.
- A full 4096×3072 synthetic input exercises coverage of all 12.13MP output
  pixels. Its constant expected result is independently known. The measured
  host time is not a phone performance estimate or a vendor full-frame oracle.
- ASan/UBSan check native bounds, alias rejection and output guards, including
  the maximum band width. The original Stage74 source and camera pipeline are
  unchanged.
- The five private Stage75 inputs also passed 32×32 versus 64×64 overlapping
  crop comparisons at eight offsets each (122,880 RGB16 codes, zero differences).
  This is the same single source photograph, not five independent scenes.

The original Phocus outer-border extension, original DNG import, physical
sensor-to-Hasselblad colour calibration, broad scene quality, full-scene phone
performance and lifecycle behaviour remain separate evidence questions.
Neither a successful build nor the synthetic coverage check resolves them.

## Reproduce

```bash
python3 hasselblad_native_audit/phocus_scene_stage76/check76.py \
  --work /tmp/hb76 --jni "$JAVA_HOME/include"
sh hasselblad_native_audit/phocus_scene_stage76/run_sanitizers76.sh /tmp/hb76-asan
python3 hasselblad_native_audit/phocus_scene_stage76/compare76.py /private/scene.zip
```
