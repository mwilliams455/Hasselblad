# Stage41U — X2D II 1.2.7.16 versus 1.3.16.2

Date: 2026-10-23. Research branch: `recovery/awb-rebuild-20261021`.
Baseline research commit: `4d3004537dbe56e3dc60e5628fcc60c9a7ba402e`.
Production main baseline: `929f523aa02ae5b224be39b9c36cce5975691a10`.

**The older 1.2.7.16 release does not provide a decryptable DSP or TEE payload using any of the six published TBIE variants in the pinned upstream tool.** Its embedded RSA public record is identical to 1.3.16.2 and verifies all nine older containers. The host firmware-loader chain is also byte-identical. This comparison narrows the search without establishing that a live camera is required.

There is no recovered AES key, DSP plaintext, secure-side loader implementation or MAIN pixel equation. No production renderer or APK changed.

## Provenance and input validation

The older CIM was downloaded successfully from the [official Hasselblad CDN](https://cdn.hasselblad.com/firmware/X2D_II_100C_Firmware/1.2.7.16/X2DII_100C_v1_2_7_16.cim). Its SHA256 matches the independently recorded value in the DevKit's [verification document at commit d82dc3b](https://github.com/derrickyau9/Hasselblad-X-System-QEMU-DevKit/blob/d82dc3b0faa6456c260378df6352a07f929caed2/docs/VERIFICATION.md). This is a two-release comparison; it does not claim either release is currently the newest.

| Input | 1.2.7.16 | 1.3.16.2 |
| --- | --- | --- |
| CIM bytes | 363402240 | 364814336 |
| CIM SHA256 | `68aa9bce63c303a7d13ca4c14aae76be935925d596094bdcb92549cff42e1bc1` | `9789d6a9843d388034bc12341ad9a97585c25cb98cf11a0da8b768399b4842f6` |
| Decrypted OTA ZIP SHA256 | `fdc6660f001c52c057f05840d7b6d7685ac4ebe631289e36c77089cb2ac41646` | `7ccd5df4dab8d098d9895973fb62bcedcaa379f75fb044408a8263ce2d1f9a57` |

The existing private CIM reader and full-OTA extractor were reused, with the older version, input hash and destination changed. The reader SHA256 is `55aab1a37c60f12455dbdc37dcbd8a5290fc044c97955d3bc370102e5f9a6a48`; the older extraction wrapper SHA256 is `2728047b59396bb047f63dd8b29c12266b82a5aaac3f2c9b4b8fefc941146bfa`. No firmware executable or update script was run. ZIP reads check member CRCs; Brotli completion, transfer ranges, expansion limits and the extracted system version were checked.

The comparison audit rehashes both CIM files, OTA ZIPs and reconstructed filesystem images against pinned values. It independently reads all 20 selected filesystem components from those images with ExtFS and compares them to the extracted files. It also rehashes every regular file recorded in each extraction manifest. The manifests contain 1,610 common regular-file paths: 1,336 identical and 274 different, with three older-only and seven newer-only paths. These counts describe the recorded regular files, not symlinks or device nodes.

## What changed and what stayed identical

| Component | Observed relationship | Consequence |
| --- | --- | --- |
| Embedded RSA public record | All 780 bytes identical | One public key verifies both releases |
| `ss_dsp_manager`, `libfw_util.so`, `libfw_util_ca.so`, `libteec.so` | Whole files identical | Stage41S host-side TEE loader analysis applies to these files in both releases |
| `ask_dsp.img` and both `.ta` containers | Headers and ciphertext identical; signatures differ | These are different signature byte strings over the same header and encrypted payload; they offer no new ciphertext for decryption research |
| `ss_dsp0.fw`, `ss_dsp1.fw`, `ss_dsp2.fw` | Ciphertext and wrapped-key fields differ; chunk descriptors and plaintext-checksum fields match | Repackaging of unchanged plaintext is possible, but not proven |
| `tos.img` and bootloader container | Ciphertext, wrapped-key fields and plaintext-checksum fields differ; chunk descriptors match | Distinct encrypted variants are available, but neither is decoded |
| Board-information container | Ciphertext and wrapped-key field differ; layout and plaintext-checksum field match | Plaintext equivalence remains unproven |
| `eagle_dsp.ko`, `ask_dsp_driver.ko` | Only `.modinfo`, `.note.gnu.build-id` and `.strtab` differ | Executable sections and other sections are identical; this is not evidence of a new loader algorithm |
| `libdcam_pp.so`, `libdcam_pp_base.so`, `libduml_hal_cam.so`, two examined PP plugin libraries | Whole files identical | These files do not supply an alternative older implementation |
| `librcam.so`, `libduml_hal.so`, `vcam_driver.ko` | Executable sections differ | Available for a later function-level comparison; raw section differences do not identify a colour-algorithm change |
| Boot-area prefix tail, partition table and widened 16-bit tail | Identical | The unclassified tail's instruction set and function remain unknown |

Nine of the 14 examined host ELF files are byte-identical. The two DSP kernel modules have identical executable sections despite differing whole-file hashes. The remaining three host files have executable-section differences; relocation or build-layout changes must be distinguished from semantic changes before drawing conclusions.

For the three SS DSP files, changed header bytes are confined to the wrapped-key field, date, encrypted checksum and payload digest. The signatures also change. Equal chunk sizes, load addresses and a 32-bit additive plaintext checksum are insufficient to establish byte-identical plaintext. Conversely, different ciphertext does not demonstrate changed DSP pixel processing.

The older boot area is 557,056 bytes, SHA256 `38fbb2a3d95329e2ab7cffdcfb3cfd77cf4f5d35c0d1ea72893ecb9cc8f93d25`. All regions outside the two encrypted IMaH containers are identical to the newer boot area. The shared widened 16-bit tail has SHA256 `89e1375b0fdcbee03721d126aa26bc86693a97c7f3940a99da3bba19780e1919`; sameness is not identification as DDR, DSP or ISP code.

## Cryptographic checks

All nine containers in each release pass RSA-PSS/SHA256/MGF1-SHA256/salt32 verification in both PyCryptodome and cryptography/OpenSSL, using the shared embedded public record. Ciphertext SHA256 and encrypted checksums also pass. Each of the 18 containers has independent one-bit header, signature and payload rejection checks. Trust remains limited to the same-package public key; there is no independent manufacturer trust anchor or live-device fuse comparison.

The older nine containers were each tested with all six published TBIE variants from unmodified `dji_imah_fwsig.py` at commit `195692263c2684cf1ddc4995f2736be6c0fb135e`:

- `TBIE-2021-08`, `TBIE-2021-06`, `TBIE-2020-04`
- `TBIE-2020-02`, `TBIE-2019-11`, `TBIE-2018-07`

**All 54 strict runs pass signature verification and stop at the decrypted-chunks checksum failure.** `force_continue` is false throughout. A separate cryptography/OpenSSL decoder agrees byte-for-byte with every attempted upstream chunk, and its plaintext checksum also fails in all 54 cases. The matching public record is supplied only to the tool's in-memory registry; its source is unchanged. Temporary attempted plaintext and generated key/INI files are deleted after each trial. No failed output is accepted as code.

A synthetic signed-and-encrypted positive fixture extracts exactly; wrong-key and corrupted-ciphertext controls are rejected. These controls establish that the tested path can accept known valid input. They do not establish compatibility of the published key/derivation choices with Hasselblad's encrypted payloads.

## What this resolves and what comes next

The signature mismatch is resolved for both releases, and 1.2.7.16 supplies no successful public-TBIE decryption route. The same-package public RSA key cannot decrypt AES payloads. This result does not distinguish a different wrapping key from an unsupported derivation scheme, and does not prove that hardware access is mandatory.

Further release searches should first compare the actual loader, trusted-application payload and container format, rather than treating a different whole-file hash as new processing code. The three unchanged encrypted components demonstrate why that distinction matters. A useful independent route remains identifying the boot-area tail against adequately sourced architecture evidence. A function-level comparison of the changed `vcam_driver.ko` and `librcam.so` can also narrow visible host-side changes, but cannot by itself reveal the encrypted DSP or fixed-function MAIN arithmetic.

## Reproduction

The audit expects privately obtained CIM files and full OTA extractions containing `ota.zip`, `system.img`, `vendor.img`, extracted regular files and the corresponding extraction manifests. It publishes no firmware or key bytes.

```bash
python hasselblad_native_audit/isp_dsp_stage41u/compare_firmware41u.py \
  --older-root /private/1.2.7.16/extracted \
  --newer-root /private/1.3.16.2/extracted \
  --older-cim /private/X2DII_100C_v1_2_7_16.cim \
  --newer-cim /private/X2DII_100C_v1_3_16_2.cim \
  --upstream-tool /private/tools/dji_imah_fwsig.py \
  --receipt /private/STAGE41U_FIRMWARE_COMPARISON_SAFE.json
```

Dependencies are pinned in adjacent `requirements41u.txt`. Stage41R and Stage41T audit helpers must remain in their sibling repository directories. The receipt contains hashes, structure, equality results and aggregate checks. It excludes firmware bytes, wrapped-key bytes, derived keys, attempted plaintext, private disassembly, photos and calibration tables.
