# Stage41T — embedded X2D II public key resolves signature verification

Date: 2026-10-23. Firmware: X2D II 1.3.16.2.
Research branch: `recovery/awb-rebuild-20261021`.
Baseline research commit: `59ec08e2b080953cbd9f94bc8ebe25fb45d01de1`.
Production main baseline: `929f523aa02ae5b224be39b9c36cce5975691a10`.

The first 780 bytes of `bootarea.img` contain a complete RSA-3072 public-key record. This key verifies all nine previously examined DSP, trusted-application, TOS and boot-area container signatures. The earlier failures with the upstream tool's bundled PRAK keys were a key-selection mismatch for these signatures, not a failure of its RSA-PSS verification scheme on these images.

**Authentication-key identification is resolved for this firmware package. Payload decryption remains unresolved.** This is a public verification key, not the TBIE encryption key or a private signing key. No MAIN pixel-processing code, DSP plaintext, secure-side implementation or photographic rendering change was recovered.

## What was found and checked

The record matches the separately obtained upstream tool's `ImgRSAPublicKey96` layout: a 96-word modulus, Montgomery helpers, and exponent 65537. Both mathematical helper checks pass: the stored inverse satisfies the required modulo-2^32 identity, and the stored Montgomery square agrees with the modulus. The modulus has 3072 bits.

Fingerprints, without publishing key bytes:

- 780-byte record SHA256: `8335ac87baa1465a4d04805ce660f801d9eadaaf46f933f75f6f8e7ebfcfa080`
- DER SubjectPublicKeyInfo SHA256: `99057b679a5e2a2f85fc7994f759e01e7a045501d7d019c1377e33720cce746e`
- Source `bootarea.img` SHA256: `0fb41e070f52cf6e0e6f36f6cce1b5d20bb8c2512afb73dcdcf7f38ce6d8d9e5`

No bundled PRAK variant has the same public modulus and exponent. The upstream record layout and verification scheme were checked in [`dji_imah_fwsig.py` at the pinned commit](https://github.com/o-gs/dji-firmware-tools/blob/195692263c2684cf1ddc4995f2736be6c0fb135e/dji_imah_fwsig.py). The project's [firsthand m0801 research notes](https://github.com/o-gs/dji-firmware-tools/wiki/Firmware-m0801/02642660c8e6139e118bf3e490a4bf61eb5cdeee) identify a public RSA prefix as a possibility in earlier DJI boot areas; the X2D II result here is established by the actual record mathematics and successful signatures, not assumed from that other platform.

## Validation results

| Containers | Count | Signature result | Strict extractor result |
| --- | ---: | --- | --- |
| `ask_dsp.img`, `ss_dsp0.fw`, `ss_dsp1.fw`, `ss_dsp2.fw` | 4 | All pass | All reach plaintext-checksum failure |
| Both packaged `.ta` files | 2 | Both pass | Both reach plaintext-checksum failure |
| `tos.img` | 1 | Pass | Reaches plaintext-checksum failure |
| Two IMaH containers within `bootarea.img` | 2 | Both pass | Both reach plaintext-checksum failure |

Each signature is independently verified by PyCryptodome and cryptography/OpenSSL using RSA-PSS, SHA256, MGF1-SHA256 and a 32-byte salt. All original ciphertext hashes and encrypted checksums also match. For each of the nine inputs:

- A one-bit signed-header change is rejected by both signature implementations.
- A one-bit signature change is rejected by both implementations.
- A one-bit payload-only change leaves the header signature valid, but fails both the signed payload digest comparison and encrypted checksum. This confirms why signature verification and payload-digest verification must be combined.

The unchanged upstream extractor is also called with `force_continue=False`, with the extracted public record supplied temporarily to its in-memory key registry. All nine runs explicitly report signature verification success, then reject the already-tested `TBIE-2021-08` decryption at the plaintext checksum. The original source is not edited. Temporary outputs and derived-key INI files are deleted on context cleanup. The other five TBIE variants are not redundantly rerun: their negative results and independent decoder cross-checks remain in Stages41R/S.

The nonzero reserved-field warning still appears. Its presence does not prevent valid signature verification under the pinned scheme. Its meaning and any relevance to payload derivation remain unknown.

Trust scope: this verifies consistency with a public key embedded in the same firmware package. It is not a comparison against an independently published manufacturer trust anchor or a live camera's fused key hash. No hardware authenticity claim beyond that evidence is made.

## Complete boot-area inventory

The audit accounts for every byte of the 557,056-byte image without assuming that unrecognized data is executable code.

| File interval, end exclusive | Classification |
| --- | --- |
| `0x00000–0x0030c` | Validated 780-byte RSA public record |
| `0x0030c–0x00400` | Unclassified prefix tail, including nonzero data |
| `0x00400–0x335c0` | Signed encrypted bootloader container (`BLLK`, `BLFA`) |
| `0x335c0–0x38000` | All-zero padding |
| `0x38000–0x38320` | `PL*I` partition table, declared size 800 bytes |
| `0x38320–0x39000` | All-zero padding |
| `0x39000–0x39280` | Signed encrypted board-information container (`BDIF`) |
| `0x39280–0x40000` | All-zero padding |
| `0x40000–0x88000` | 73,728 32-bit slots, every upper 16 bits zero; includes zero padding |

The partition table contains two named area descriptors (`userarea`, `bootarea`) and 16 named partition records. These include `bootloader`, `pli`, `bd_info`, `fc_fw`, `recovery`, `normal`, `system`, `vendor` and others recorded in the receipt. Numeric field units and correspondence between package-file offsets and device partition offsets are not established here.

The tail has three large occupied regions and two smaller isolated occupied pages. Its storage representation is established, but its instruction set and purpose are not. A DDR-training/microcontroller interpretation was considered during investigation; no adequate reference match was obtained, so that interpretation is not promoted to a finding. It must not be described as recovered ARM, CEVA, decryption or MAIN ISP code. Public binary-comparison retrieval was unavailable through the GitHub text fetch interface; no binary reference comparison was performed.

## Next research boundary

The matching public-key fingerprint can now be used to compare other firmware revisions, and candidate decoded payloads can be tied to the signed source containers more reliably. The encrypted DSP and TEE payloads still require compatible TBIE key/derivation support. A public RSA verification key cannot supply that AES key by itself.

The next useful routes are a provenance-controlled comparison with an available earlier firmware revision and a supported identification of the widened 16-bit boot-area regions. There is still no proof that a live X2D II is the only route. Do not repeat the old bundled PRAK trials as an unresolved signature problem, and do not mark the main colour implementation recovered because authentication now passes.

## Reproduction

Source: `hasselblad_native_audit/isp_dsp_stage41t/audit_bootarea41t.py`.
Receipt: `hasselblad_native_audit/evidence/stage41t/STAGE41T_EMBEDDED_PUBLIC_KEY_SAFE.json`.
Dependencies: adjacent `requirements41t.txt`, which includes the Stage41R dependencies. The script imports the Stage41R bounded container parser and options helper.

```bash
python hasselblad_native_audit/isp_dsp_stage41t/audit_bootarea41t.py \
  --firmware-root /private/extracted \
  --ota /private/extracted/ota.zip \
  --upstream-tool /private/tools/dji_imah_fwsig.py \
  --receipt /private/STAGE41T_EMBEDDED_PUBLIC_KEY_SAFE.json
```

Only own audit code, fingerprints, structural facts and aggregate verification results are published. Key bytes, vendor binaries, attempted plaintext, disassembly, photos and calibration data are excluded. No device access, firmware execution, signing or flashing occurs.
