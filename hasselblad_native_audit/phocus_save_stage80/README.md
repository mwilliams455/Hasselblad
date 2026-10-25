# Stage80: publish shutter JPEG/DNG through the granted DCIM tree

Stage79 could finish RAW preparation, demosaic, colour and JPEG encoding but fail
when creating a generic `.tmp` file inside public DCIM. Its host filesystem tests
did not model Android's scoped-storage restrictions. The failure was in public
file publication; it was not evidence of a demosaic or colour failure.

Stage80 resolves the app's existing persisted primary-DCIM document-tree grant.
It creates a uniquely named JPEG or DNG document with the matching image MIME
type, streams the complete private output, checks the written length, then uses
the document provider to rename it to the requested capture name. It retains the
provider's updated URI after rename. It never uses a direct public `.tmp` path.

Existing final names are checked before creation and again before rename. The
primary external-storage provider handles the final rename; this path never
deletes a pre-existing destination. A failed/partial owned document is deleted,
and cleanup failures are attached to the original exception. Cancellation is
checked before creating, while copying and before renaming. JPEG-only, RAW-only
and RAW+JPEG routing retain the Stage79 contract.

The capture report records the failure stage, whether rendering completed and
separate RAW/JPEG save timings. If publication fails after rendering, the private
diagnostic ZIP retains the completed JPEG and small Bayer/RGB samples. The full
DNG and imported colour profile are never included in that ZIP. The previous
Stage79 failure export contained only its report; it cannot recover that image.

## First phone check

Install `HasselbladPhoton-0.1-hb-save80-27220.apk` over Stage79; retain the imported
automatic profile and existing DCIM access. Take one normal RAW+JPEG PHOTO with
standard RAW, 4:3 and no digital zoom. Confirm both files appear, then use
**Saved DNG colour → Stage80 · shutter colour and save report** to export the
last shutter comparison ZIP. If saving still fails, send this ZIP first.

After saving works, the same saved DNG can be rendered through Stage78 for the
previously planned same-capture comparison. There is no need to repeat the
demosaic fixtures for this storage fix. JPEG-only and RAW-only, gallery orientation
and a second queued capture remain normal capture acceptance checks.

## Automated checks and limits

`python3 hasselblad_native_audit/phocus_save_stage80/check80.py --work /tmp/hb80-tests`
checks 18 publication cases: JPEG/DNG MIME and suffix, exact transferred bytes,
creation/open/write/close/length/rename errors, cancellation, collisions, provider
name changes and cleanup failures. Private source bytes remain unchanged.

The actual Android adapter is compiled against JVM document-provider spies for
12 cases covering root/DCIM/subfolder grants, most-specific selection, updated
rename URIs, read-only/unrelated/secondary-volume grants, authority checks and
canonical path confinement. This is not an Android/FUSE device test.

CI builds the Android APK and asserts that validated RAW preparation, demosaic,
colour, native libraries, headless renderer and original-metadata DNG bridge are
unchanged. Stage80 requires phone confirmation that Android publication succeeds.

API reference: https://developer.android.com/reference/android/provider/DocumentsContract
