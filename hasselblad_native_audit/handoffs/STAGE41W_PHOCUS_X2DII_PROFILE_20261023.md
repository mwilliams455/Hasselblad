# Stage 41W: X2D II profile selection, decoding and native loading

The supplied Phocus Android APK contains an accessible X2D II colour profile. All 26 bundled colour-map assets decode to XML property lists. The library's original profile selector maps the sensor/filter values found in all four supplied X2D II RAWs to profile `0x0616`, selecting `bohnjuhtuvuvtxyydb56.dat` under the tested normal configuration. The original native profile loader then reconstructs five matrices and six chroma tables from that decoded profile.

This removes the unidentified-profile obstacle recorded in Stage 41V. It does not establish a complete RAW render, equality with the in-camera MAIN ISP, or a ready-to-ship phone renderer. The result concerns the exact supplied Phocus APK and an explicitly controlled native execution environment.

## Inputs and identity

The APK and `libcrosssdk.so` are the same inputs used in Stage 41V:

| Input | SHA-256 |
| --- | --- |
| Supplied Phocus 1.1.0 APK | `5ee52bbb2b7a3fa708628ba251b409a551ae099697668427cf54b523328ccf68` |
| `lib/arm64-v8a/libcrosssdk.so` | `d757237554529f8ab485f88f2c5e5399fbc8d56035c79b8e057b41a40fd055e4` |

The audit reads these from the private APK and verifies both hashes. It also reads camera model and three integer MakerNote fields from the four existing `.3fr` samples. No RAW image data is decoded or rendered in this stage. Stage 41V's limitation remains: the APK signing certificate has not been independently authenticated against a manufacturer distribution.

## Camera-to-profile link

All four samples identify their model as `X2D II 100C` and agree on the following MakerNote values:

| Field | Value | Native evidence |
| --- | ---: | --- |
| Sensor, tag `0x11` | 22 | `CRawImageFileData::CCDType` requests this tag from RAW IFD index 3 |
| Camera back, tag `0x12` | 71 | `CRawImageFileData::GetBackModel` requests this tag; native model-string code returns `Hasselblad X2D II 100C` for back 71 / sensor 22 |
| Filter, tag `0x16` | 6 | `CRawImageFileData::SetIrType` establishes this tag's filter-field association |

With sensor 22, filter 6, the third `GetCPID` argument set to zero, and the queried application boolean `ClosedLoop` set to false, the original `CRawColorParams::GetCPID` returns **`0x0616`**. The original `CXMLLut::GetFileName` returns **`bohnjuhtuvuvtxyydb56.dat`** for that ID.

The selection function also contains an alternate configuration branch. Supplying true for the boolean produces `0x010616`. The audit records the configuration query and both results. This is a controlled environment fixture; the setting of an actual running Android app was not observed. The RAW metadata, native selector and filename map have been verified individually, rather than by executing the entire app's RAW import sequence.

The filename function constructs 26 explicit profile-ID entries. Every entry was captured from native execution and then checked by calling the original selector with that ID. Some entries share an asset; for example, `0x0615` and `0x0616` both select this same file. A shared asset does not establish that the complete rendering configurations are identical.

## Asset decoding

The `CXMLLut(uColorProfile, int)` constructor calls the filename selector and then `HBCryptoNameSpace::decrypt`. Its success path creates a memory stream, obtains a key coder, and invokes the profile object's decode method. Resolving the constructor's vtable through ELF relocations identifies that method as `CXMLLut::DecodeFrom`.

The asset wrapper has a 16-byte initial chaining block followed by encoded blocks and checked padding. The original block routine uses tables embedded in the library. The independent decoder reads those tables from the private input at runtime; no tables or key material are embedded in the published audit.

Validation compares the independent decoder against the original ARM64 block routine and its original mixing helper on **136 blocks**: 32 seeded synthetic blocks and four ciphertext blocks from each of the 26 assets. All 136 blocks match exactly. Inputs remain unchanged, output guards pass, and unexpected execution or instruction-budget exhaustion fails the audit.

All 26 complete assets pass padding checks and parse as XML property lists. Their numeric arrays contain finite values. These checks establish usable decoded structures; padding and XML validity are not cryptographic authentication of the assets. The receipt records ciphertext/decoded hashes and structural summaries, without exporting decoded calibration.

## Selected profile and native loading

The selected profile declares version `3.0`. It contains five nine-element matrix arrays (`mf`, `mfd`, `mt`, `mlt`, `mh`) and the following chroma tables:

| Illuminant family | Standard table | Reproduction table |
| --- | --- | --- |
| Flash | `LUTTableFlashStd` | `LUTTableFlashRepro` |
| Tungsten | `LUTTableTSStd` | `LUTTableTSRepro` |
| High temperature | `LUTTableHTStd` | `LUTTableHTRepro` |

Each table has **18,690 doubles**, corresponding to **105 × 89 grid points with two chroma components**. The profile also supplies reference-temperature fields and neutral vectors. The exact use of every matrix and interpolation branch remains a separate tracing task.

To verify loading, the harness executes the original `CXMLLut::DecodeFrom` and `InitializeLUTs` functions with the selected profile's actual values. Python parses the XML and provides a key-value getter facade; allocation and basic memory operations are also provided by the harness. Native code performs the numeric conversion, table allocation/layout and copying. The fixture starts with a zeroed object and supplies the complete selected profile; the original Android XML parser and full profile constructor are not executed in this replay.

The native loader applies **`stored_value × 0.5 + 1`** to all five matrices and the two neutral vectors it reads. All **51 reconstructed scalar values** match the independent calculation exactly. The six table buffers match their decoded source arrays across **112,140 doubles**. This distinction matters: successful file decryption alone does not yield ready-to-use matrix values.

The loader reads the high-temperature matrix and high-temperature tables. In this replay it reads neutral vectors `vf` and `vt`; it does not request the profile's `vh` array. No conclusion about a bug or the full pipeline's use of `vh` follows from that observation.

The object and allocated buffers retain their guards. No vendor calibration values, encoded payloads, shaders, disassembly or photos are included in the repository additions. The script requires the private APK to reproduce the result.

## Reproduction

Use Python 3.12 without `-O`, because verification assertions must remain enabled:

```bash
python -m pip install -r hasselblad_native_audit/phocus_stage41w/requirements41w.txt
python hasselblad_native_audit/phocus_stage41w/inspect_phocus_profiles41w.py \
  --apk /absolute/path/to/the/supplied.apk \
  --raw /absolute/path/to/sample1.3fr /absolute/path/to/sample2.3fr \
        /absolute/path/to/sample3.3fr /absolute/path/to/sample4.3fr \
  --receipt /absolute/path/to/STAGE41W_PHOCUS_X2DII_PROFILE_SAFE.json
```

`--raw` may be omitted to reproduce the APK-only work. Including the four original samples reproduces the metadata-to-selection evidence. The audit emits structural metadata, hashes, mapping results and verification aggregates only.

## Next implementation target

Trace and execute the conversion from this loaded `CXMLLut` into the `CColorCorrection` object used by Stage 41V's pixel routine. Resolve the colour-temperature interpolation, normal/reproduction choice, input linearization, working-space matrices, neutral/shadow thresholds, exposure handling and output gradation. Then render an existing X2D II RAW through the verified path and compare it with a controlled Phocus export.

The profile is sensor-specific. Adapting this processing to the phone still requires a justified sensor-to-working-space conversion; copying Hasselblad RAW matrices directly onto phone sensor samples would not establish colour accuracy. No production rendering code or APK build changed in this stage.
