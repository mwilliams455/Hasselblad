# Stage84: normal camera look controls

Stage83's phone comparison passed: its current-profile image and recovered
curve 0 were identical, and the baseline matched Stage82. Curve 1 was selected
for normal shooting. This build exposes that choice under **Settings →
Hasselblad rendering**, with active-profile status, curve 0/1 buttons, imports,
saved-DNG comparison and last-photo details.

## Use

Install over Stage83. Existing `.hbc` and `.hbt` imports remain available. Open
**Settings → Hasselblad rendering** and select **Use curve 1** if it is not
already active. No profile changes occur just by opening the screen. Once saved,
the curve remains selected across app restarts. Importing another `.hbc` replaces
the whole profile and therefore adopts its curve; the screen reads the actual
profile rather than keeping a second potentially inconsistent preference.

Take normal standard-resolution, 4:3, no-digital-zoom camera photos. Selection
applies to saved JPEGs; the live viewfinder has not yet gained this colour path.
RAW-only captures have no rendered JPEG curve. Existing unsupported-capture
fallback rules remain. The last-photo label reads the capture's recorded curve,
not the currently selected curve. Older reports without that field are labelled
as not having recorded it. The no-film control stays in the comparison screen.

## Data and capture behaviour

Curve switching validates the existing profile against the separately imported
private pack. Only the film-code field, the 65,536-entry film table, and the
checksum are replaced. All matrix, WB/exposure, LUT anchors, manual LUT, native
gradation/output data are byte-preserved. The resulting profile is reparsed.
Missing/incompatible packs and unsupported profiles do not change the profile.
A stale UI fingerprint is rejected and refreshed instead of overwriting a newer
import. Curve 0 → 1 → 0 restores the original bytes exactly.

Profile imports, curve selection, pack imports and capture profile snapshots are
serialized. Writes use Android AtomicFile and verify the saved bytes before
reporting success. A capture keeps its already-read profile for the entire render.
New capture reports record film code, profile and curve SHA-256, and the finishing
flag; JPEG ImageDescription records curve and selected automatic LUT temperature.
Report schema/export naming advances to Stage84; existing capture cache locations
remain so the previous report can still be viewed immediately after upgrading.

Preparation, demosaic, colour math, finishing kernels and public RAW/JPEG storage
are unchanged. Sharpening remains unported, and highlight reconstruction remains
disabled. No automatic preview match, physical sensor colour parity or full
Phocus equivalence is claimed.

## Focused validation

`python3 hasselblad_native_audit/phocus_look_stage84/check84.py --work /tmp/hb84`
checks reversible/idempotent curve selection, byte preservation, LUT temperatures,
stale selections, unsupported profiles/curves, and persistent-store write/rename/
cancellation failures. The Android Context/AtomicFile substitutes used by these
JVM tests are explicitly fault-injection adapters, not device validation.
Optional `--private-profiles CURVE0 CURVE1 PACK` checks that app selection produces
the exact private curve-1 profile previously delivered. Private data stays local.

CI pins the image-processing and public-storage sources to Stage83. The capture
integration diff is limited to the profile snapshot, receipt and EXIF metadata
changes and their UI wording. CI compiles Android, checks signing/version/ABI
alignment, and rejects bundled private profiles, curve packs, photos or original
vendor libraries. No demosaic test loop is added. Phone confirmation is still
needed for the new screen and per-shot curve metadata.
