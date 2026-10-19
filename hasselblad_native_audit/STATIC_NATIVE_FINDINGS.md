# X2D II native firmware audit

## Verified input and extraction

The public Hasselblad downloads API returned product 173, release item 1568,
version 1.3.16.2:

- API: https://api.hasselblad.com/products/downloads/173/firmware
- Official CIM: https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.3.16.2/X2DII_100C_v1_3_16_2(1).cim
- Downloaded bytes: 364,814,336.
- SHA-256: `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6`.

That digest exactly matches the X2D II 1.3.16.2 profile in the independently
published QEMU DevKit at commit
`d82dc3b0faa6456c260378df6352a07f929caed2`:
https://github.com/derrickyau9/Hasselblad-X-System-QEMU-DevKit/blob/d82dc3b0faa6456c260378df6352a07f929caed2/devkit/firmware.py

`extract_official.py` uses the pinned DevKit CIM reader to read the container,
then reconstructs the full Android OTA system and vendor partitions. Only
regular files are copied to the host. Symlinks are recorded in manifests and
are not materialized. No firmware executable or update script is run by the
extractor. The original download is retained unchanged.

The OTA ZIP SHA-256 is
`7ccd5df4dab8d098d9895973fb62bcedcaa379f75fb044408a8263ce2d1f9a57`.
The reconstructed system image is 746,586,112 bytes and yields 1,524 regular
files plus 171 symlinks. The vendor image is 134,217,728 bytes and yields 93
regular files. All regular files have hashes in the partition manifests.

## Confirmed platform

The extracted `system/etc/VERSION` reads `1.3.16.2`.
The extracted `system/build.prop` contains:

```properties
ro.build.version.incremental=316
ro.build.version.sdk=28
ro.build.version.release=9
ro.product.model=Android HB722 on Eagle2 HB722
ro.product.name=eagle2_hb722
ro.product.device=eagle2_hb722
ro.product.cpu.abi=arm64-v8a
ro.product.cpu.abilist=arm64-v8a
```

This is direct evidence of the firmware's Android 9 / API 28 / ARM64 platform.
It does not, by itself, establish application-namespace compatibility on a
phone running a different Android build.

## Static native dependencies

`audit_dependencies.py` inventories ELF dynamic dependencies, symbol-version
requirements, undefined symbols, constructor metadata, load segments, and
hashes. Its current report covers 366 library files. These are candidate
libraries; a name or successful load does not identify the saved-image colour
transform.

| Candidate | Full DT_NEEDED closure, including candidate and core runtime | Closure bytes |
| --- | ---: | ---: |
| libdcam_adj_product.so | 6 | 2,526,392 |
| libadj_base.so | 65 | 32,568,984 |
| libaaa.so | 65 | 39,924,592 |
| libdcam_pp_base.so | 67 | 33,370,952 |
| libalgo_share.so | 70 | 34,168,920 |
| libdcam_pp.so | 73 | 37,341,824 |
| librcam.so | 92 | 57,017,192 |

All dependencies in those closures are present in the extracted `system/lib64`.
The observed `libaaa.so` hash is
`7d6164eccc734de7087bb778ee72f17a0b3ccf6c0d1f20092c7ebe74a86574ba`, matching
the X2D II AFS research input hash. `libaaa.so` preserves `.gnu_debugdata` and
has 3,876 defined global/weak dynamic symbols.

The short path from `libaaa.so` to a private Android linker API is:
`libaaa.so → libduml_util.so → libutils.so → libvndksupport.so`.
The latter imports `android_get_exported_namespace` with a `LIBC_PLATFORM`
version requirement. Other dependency paths reach `libion.so`, `libteec.so`,
and the camera's hardware abstraction libraries. A dependency's presence does
not prove that a selected CPU routine calls it.

Android's application linker namespace restrictions and the need to include
non-NDK dependencies are documented by Google:
https://developer.android.com/about/versions/nougat/android-7.0-changes#ndk
https://source.android.com/docs/core/architecture/vndk/linker-namespace

The original code also carries concrete 4 KB page assumptions in some ELF
segments. For example, `libaaa.so` has a PT_LOAD at file offset 0 and virtual
address 0x1000, alignment 0x1000. This mapping is not congruent for an ordinary
16 KB page load. 89 of the 366 inventoried libraries have at least one such
noncongruent mapping. This is a separate device/runtime compatibility check;
the initial matching Android 9 execution baseline should retain 4 KB pages.
Google's current page-size guidance:
https://developer.android.com/guide/practices/page-sizes

## Model assets: scope of the encryption statement

The vendor partition contains the encrypted `vendor/model/ml` and `vendor/etc/ml`
assets discussed in the existing research. It also contains a separate NNF
model group: `parsing.json`, `skin_mask.json`, `person_detection.json`, and
`nnpd_depth.json`. Those files begin with bytes `00 56 34 12` and have readable
JSON node descriptions beginning at byte 12. They are not the same IMaH `.enc`
containers. Their original proxy configuration names DSP ICC device channels
and ION heaps 18/19. This observation does not establish that they implement
HNCS, or that their configured inference path works on a phone.

## Scope of this report

This report establishes authentic firmware acquisition, reproducible offline
extraction, the native platform, and static dependency constraints. Runtime
probe evidence is maintained separately under `runtime_probe/`. Photographic
function selection and recovered call signatures are maintained separately by
the colour/WB audit. Full saved-image rendering remains a separate test from
library loading or a successful call to one mathematical helper.
