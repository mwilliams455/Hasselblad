# Stage82: check the destination without enumerating the image folder

Stage81 successfully saved RAW and JPEG on the phone. Its operation timings
showed that the two bulk filename queries still dominated JPEG publication time.
Provider work to enumerate a populated folder remains expensive even when the
app requests only one column.

Stage82 adds an exact-document lookup for the already supported primary Android
external-storage provider. It first compares the actual granted parent document
ID to the canonical destination's `primary:<relative path>` ID. Only an exact
match enables a child-document query built with `buildDocumentUriUsingTree`.
An unknown parent-ID mapping retains Stage81's bulk query; identifiers from
other providers or volumes are never guessed.

A missing document can return null or the AOSP tree-ancestry
`IllegalArgumentException`. Only the exact AOSP missing-child message matching
the requested target and granted tree is accepted as a missing candidate;
unrecognised argument errors fall back to the complete bulk check. Security
exceptions are never treated as absence. For missing or empty targets, Stage82 verifies that the parent still returns its
expected ID and directory MIME type before treating the filename as absent.
Permission exceptions, failed parent probes, inconsistent rows, incomplete/error
extras and cancellation reject publication. The two independent collision
checks remain, with the provider rename and final-name verification unchanged.
If the provider chooses a different final name, publication is rejected and
only the newly created owned document is cleaned up. Existing files are never
explicitly deleted or opened for writing by this path.

For a normal unused filename, there are two target queries and two parent health
queries per image, independent of sibling count. Reports retain Stage81 operation
timings and add target-query, parent-probe and bulk-query counts. A successful
fast-path publication scans zero unrelated filename rows. Parent folder traversal
is unchanged and remains separately timed.

Rendering, automatic colour/LUTs, RAW preparation, demosaic, JPEG encoding, save
modes and diagnostic retention are unchanged. This optimization targets the
Android storage provider, with no phone-manufacturer restriction.

## Phone check

Install `HasselbladPhoton-0.1-hb-save82-27222.apk` over Stage81, preserving the
imported automatic profile and DCIM access. Take one RAW+JPEG PHOTO using standard
RAW, 4:3 and no digital zoom. Confirm both files saved, then export **Saved DNG
colour → Stage82 · shutter colour and save report** as
`Hasselblad_Stage82_Shutter_Comparison.zip`.

Check save timings and the new lookup counters. No demosaic fixtures need to be
repeated. The later same-saved-DNG render through Stage78 remains the planned
shutter-versus-DNG colour comparison.

## Focused validation

`python3 hasselblad_native_audit/phocus_save_stage82/check82.py --work /tmp/hb82-tests`
checks 18 publication cases and 54 actual-adapter JVM cases. Coverage includes
the original grant/path restrictions, 0/1/10,000 sibling images, AOSP missing-child exceptions, null/empty
missing-document results, unrecognised-query fallback, literal spaces/Unicode/percent/hash filename characters,
opaque-ID fallback, early/late collisions, unavailable parent folders, query
errors, cancellation, cursor closure, retained failure timings and owned-file
cleanup. Source bytes and existing image bytes must remain unchanged on failure.

These are synthetic provider fixtures, not an Android performance measurement.
CI builds/verifies the APK and asserts the validated renderer sources remain
unchanged. Stage82 speed still requires phone confirmation. No private capture,
profile or full DNG is uploaded or bundled.

Provider references:

- Primary volume/path IDs and missing-file behavior:
  https://android.googlesource.com/platform/frameworks/base/+/2e371c1b5a8326c1af21b6d12f90f61591d0b1c9/packages/ExternalStorageProvider/src/com/android/externalstorage/ExternalStorageProvider.java
- AOSP missing-child ancestry exception:
  https://android.googlesource.com/platform/frameworks/base/+/5d8e1b2adf0a8d59ea51eadc8d7f2e2ca093a204/core/java/com/android/internal/content/FileSystemProvider.java
- Framework conversion of missing-document queries to null:
  https://android.googlesource.com/platform/frameworks/base/+/HEAD/core/java/android/provider/DocumentsProvider.java
- Public single-document query contract:
  https://developer.android.com/reference/android/provider/DocumentsProvider#queryDocument(java.lang.String,java.lang.String[])
