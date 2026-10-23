# Stage41I: real RAW pixels are accessible

Date: 2026-10-23. Research branch only. No APK or photographic renderer change.

## Correction to the recent pixel-access wording

Actual captured sensor pixels are available through saved RAW/DNG files. The Stage41G/H statements about synthetic pixels apply to those firmware exporter tests. They must not be read as saying that this project or Work Mode cannot access real camera pixels.

Stage36 already demonstrated two native diagnostic calls on the same 1,024 real samples from a phone DNG, with source binding and separate neutral inputs. That result remains valid. Stage41I verifies full saved-file access in Work Mode and does not restart white-balance or neutral-policy research.

## Work Mode verification completed

The user's already-supplied DNG and capture record were retrieved privately and inspected read-only. The complete DNG checksum and file length match its recorded capture sidecar. The record reports selected still-result/image timestamp pairing; this is application-recorded provenance, not independent hardware attestation.

| Property | Verified result |
|---|---|
| Saved RAW dimensions | 4096 × 3072 |
| Stored samples | 12,582,912 Bayer sensor samples |
| Storage | Unsigned 16-bit, uncompressed, one CFA sample per pixel |
| CFA | RGGB |
| RAW sample bytes | 25,165,824 |
| Full decoder versus independent raw-strip memory map | Every sample identical |
| Source DNG | Unmodified; hash rechecked after reading |
| Available metadata | Black/white levels, AsShotNeutral, colour/forward matrices, OpcodeList2 |
| Demosaic, GainMaps or colour transform applied in this check | No |

The supplied JPEG also decodes successfully as RGB with an ICC profile. Its dimensions are 1536 × 2048. It is not directly pixel-aligned with the RAW. This check does not independently establish that JPEG's capture identity, original-resolution provenance, or all applied processing. Do not use it as an exact RAW-to-render pixel reference without further binding, orientation, crop and resampling checks.

The source remains a **phone DNG**, not an X2D II sensor file or internal ISP tap. Individual sensor values, original image hashes, camera identifiers and calibration arrays remain private. The committed receipt contains only bounded aggregate facts and proof flags.

## What each source can establish

| Source | Useful evidence | Remaining limit |
|---|---|---|
| Existing phone DNG plus capture record | Genuine phone input, sensor layout, levels, metadata and reproducible pixel tests | Does not contain the Hasselblad processing operation |
| Phone JPEG | The phone pipeline's rendered result | Processing, scaling and provenance must be accounted for; it is not a Hasselblad reference |
| Genuine X2D II 3FR plus controlled camera/Phocus render | A possible end-to-end Hasselblad input/output reference | Includes multiple processing stages; cannot uniquely identify MAIN CCM by itself |
| Embedded RAW preview | Rendered pixels if present and decoded | Usually has additional processing/resizing; this check did not inspect an X2D II embedded preview |
| Internal stage capture or a verified original pixel routine | Can test a specific processing stage with controlled inputs/parameters | Such an isolated MAIN CCM pair/routine has not yet been obtained |

RAW sensor values are valid input. Their colour interpretation still needs the correct sensor calibration and processing domain. Directly feeding Xiaomi samples into Hasselblad sensor-specific coefficients would not establish colour fidelity.

## External reference avenues checked

On 2026-10-23, Hasselblad's official [X System sample gallery](https://www.hasselblad.com/learn/sample-images/x-system/) listed X2D II JPEG examples. The RAW links exposed on that page were for older models. No matched X2D II RAW/render pair was obtained from it in this task.

Hasselblad's current [Phocus Mobile documentation](https://www.hasselblad.com/phocus/phocus-mobile-2/) describes X2D II RAW processing, HNCS rendering and image export. A controlled render from that software could support an end-to-end comparison. It would need its software version, settings, colour space, transfer function and HDR/SDR mode recorded; it is not automatically bit-equivalent to the pinned camera firmware 1.3.16.2.

Search also surfaced a DPReview X2D II gallery advertising original RAW/JPEG files. The opened page did not expose usable download links in this environment, so no pair was downloaded or validated. Do not count it as an acquired reference.

## Direction from this checkpoint

Pixel input access is established. Reuse the existing privately bound phone RAWs for implementation tests. Keep the missing original MAIN CCM/gamma/LUT arithmetic as the firmware reconstruction blocker. A genuine X2D II RAW plus controlled render would add valuable end-to-end validation, while stage-specific proof remains a separate requirement for exact firmware claims.

The verified local command is implemented in `isp_raw_stage41i/verify_real_raw_access41i.py`. Its receipt is `evidence/stage41i/STAGE41I_REAL_RAW_ACCESS_SAFE.json`. This is a local test with private user inputs; no public CI runner was given the photographs, RAW arrays or sidecar.
