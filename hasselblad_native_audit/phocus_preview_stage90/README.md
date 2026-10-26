# Stage90 — live preview follows tone selection

The owner reports Stage89's tone preview works, but can remain stale after a
different tone is selected. Stage89 loaded on attachment/resume and had no
direct subscription to profile, tone-pack or preview preference changes.
Stage90 connects committed changes to the live preview instead of relying on
the Activity restarting or resuming at the right time.

## Behaviour

- Curve 0 and curve 1 each use their own derived table. Switching back reuses
  that curve's table when it remains in the bounded cache.
- A replacement automatic profile is detected even if its film number is the
  same. The key includes SHA-256 of the complete profile and complete tone pack,
  including the no-film reference and output parameters.
- Importing a matching tone pack and changing the preview toggle update active
  previews immediately. Missing/incompatible data clears the old treatment;
  importing matching data restores the guide without a restart.
- A monotonically increasing revision invalidates already published frames as
  soon as a change is committed. Older asynchronous loads cannot overwrite the
  latest selection. One frame still snapshots one table for sharp and blur.
- Pause removes the listener and cancels pending work; resume subscribes before
  loading current settings. Detachment closes the worker/controller. No profile
  polling, file hashing or JNI calls run in the per-frame rendering loop.

The cache holds at most three immutable 4 KiB tables (12 KiB table payload),
plus hash keys and ordinary object overhead. It retains no profile, pack or
photo bytes. An active renderer can additionally retain its currently uploaded
table. Profile storage still verifies the same bytes after AtomicFile writes.
If post-write verification fails, invalidation is conservative and reloads the
actual file. Failed pre-commit writes do not announce a new selection.

The UI continues to offer recovered curves 0 and 1. An imported no-film (7)
profile retains the existing bypass. This does not add arbitrary tone editing
or apply Photon's separate custom post-processing tone setting to Hasselblad
JPEGs. It fixes selection tracking for the imported Hasselblad look system.

The Stage89 tone transform and shader arithmetic, RAW preparation, demosaic,
colour, sharpening, exposure and saved-photo processing are unchanged. The
preview remains an approximate tone guide; full preview/JPEG colour matching
and phone frame rate are not established by these tests.

## Validation

```sh
python3 hasselblad_native_audit/phocus_preview_stage90/pins90.py
python3 hasselblad_native_audit/phocus_preview_stage90/check90.py --work /tmp/hb90
python3 hasselblad_native_audit/phocus_look_stage84/check84.py --work /tmp/hb90-store
```

Checks run the production profile store, selector, settings, controller, cache
and Java/JNI tone builder together, using explicit JVM substitutes for Android
AtomicFile and preferences. They exercise live 1→0→1 switches with no lifecycle
restart, same-film imports, changed no-film reference, incompatible/matching
pack replacement, toggles, pause/resume, no-film bypass, write failures, bounded
eviction and an intentionally delayed old load followed by rapid changes.
An optional local `--private-pair profile.hbc pack.hbt` repeats these scenarios
with the owner's data; no private files are included in GitHub, CI or the APK.

CI also retains the profile-store persistence regressions, builds both ARM ABIs,
verifies signing/alignment and rejects private payloads. Source pins preserve
Stage89's shader proof; completed demosaic/sharpening tests are not repeated.

Install over Stage89 and switch curve 1 → curve 0 → curve 1 under Hasselblad
rendering. The preview should follow each selection when visible, including
after returning from settings. No new profile import, diagnostics or DNG export
is required when the existing profile and pack are compatible. This particular
fix still needs the owner's phone confirmation.
