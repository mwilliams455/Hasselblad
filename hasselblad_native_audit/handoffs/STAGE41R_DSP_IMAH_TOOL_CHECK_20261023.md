# Stage41R — test the supplied DJI IMaH decryptor on X2D II DSP images

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Baseline research commit: `8190969f37bc5e91cc9668eba68ab5670944f51a` (Stage41Q).
Production `main` remains `929f523aa02ae5b224be39b9c36cce5975691a10`.

The user supplied the appropriate container-family tool: [o-gs/dji-firmware-tools, dji_imah_fwsig.py](https://github.com/o-gs/dji-firmware-tools/blob/195692263c2684cf1ddc4995f2736be6c0fb135e/dji_imah_fwsig.py). It parses the X2D II DSP containers, but none of its six bundled TBIE encryption-key variants yields a matching plaintext checksum for any of the four images. No decoded DSP program or MAIN pixel implementation was recovered.

This is a tested incompatibility with the pinned tool/key set, not evidence that decryption is impossible. It also does not uniquely distinguish an unavailable key variant from a derivation/algorithm difference unsupported by that tool.

## Exact source and inputs

Upstream commit: `195692263c2684cf1ddc4995f2736be6c0fb135e`.
Tool version: `0.3.2`; source SHA256: `955c6798f3e42b07799358208b390e9c5f167479f3a6b81e06f482d200146b9d`.
The source read through GitHub at `master` matches the pinned commit's source, and the local source remains unmodified. The upstream script is GPL-3.0-or-later and is obtained separately; neither it nor its key arrays are copied into this repository.

The inputs are the already-extracted original 1.3.16.2 files under `vendor/firmware/dspf/`:

| Image | Bytes | Header version | Signature bytes | Encryption ID | Chunk IDs |
| --- | ---: | ---: | ---: | --- | --- |
| `ask_dsp.img` | 140,928 | 2 | 384 | TBIE | DATE, DATE, CODI, DATI |
| `ss_dsp0.fw` | 6,100,480 | 2 | 384 | TBIE | CODI, DATI, CODE, DATE |
| `ss_dsp1.fw` | 5,838,336 | 2 | 384 | TBIE | CODI, DATI, CODE, DATE |
| `ss_dsp2.fw` | 5,838,336 | 2 | 384 | TBIE | CODI, DATI, CODE, DATE |

Every image has `IM*H` magic, a 320-byte main-plus-chunk header, authentication ID PRAK, authentication-algorithm field `0x00040003`, compression field zero, and four encrypted chunks. Each SS image declares a 4,599,392-byte CODE chunk. The receipt records per-image source hashes and structural chunk offsets/sizes/load addresses, without payload bytes or derived keys.

The upstream script also warns that the header's first reserved field is nonzero. The receipt records that condition separately; its meaning has not been established. This is another reason to describe the result as tool/key compatibility, rather than declaring that a missing AES key is the only possible cause.

The chunk labels describe the container's declared layout. They do not establish the DSP instruction set, that CODE contains the photographic MAIN equations, or that MAIN fixed-function hardware has a software implementation there.

## Integrity, authentication and decryption are separate checks

1. **Ciphertext integrity passes for all four images.** Independently calculated payload SHA256 matches the stored payload digest, and the header-plus-encrypted-payload additive checksum matches. Header lengths, contiguous 32-byte-padded chunk ranges and complete file coverage are also checked. These are consistency checks against the supplied header, not proof of cryptographic authenticity.
2. **Authentication does not pass.** All eight bundled PRAK variants were considered per image. Only length-compatible keys enter RSA-PSS/SHA256 verification using the upstream tool's scheme. No candidate verifies. An unmodified strict CLI run for each image exits with status 10 on signature verification.
3. **No tested encryption key passes.** All six bundled TBIE variants are tested independently for each image: `TBIE-2021-08`, `TBIE-2021-06`, `TBIE-2020-04`, `TBIE-2020-02`, `TBIE-2019-11`, and `TBIE-2018-07`. All 24 plaintext checksum comparisons fail.

## Original-tool cross-check and the force-option trap

For each of those 24 image/key combinations, the unmodified upstream script is also run on a temporary copy with `-u -f`, an explicit encryption-key selection and a length-compatible authentication-key selection. Its output is never accepted as verified code.

An independent decoder uses `cryptography`/OpenSSL: AES-ECB unwraps the header's per-image scramble key, followed by AES-CTR over the encrypted payload. The original tool uses PyCryptodome. Every produced chunk matches byte-for-byte between the two implementations, including the duplicate DATE naming in `ask_dsp.img`. The independent plaintext checksum result agrees with the original script's failure warning in every trial.

**All forced runs return exit status zero despite reporting a failed plaintext checksum.** File creation and a successful shell status are therefore insufficient to identify a decoded DSP image. The `-f` option suppresses the exception; it does not supply a compatible key. All unvalidated chunk files and derived-key INI files created by these trials are deleted from their private temporary directories. Only private logs and the aggregate receipt remain.

The independent whole-payload decoder is deliberately restricted to the layout observed here: v2, uncompressed, contiguous, entirely encrypted chunks padded to 32 bytes. It rejects other layouts. The payloads are small enough that the low 32-bit CTR counter cannot wrap, so the independent full-width CTR implementation yields the same stream for these images.

## Positive and negative controls

The audit first generates a small, synthetic IMaH v2 fixture with a temporary RSA-3072 signing key and synthetic AES key material, four differently sized chunks and padding. This does not modify or sign any vendor firmware.

- The original extractor verifies the synthetic signature and checksums and reproduces all four known plaintext chunks exactly.
- The independent decoder reproduces the same padded plaintext exactly.
- Changing the synthetic wrapping key makes strict upstream extraction fail specifically at the plaintext checksum.
- Corrupting ciphertext makes both independent ciphertext-integrity checks fail.

These controls rule out a blanket inability to decrypt or validate the supported v2 construction in this environment. They do not prove that the real camera uses every part of that construction identically.

All four original firmware files and the upstream tool retain their SHA256 hashes. No physical camera, hardware I/O, executable DSP emulation, firmware rewrite or Android rendering change occurs.

## What this changes for the next search

The unresolved acquisition is now more specific: compatible **TBIE key/derivation support for these X2D II images**, or a correctly decoded instance of the same DSP payload. Authentication additionally needs a compatible PRAK public key/signature scheme to verify provenance cryptographically. Another copy of the same host `.so` libraries or the same encrypted `.fw` containers does not resolve this result.

Useful candidate output names from this tool would include `ss_dsp0_CODE.bin`, `ss_dsp0_DATE.bin`, and the corresponding DSP1/DSP2 chunks. Any such find must come with enough provenance and validation to distinguish it from the invalid output that force mode can generate. Matching CODE/DATA chunk labels alone do not establish valid decryption.

A narrow upstream search found no Hasselblad issue or TBIE pull request in the returned results. [Issue 251](https://github.com/o-gs/dji-firmware-tools/issues/251) documents a historical missing-TBIE case; its later disclosed key was incorporated as TBIE-2020-02, which is already among the variants tested here. [Issue 467](https://github.com/o-gs/dji-firmware-tools/issues/467) concerns a different DJI RC2 application and also reports that all bundled TBIE keys fail. Those reports do not establish the X2D II key-storage mechanism or justify assuming that hardware access is the only remaining route.

## Reproduction

Source: `hasselblad_native_audit/isp_dsp_stage41r/audit_imah41r.py`.
Install the adjacent pinned requirements and obtain the separately pinned upstream script. Run locally with private firmware:

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python hasselblad_native_audit/isp_dsp_stage41r/audit_imah41r.py \
  --upstream-tool /private/tools/dji_imah_fwsig.py \
  --firmware-root /private/original-firmware/extracted \
  --private-dir /private/stage41r/audit \
  --receipt /private/STAGE41R_IMAH_COMPATIBILITY_SAFE.json
```

The script pins the upstream source hash, runs synthetic controls, checks the four originals, runs all 24 comparisons and rejects any attempt to record a newly successful key as the existing negative result. A positive match requires a new analysis and structural validation before it is described as usable DSP code.

Public artifacts contain independently written audit code, dependency versions, structural container facts, source hashes and aggregate outcomes only. No upstream/vendor key bytes, firmware bytes, derived scramble keys, temporary plaintext, photographs or calibration data are published.
