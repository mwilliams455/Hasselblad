# Stage81: reduce filename-query overhead during shutter saving

Stage80 successfully published RAW and JPEG through the existing DCIM grant on
the phone. Its report exposed a much longer JPEG publication time. The old
`DocumentFile.findFile` collision checks enumerate document IDs and then query
each child's display name separately. A populated image folder can therefore
cause thousands of provider calls for each capture.

Stage81 replaces the two final-name collision scans with two independent cursor
queries requesting only display names. Row comparisons happen locally; there
are no per-child name queries. It preserves the granted folder, image MIME and
suffix, complete copy/close/size check, collision protection, provider rename,
updated URI, failure cleanup and private diagnostic retention from Stage80.
The parent-directory traversal remains unchanged.

Null cursors, missing name columns, failed or incomplete queries and unnamed
documents stop publication instead of treating an unreadable directory as empty.
Cancellation during a scan closes the cursor. Both collision checks are retained
so a name appearing during the copy is rejected before rename.

Each capture report now separates folder lookup, name checks, creation, opening,
writing, closing, size verification, rename, final-name verification and cleanup.
It records operation counts and scanned rows, without filenames or folder URIs.
Metrics are attached even when saving fails. Provider activity and thread
scheduling may still contribute time; improved phone speed is not yet proved.

No preparation, demosaic, colour/LUT, JPEG encoder or metadata bridge algorithm
changes are included. Stage81 remains compatible with the existing imported
profile and DCIM grant.

## Phone check

Install `HasselbladPhoton-0.1-hb-save81-27221.apk` over Stage80. Keep the imported
profile and folder access. Take one normal RAW+JPEG PHOTO using standard RAW,
4:3 and no digital zoom, confirm both saved, and export through **Saved DNG colour
→ Stage81 · shutter colour and save report**. The export is
`Hasselblad_Stage81_Shutter_Comparison.zip`.

There is no need to repeat demosaic fixtures. A later render of the same saved DNG
through Stage78 can complete the already planned shutter-versus-DNG colour check.

## Focused host verification

`python3 hasselblad_native_audit/phocus_save_stage81/check81.py --work /tmp/hb81-tests`
runs the 18 existing publication cases and 25 actual-adapter JVM cases. The latter
include the original 12 grant/path cases, successful folders containing 0, 1 and
10,000 images, and 10 query/collision/cancellation failure cases. Successful
publication must use exactly two bulk name queries, one final-name verification
and no per-child filename queries. Source bytes and existing files must survive
all rejected publications, and acquired cursors must close.

These are synthetic JVM provider checks, not Android performance measurements.
CI also builds/verifies the APK and asserts the validated renderer sources are
unchanged. Private photographs, profiles and capture reports are not bundled.

AndroidX source for the previous lookup behavior:
https://android.googlesource.com/platform/frameworks/support/+/9a5adc584f9897b185b3483f802f78b4e41d516a/documentfile/documentfile/src/main/java/androidx/documentfile/provider/DocumentFile.java
