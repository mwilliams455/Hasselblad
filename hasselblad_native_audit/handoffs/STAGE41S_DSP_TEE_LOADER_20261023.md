# Stage41S — X2D II DSP firmware loading reaches a named TEE service

Date: 2026-10-23. Firmware: X2D II 1.3.16.2.
Research branch: `recovery/awb-rebuild-20261021`.
Baseline research commit: `46fda21b40b0e0b52016fb0268ed2ae5f5fb5205`.
Production main baseline: `929f523aa02ae5b224be39b9c36cce5975691a10`.

The readable host loader passes DSP firmware to a specific trusted application through the TEE client API. The service UUID resolves to a file already present in the extracted firmware. That application and the secure-OS image are themselves encrypted IMaH containers. This is direct X2D II evidence of the secure-service loading boundary, rather than an inference from another DJI device.

No DSP payload, MAIN pixel equation, encryption key, or secure-side decryption implementation was recovered. No Android rendering or APK change is made.

## Confirmed loading path

| Component | Confirmed operation |
| --- | --- |
| `ss_dsp_manager` | Both `load_IMAGE_dsp_firmware` and `load_IMAGE_e2_ask_dsp_firmware` call `plt_fw_load_file`, passing the `dspimage` tag and zero scalar options. The ordinary DSP route halts the core before loading and launches it after successful loading. |
| `libfw_util.so` | `plt_fw_load_file` reads the complete file into an ION allocation, then passes its file descriptor, size, tag and options to `fw_util_load`. No container decryption occurs in this inspected function. |
| `libfw_util_ca.so` | `fw_util_load` opens a TEE session for UUID `09db16c0-873b-4fed-b87e-a5d2b86293a2`, registers the input allocation, allocates a 32-byte tag buffer, and invokes command 1. |
| `libteec.so` | The client contains `/dev/tee%zu` and `optee-tz`; its session and invoke functions issue ioctls. The observed invoke request is `0x8010a403`. |
| Matched application | `vendor/ta/09db16c0-873b-4fed-b87ea5d2b86293a2.ta`. Its compact filename omits the UUID's final separator. Its payload is an encrypted `TZTA` chunk. |

The trace verifies six direct call edges in the original ARM64 files. Function bounds come from ELF symbols and compressed `.gnu_debugdata`. PLT mappings are checked against each stub's actual GOT address, not only assumed from its position.

`libduml_hal.so` remains involved in DSP control, such as halt/launch. The actual manager loading call traced here goes through `libfw_util.so`; a similarly named HAL firmware-loading function is not substituted for that observed route.

## Exact client request, with a bounded emulation check

The operation parameter-type word is `0x11dd`. The [OP-TEE client API header](https://github.com/OP-TEE/optee_client/blob/master/libteec/include/tee_client_api.h) defines type `0xD` as a partial registered input memory reference and `0x1` as an input value. Applied to the observed request:

| Parameter | Direction | Content |
| --- | --- | --- |
| 0 | Input memory | Complete firmware allocation, offset zero, file length |
| 1 | Input memory | 32-byte buffer containing the `dspimage` tag |
| 2 | Input value | First scalar option; zero in the inspected DSP callers |
| 3 | Input value | Second scalar option; zero in the inspected DSP callers |

**Command 1 has no output memory reference for returning decoded firmware to Android.** This does not prove that secure-side code cannot write destination memory or that other commands cannot return data. It describes this request only. The secure-side parser, cryptography, destination handling, key derivation and key storage remain unseen.

The original `fw_util_load` client function was executed in ARM64 Unicorn emulation with synthetic descriptor/size/scalar inputs and intercepted TEE/libc calls. Both a simulated success and a simulated `0xffff0000` error verify:

- The UUID, command ID, tag, parameter types, offsets, lengths and scalar mapping.
- Exactly one command invocation and two shared-memory releases on each tested path.
- Propagation of the simulated TEE result to the caller.

These checks validate the client-side interpretation. The TEE is a stub: no trusted application, DSP program, hardware access, real decryption service or camera is exercised by this emulation. Nonzero synthetic scalar inputs are test markers, not inferred valid camera options. Session-open and allocation failures are not emulated.

## Newly located encrypted components

| Component | Bytes | Chunks | Published TBIE trials |
| --- | ---: | --- | ---: |
| Matched firmware-loader TA `09db16c0…ta` | 207,360 | `TZTA` | 6, none validate |
| Other packaged TA `e91c9402…ta` | 272,128 | `TZTA` | 6, none validate |
| OTA member `tos.img` | 462,272 | `LATF`, `TZOS` | 6, none validate |
| `bootarea.img` container at offset 1,024 | 209,344 | `BLLK`, `BLFA` | 6, none validate |
| `bootarea.img` container at offset 233,472 | 640 | `BDIF` | 6, none validate |

All five containers have IMaH v2 headers, PRAK authentication, TBIE encryption, 384-byte signatures, no declared compression, and nonzero first reserved fields. Their encrypted-payload hashes and checksums agree with their headers. None verifies with the bundled PRAK variants under the upstream signature scheme.

For all 30 new image/key combinations, the unchanged upstream extractor's chunks match the independent cryptography/OpenSSL decoder byte for byte. All decrypted-payload checksums fail. Forced extraction again returns status zero despite failed validation. Temporary candidate plaintext and derived-key files are removed; only aggregate results are exported.

The separately obtained upstream tool remains pinned to commit `195692263c2684cf1ddc4995f2736be6c0fb135e` and SHA256 `955c6798f3e42b07799358208b390e9c5f167479f3a6b81e06f482d200146b9d`. Stage41R already supplies its synthetic positive/negative controls; this stage extends the tested inputs. These results do not uniquely distinguish an unavailable key from an unsupported derivation or format variant.

The `bootarea.img` member totals 557,056 bytes. Only the two identified IMaH containers are classified and tested here. Regions outside them contain non-padding data and remain unclassified; this stage does not declare the entire boot area encrypted or exhausted.

## What this changes

The previous claim that there was no X2D II evidence of TEE involvement is now superseded: the host loading path directly invokes a named TEE service. Claims about a hardware-bound root key, RPMB key storage, or a requirement to acquire a live X2D II remain unsupported.

The concrete research targets are now the decoded firmware-loader TA, the secure-side loader in `tos.img`, compatible TBIE derivation/key support, or a validated decoded DSP image. A readable `libfw_util_ca.so` is already available; it is client glue and does not expose the secure implementation in the inspected path.

Useful camera-free follow-up is to classify the remaining boot-area regions and compare matching loader/TA/TOS components from independently available firmware revisions or source trees. Any candidate needs provenance and validation. Repeating the same six keys against the same five containers adds no evidence. Obtaining the secure loader could explain decryption without yet recovering the photographic MAIN equations; those are separate milestones.

## Reproduction and evidence

Repository files:

- `hasselblad_native_audit/isp_dsp_stage41s/audit_loader41s.py`
- `hasselblad_native_audit/isp_dsp_stage41s/requirements41s.txt`
- `hasselblad_native_audit/evidence/stage41s/STAGE41S_TEE_LOADER_SAFE.json`

The script imports the adjacent Stage41R parser and independent decoder. With dependencies installed and the separately obtained, hash-pinned upstream tool:

```bash
python hasselblad_native_audit/isp_dsp_stage41s/audit_loader41s.py \
  --firmware-root /private/extracted \
  --ota /private/extracted/ota.zip \
  --upstream-tool /private/tools/dji_imah_fwsig.py \
  --receipt /private/STAGE41S_TEE_LOADER_SAFE.json
```

Public evidence contains own audit code, structural facts, source hashes, call relationships and aggregate outcomes. Vendor binaries, disassembly, keys, attempted plaintext, photos and calibration data are excluded. Original inspected host files, packaged TA files and the upstream tool remain unchanged.
