# Saved-still dispatch and the packaged DSP boundary

Audit date: 2026-10-19. Target: **Hasselblad X2D II 1.3.16.2**.

## Result

The inspected `raw2rgb_proc` and HBL calibration paths are ARM-side request
builders. For the DSP framework context inspected here, their indirect process
callback resolves to `_pp_dsp_frwk_sl_process`, which creates and calls a DSP
function client. Its normal remote entry is named **`cam_libpp_function_entry`**.
The transport reaches the ICC HAL and a Linux `ioctl` request, rather than a
recovered CPU loop that transforms photographic pixels.

The matching DSP firmware family is present in the update: `ss_dsp0.fw`,
`ss_dsp1.fw`, and `ss_dsp2.fw`. They are encrypted IMaH v2 containers. All three,
and the separate `ask_dsp.img`, pass their encrypted-payload SHA-256 checks. All
six TBIE variants in the precisely pinned public `dji_imah_fwsig.py` source fail
the stored plaintext checksums for all four images. No DSP implementation of
the remote entry or its operation dispatch table was recovered.

This establishes a concrete implementation boundary for this branch. It does
**not** establish that the whole firmware is inaccessible, that all colour work
runs on a DSP, or that this RPC necessarily applies `MAIN_3DLUT` or `MAIN_HNCS`.
The ARM coefficient and table-generation work in the neighbouring audits is a
separate, executable source of useful results.

## Evidence and reproduction

`inspect_dispatch.py` independently checks the supplied firmware against 13
whole-file SHA-256 pins, records hashes for 26 bounded host functions, and verifies
32 direct calls. It also checks selected indirect callback slots, reconstructs
the DSP callback installation from the constructor's address calculations,
verifies selected strings and channel configuration, and parses the DSP image
headers. It never executes vendor code or starts a device service.

The recorded run is `dispatch_evidence.json`. It includes the file hashes,
function addresses and hashes, call sites, callback targets, container metadata,
encrypted payload hashes, and each published-variant checksum result. It contains
no original firmware bytes, decrypted bytes, cryptographic keys, photographic
pixels, calibration arrays or full disassembly. The script and report are
research artifacts; they do not modify the Photon application.

From this directory, with dependencies installed and firmware supplied separately:

```bash
python3 inspect_dispatch.py \
  --firmware-root /absolute/path/to/firmware/extracted \
  --public-imah-source /absolute/path/to/exact/dji_imah_fwsig.py \
  --out /tmp/dispatch_evidence.json
```

Dependencies are `pyelftools`, `capstone`, and, for the optional public-variant
check, `cryptography`. Their versions are recorded in the JSON. Omitting
`--public-imah-source` performs the ELF and container checks and explicitly marks
the published-variant check as not performed. No downloads are performed by the
script. Exact upstream file bytes are required; an extra trailing newline will
fail its source identity check.

The underlying analysis additionally inspected instructions and callers in
temporary files outside this repository. The compact script verifies selected
relationships from that analysis; it is not a general control-flow decompiler or
a proof of every possible path through the firmware.

## 1. The raw2rgb and calibration commands

All virtual addresses below refer to the exact ELFs pinned in the JSON.

| Location | Observed role |
| --- | --- |
| `libdcam_pp.so:raw2rgb_proc`, `0x1d15a8`, 1,160 bytes | Builds a 192-byte transfer descriptor, with parameter size/value `0x24c0`, then calls `message_trans_arm_proc_pull` at `0x1d16b4` or `0x1d19d8`. |
| Raw2rgb command construction, `0x1d15f0`/`0x1d15f4` | Constructs **`0x00110009`**, passed as argument 5, `w4`. This is a libpp operation selector, **not the resolved RPC transport function ID**. |
| Raw2rgb call setup | Supplies transfer selector/value `0xbfc`, timeout parameter `0xfa0` (4,000), the caller's flag, a null optional host callback, and `_raw2rgb_pull_buf_cb` as the output callback. The unit of the transfer value is not independently established here. |
| `proc_hbl_calib`, `0xd4ed8` | Calls `hbl_calib_build` with **`0x002e0001`** for mode 1 and **`0x002e0002`** for mode 2, at `0xd529c` and `0xd5160` respectively. |
| `hbl_calib_build`, `0xd55a0`, 1,700 bytes | Transfers a 256-byte parameter record through the device buffer callback, then calls `message_trans_arm_proc_pull` at `0xd5974`, carrying the caller's operation selector and the same 4,000 timeout parameter. |

Known raw2rgb callers include `min_ev_raw2rgb` (`0x1d9700`),
`med_ev_raw2rgb` (`0x1db030`), `raw2rgb_hlrec_drc` (`0x1b6f18`), and `raw2rgb`
(`0x1df040`). These calls go through the ELF's `raw2rgb_proc` PLT entry. The
surrounding saved-image/fusion context makes this more relevant than display
colour correction, but function names alone do not prove which final colour
stages the remote operation performs.

`_raw2rgb_pull_buf_cb`, at `0x1d1a30`, is a 116-byte copy callback. It reads the
per-core destination pointer using descriptor fields `+0x10` and `+0xb8`, then
performs exactly three `memcpy` calls:

| Source offset | Destination offset | Bytes |
| ---: | ---: | ---: |
| `0xc8` | `0x199c` | 400 |
| `0x258` | `0x1b2c` | 400 |
| `0x3e8` | `0x1cbc` | 2,052 |

It returns zero and contains no colour sampling computation. These offsets are
internal parameter/buffer offsets, not an established phone RAW or RGB ABI.

## 2. Resolving the indirect callbacks

`message_trans_arm_proc_pull` in `libdcam_pp_base.so` is at `0x3a220`, size
1,380. It validates the context, adapts inputs, and calls
`sl_message_trans_arm_proc_pull` at `0x3a354`. The latter is at `0x38998`, size
6,280, and dispatches through device callbacks:

| Device slot | Call site(s) | DSP framework target |
| ---: | --- | --- |
| `+0x08` | `0x38a4c` | `_pp_dsp_frwk_sl_buf_trans` |
| `+0x18` | `0x38aa8`, `0x38bfc` | **`_pp_dsp_frwk_sl_process`** |
| `+0x30` | `0x38f9c` | `_pp_dsp_frwk_wait` |
| `+0x38` | `0x39274` | `_pp_dsp_frwk_sl_pull_buf` |

The target resolution is grounded in `pp_create_dsp_frwk_dev_ctx` at `0x57ce8`,
size 1,796. It allocates a `0x680`-byte device context and installs the actual
callback addresses. In particular, its store at `0x57d80` places
`_pp_dsp_frwk_sl_process` (`0x5b598`) in slot `+0x18`; its store at `0x57db8`
places the wait and pull callbacks in `+0x30` and `+0x38`. The reproduction
script evaluates this bounded address-construction sequence and checks the
result against symbols recovered from `.gnu_debugdata`.

This proves the targets for a context made by this DSP constructor. The generic
dispatch API may accept other context implementations; this audit does not claim
to have excluded all such alternatives.

The further host path is:

| Host location | Next operation |
| --- | --- |
| `_pp_dsp_frwk_sl_process`, `0x5b598` | Calls `pp_new_ss_function_client` at `0x5b98c`, and `pp_call_ss_function_client` at `0x5b9a4`. |
| `pp_new_ss_function_client`, `0x6e350` | Selects **`cam_libpp_function_entry`** for its normal flag value, then calls `ss_dsp_function_client_new` at `0x6e4a0`. An alternate flag selects `framework_sdk_e2_proxy_demo_op`. |
| `ss_dsp_function_client_new`, `libdsp_frwk.so:0xa6bc` | Uses `ss_icc_find_dsp_function_id_hash` to resolve the requested function name for the DSP cores. The numeric remote function ID is supplied by the runtime DSP map. |
| `pp_call_ss_function_client`, `0x6ee60` | Calls `ss_dsp_function_client_call` at `0x6eec0`. |
| `ss_dsp_function_client_call`, `libdsp_frwk.so:0xaa18` | Selects an eligible DSP, handles shared-memory address translation, then calls synchronous or asynchronous DSP RPC. |
| `ss_icc_dsp_function_rpc`, `0xff10` | Calls `ss_icc_send_sync` at `0xfff4`; the asynchronous path reaches `ss_icc_send_sync_nowait` at `0x10200`. |
| `ss_icc_send_sync_nowait`, `0xcbc0` | Calls `duss_hal_icc_send` at `0xcf4c`. |

The pp_base source-path string identifies the original host implementation as
`hardware/dji/common/camera/libpp_proxy/pp_proxy/platform/dspf10/pp_dspf_api.c`.
That string is supporting context; the call and callback relationships provide
the stronger evidence.

## 3. The device transport boundary

`duss_hal_icc_send`, `libduml_hal.so:0x21fa8`, dispatches through the device's
ICC operations table. `duss_hal_attach_linux_icc` installs the table at `0xfd738`.
Its send slot `+0x20` points to `0x36020`, an unnamed local callback in the
available symbol tables. This report calls it the **Linux ICC send callback**;
that is an analyst-assigned name.

The callback constructs a 24-byte request and calls `ioctl` at `0x3605c`, with
request number **`0x40184905`** and a file descriptor from device-private state.
This was inspected statically; no ioctl was issued by this audit.

`system/etc/dspf/json/dspf_icc_chnl_cfg.json` enables its JSON configuration and
defines DSP endpoints 0, 1, and 2, with Linux endpoint 4. It supplies channels
such as `/dev/icc_dev:ap0-dsp0-0.0` and the corresponding receive channel. The
device configuration in `system/etc/dji.json` references the Linux ICC HAL
attachment. These are camera-platform resources, not Android APIs that can be
assumed available in a normal phone application.

## 4. The packaged DSP images

`ss_dsp_manager:ss_load_dsp_firmware`, at `0x6f00`, selects firmware filenames
and calls `load_IMAGE_dsp_firmware` (`0x5958`). That function halts the DSP,
loads the `dspimage` through `plt_fw_load_file` at `0x59f0`, then calls
`duss_hal_dsp_launch` at `0x5a64`. `plt_fw_load_file` in `libfw_util.so` reads
the image into ION memory and calls `fw_util_load`. The later authentication or
decryption implementation is not established by this trace; no claim of a
specific TEE or hardware key store is made here.

The three SS filenames are present in this loader and in the extracted update:

| Image under `vendor/firmware/dspf/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `ss_dsp0.fw` | 6,100,480 | `5dd6da299227bca0d4bf3c1e92482ebcebf709216fc1e1e9efde8bd2cfab5344` |
| `ss_dsp1.fw` | 5,838,336 | `03f08813e18b577219986495c653b8ad1b58ed9edaad10ffb86cab4c29890572` |
| `ss_dsp2.fw` | 5,838,336 | `037fdd1476fcb0d738b1ce0f5933d8ddd64ce0a87862e0209dda394e5c6d8b5f` |
| `ask_dsp.img` | 140,928 | `bc64b8862f5e0eb2026eb90e20c6efb3e6d31ee2934bd20d93656747fde40128` |

Each has IMaH version 2, a 320-byte header containing four chunk descriptors, a
384-byte signature area, authentication identifier `PRAK`, and encryption
identifier `TBIE`. All chunk attribute values are zero, marking them encrypted
under the referenced public format. Each SS image has `CODI`, `DATI`, `CODE`,
and `DATE` chunks; its large `CODE` chunk is 4,599,392 bytes. Their external code
load addresses are `0x20200000`, `0x21200000`, and `0x22200000` respectively.
The complete chunk sizes and addresses are in the JSON.

All encrypted-payload hashes match their headers. This is a content-integrity
check, **not RSA signature verification**. The outer update's previously
recorded identity provides the firmware provenance; this audit does not repeat
the original download.

The manager contains the strings `ceva version` and `SS_CEVA_DMA`, and the DSP
framework also refers to `SS_CEVA_DMA`. These support a **CEVA family** attribution
in the host software. The exact DSP instruction set, model, and code ABI remain
unestablished. The containers' architecture bytes are zero, and the host ELFs
being AArch64 does not make the encrypted DSP code AArch64.

The filenames and loader establish the packaged target image family. Because
the server payloads remain encrypted, this audit has not independently located
`cam_libpp_function_entry` inside one particular DSP image, recovered its
per-operation handler table, or proven which core handles operation `0x00110009`
in a live capture.

## 5. Scope of the public decryption check

The format reference and candidate set come from the primary public project
[o-gs/dji-firmware-tools, `dji_imah_fwsig.py`](https://github.com/o-gs/dji-firmware-tools/blob/master/dji_imah_fwsig.py).
The exact source is pinned by
[Git blob `aa8d75548db2958685cfb643f2ab0bc9c8b8b823`](https://api.github.com/repos/o-gs/dji-firmware-tools/git/blobs/aa8d75548db2958685cfb643f2ab0bc9c8b8b823),
74,094 bytes, SHA-256
`534680d1fb0ced5f6425b276fcd421456a45a513cf625d73566b2150c2ed6760`.
The moving `master` link is for reading; the blob and SHA-256 are the
reproduction identities.

The six variants tested were `TBIE-2021-08`, `TBIE-2021-06`, `TBIE-2020-04`,
`TBIE-2020-02`, `TBIE-2019-11`, and `TBIE-2018-07`. The optional check parses only
their literal values from the pinned source. It does not execute that downloaded
program, print keys, write decrypted chunks, or attempt further candidate keys.

The check follows that source's IMaH v2 construction: AES-ECB unwraps the image's
scramble key, AES-CTR uses a zero initial counter continuously across the
encrypted chunks, encrypted chunk sizes are padded to 32 bytes, and the
plaintext checksum sums little-endian 32-bit words including padding modulo
2^32. The counter cannot approach overflow for these small images.

**All 24 image/variant combinations fail the expected plaintext checksum.** The
JSON records the computed and expected values, allowing an independent review.
This rules out those six variants under the pinned format interpretation. It
does not prove that no other published, vendor-specific or legitimately
obtainable decryption route exists. No brute force or key search was performed.

## Implication for the Photon work

Calling `raw2rgb_proc` or `hbl_calib_build` in an Android native library would
still require the correct platform context, shared buffers, ICC driver and DSP
server. Successfully loading the host library is therefore not equivalent to
having a portable photographic renderer. No guessed casts or fabricated
camera-state structures were used to invoke these wrappers.

The practical work supported by current evidence remains recovery and
verification of bounded ARM arithmetic, followed by a correctly specified
phone-to-target pixel contract. The separate MAIN CCM, gamma and LUT-format
audits address those pieces. A full saved-image DSP implementation would require
readable server code and its proven architecture, or an independently verified
replacement for the relevant pixel operations. This report supplies a precise
boundary and identifies the packaged target; it does not add HNCS processing to
the application.
