# Stage91 — saved-JPEG sharpening controls

The normal camera previously exposed sharpening only as an on/off switch with
fixed recovered values. **Settings → Hasselblad rendering → Adjust sharpening…**
now exposes strength 0–200 and fine-detail threshold 0–32. Save commits the pair
together. Cancel discards edits; Restore 100 / 0 resets the dialog's draft.
The existing **Sharpen saved JPEGs** switch remains independent and immediate.
Opening settings does not change anything. Existing on/off selections migrate
without changing their output; new installs remain off.

Strength 100 / threshold 0 is the previous enabled behaviour. Strength 0 uses
the exact unsharpened finishing path, avoiding RGB14 quantization too. Increasing
threshold suppresses sharpening of smaller luminance differences; it is not
denoising. Radius remains 1 and dark limit 10. These are bounded controls over
the recovered CPU operation, not named camera looks or a claim of matching the
Phocus UI scale. Native ranges are broader; this increment intentionally offers
only strength 0–200 and threshold 0–32.

## Capture and preview ownership

One immutable enabled/strength/threshold tuple is taken when capture processing
starts, before Photon metadata modifications. All bands and metadata use that
tuple. Changes after this point affect later renders. This is not a shutter-press
snapshot or a new exposure-control mechanism. The profile retains its own existing
snapshot. The normal JPEG path passes the tuple into the stream after film/default
gradation and before output conversion. EXIF records applied values even with
diagnostics off. Optional diagnostics record requested and applied settings;
RAW-only does not claim applied sharpening. Temporary DNG/public save behaviour
is unchanged.

Sharpening remains **saved-JPEG only**. The UI explicitly says that the live
viewfinder does not display it. Stage90's approximate tone guide and live curve
selection remain unchanged. These settings do not affect the tone table, so they
do not enter its cache identity or trigger preview table reloads. No false
sharpening preview is applied to the HAL's already sharpened feed.

Settings persist as one versioned preference value. Synchronized reads/writes
avoid mixed tuples. A failed commit restores the previous tuple in memory and
reports failure; Android filesystem durability still requires device testing.
Invalid stored tuples fail closed to off. No native math, profile payload,
colour/LUT, RAW preparation or demosaic is changed. The JNI bridge accepts the
two additional parameters; the recovered Stage85 kernel is pinned unchanged.

## Checks

```sh
python3 hasselblad_native_audit/phocus_controls_stage91/pins91.py
python3 hasselblad_native_audit/phocus_controls_stage91/check91.py --work /tmp/hb91
python3 hasselblad_native_audit/phocus_preview_stage90/check90.py --work /tmp/hb91-preview
```

Focused checks run production settings, stream, scene renderer and JNI. Stage87
RAW/demosaic fixtures are explicit adapters, not another demosaic validation.
They cover legacy enabled/off migration, saved values/reload, failed disk commit
with changed memory, rollback, invalid tuples, bounds, concurrent tuple changes,
in-flight rendering, off/default equivalence and actual parameter effects.
Whole-frame calls to the unchanged kernel independently check streaming output
at 1/7/64-row partitions, width 1 through 4032 and partial final bands. Default
and cancellation regressions are retained. Stage90 checks retain rapid tone
switching and stale-load protection. CI builds both ARM ABIs with the existing
signing identity, verifies 16 KiB native alignment and excludes private payloads.

Host success is not phone validation. Stage90 live switching and these Stage91
controls await the owner's phone check. Full preview/JPEG colour matching is
still outstanding.

## Minimal phone check

Install over Stage90; existing profiles/imports remain available. Leave diagnostics
off and use ordinary 4:3 JPEG capture. Turn sharpening on. Start with strength
50 and threshold 8 as a trial, then compare with 100 / 0 on similar fine detail
and indoor grain. This trial is not a calibrated recommended profile. Confirm
values survive closing/reopening the app and the photos save/open. Switch off
or use strength 0 for the established unsharpened output. Also check curve
1 → 0 → 1 updates the tone preview; no DNG export is needed.

See [CONTROL_INVENTORY.md](CONTROL_INVENTORY.md) for the code-backed inventory
and the next ownership work.
