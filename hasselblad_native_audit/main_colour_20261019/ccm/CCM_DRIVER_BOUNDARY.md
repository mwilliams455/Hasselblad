# Bounded CCM driver follow-up

Target: X2D II 1.3.16.2, `system/lib/modules/vcam_driver.ko`, SHA-256
`29309a225f2dcd8327b6fdaca477425b2c21ba580daa83599c1ea8699b7e450e`.

The four requested functions expose register configuration and field widths,
but **do not establish a pixel transform or its Q
format**. No module or driver was loaded or executed.

This is an AArch64 `ET_REL` object. The addresses below are offsets in `.text`,
not loaded virtual addresses. `inspect_ccm_driver.py` records function hashes and
relocations and verifies the direct relationship between `ccm_set_fmt` and
`ccm_set_fn0_config`. The results are in `ccm_driver_evidence.json`.

| Function | `.text` offset / bytes | Result |
| --- | --- | --- |
| `ccm_set_fn0_config` | `0x30e40` / 92 | Clears enable bits, packs two caller fields into the low and high 16 bits of register `+0x10`, and sets the bit at `+0x394`. There is no enum mapping or numeric rescaling that establishes a pixel format. |
| `ccm_set_ig0_config` | `0x30e9c` / 1,280 | Masks and copies configuration fields into register locations, then enables the block. Contains bounded scalar copy loops, no calls and no matrix multiplication of image samples. |
| `ccm_set_fmt` | `0x314c8` / 80 | Gets the register base from context `+0x50`, constructs the two-field record from arguments, and calls `ccm_set_fn0_config`. The call at `0x314f0` has relocation `R_AARCH64_CALL26`; the unrelocated branch immediate must not be interpreted as a self-call. |
| `ccm_probe` | `0x31518` / 204 | Allocates the component, calls `fc_component_init` and `muse_mapping_peg_init`, and installs an internal callback through section relocations. It does not expose colour arithmetic. |

The complete array-copy extents in `ccm_set_ig0_config` are:

| Parameter fields | Transfer | Register fields |
| --- | --- | --- |
| `+0x1e .. +0x2e`, nine values read as `uint16` | Loop at `0x31068` keeps only the low byte of each value | Low 8 bits of nine 32-bit registers, `+0x34c .. +0x36c` |
| `+0x30 .. +0x40`, nine values read as `uint16` | Loop at `0x31094` preserves all 16 loaded bits | Low 16 bits of nine 32-bit registers, `+0x370 .. +0x390` |
| `+0x58 .. +0x67`, 16 bytes | Loop at `0x31168` | Low 8 bits of 16 registers, `+0x28 .. +0x64` |
| `+0x68 .. +0x86`, 16 values read as `uint16` | Loop at `0x31194` | Low 16 bits of 16 registers, `+0x18c .. +0x1c8` |
| `+0x8d .. +0xa5`, 25 bytes | Loop at `0x31238` | Low 8 bits of 25 registers, `+0xac .. +0x10c` |
| `+0xa6 .. +0xbe`, 25 bytes | Loop at `0x31260` | Low 8 bits of 25 registers, `+0x110 .. +0x170` |
| `+0xcc .. +0xd6`, six values read as `int16` | Loads at `0x31324 .. 0x31338`, then loop at `0x3133c` repeats these six values 16 times | 96 full 32-bit registers with sign extension, `+0x1cc .. +0x348` |

Unrolled array-like copies also transfer three bytes at `+0x10` to register
fields at `+0x7c`, five bytes at `+0x13` to `+0x14`, six halfwords at `+0x48` to
`+0x94`, five bytes at `+0x88` to `+0x68`, and six halfwords at `+0xc0` to
`+0x174`. Each destination register has a four-byte stride. The last group is
masked to 9 bits. The first clears a 9-bit field but copies an 8-bit input, so
its ninth bit is always cleared. The JSON records these extents separately from
the actual loops.

The nine-value groups are distinct configuration fields whose meanings remain
unidentified. This setter does not combine the fields, sign-extend them as matrix
coefficients, divide by a scale, multiply them by pixels, or establish their row
and column order. Calling the format Q8.16, or identifying one group as an
integer part and the other as a fractional part, would go beyond this evidence.

Elsewhere in the same setter, the six `int16` values at parameter offsets
`+0xcc .. +0xd6` are explicitly sign-extended to 32 bits and repeated into 16
groups of six registers at `+0x1cc .. +0x348`. This is useful evidence of signed
handling for **those separate fields**; it cannot be transferred to the two
nine-value groups without a proven structure mapping.

The separate MAIN CCM descriptor audit reports `lmtx_fw` physical addresses
`0xf322c1cc .. 0xf322c348` for 16 groups of six words. The additional bounded
component-binding check below establishes the CCM register mapping offset,
which matches the driver's 96-word region above. In
particular, descriptor parents 4125, 4128, and 4170 report first-word addresses
`0xf322c1cc`, `0xf322c1e4`, and `0xf322c334`. Those addresses establish a useful
cross-check with the neighbouring audit. The two nine-value groups are later,
**distinct** fields at `+0x34c` and `+0x370`; they must not be substituted for
the already identified 16-by-6 `lmtx_fw` region.

## Component and register binding

The 56-byte slice at `.text+0x59fbc .. +0x59ff0` within
`plat_eagle2_probe_components` was then inspected independently. The script
checks its hash, actual load/store offsets, constant construction, and the
`R_AARCH64_CALL26` relocation to `ccm_probe`. The returned component is stored at
platform context `+0x510`, receives component ID `0x4b`, and has its register
base written to component `+0x50`. That base is loaded from
`[[platform_context+0x2a0]+0x48]` and increased by **`0x2c000`**.

The separate MAIN format audit identifies the source pointer as the common
mapped YUV postprocessing base, also used by the LUT and gamma components. This
links the CCM component and its register setters to that platform block. The
librcam descriptor physical addresses then imply common physical base
`0xf3200000` and CCM physical base `0xf322c000`; this is an inference from the
matching offsets and addresses, not an absolute address literal in the driver
slice. The `lmtx_fw` descriptor region and the driver 96-word region now have a
concrete common register mapping. That establishes a register relationship, not
a pixel equation, segment selector or colour-space interpretation.

The register mapping and the 96-word field-extent match are established. What
remains is tracing the runtime relationship between descriptor-driven updates
and this `ig0` setter, and recovering the fields' pixel meanings, selectors and
numeric formula. In particular, this setter repeats six inputs across the whole
region; that does not prove how live updates populate or select its 16 groups.
This review makes no claim based on display register headers or another SoC's
definitions. It also does not label the two fields passed through `set_fmt` as
a colour-space or channel-order setting; their numerical packing alone is
insufficient.

Reproduction, with the original module supplied separately:

```bash
python3 inspect_ccm_driver.py \
  --module /absolute/path/to/firmware/extracted/system/lib/modules/vcam_driver.ko \
  --out /tmp/ccm_driver_evidence.json
```

Dependencies: `pyelftools` and `capstone`. The output contains metadata and
bounded analysis conclusions, not the module, its code bytes, vendor arrays or
full disassembly. No application files were changed.
