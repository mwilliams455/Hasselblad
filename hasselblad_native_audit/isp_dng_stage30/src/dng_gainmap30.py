#!/usr/bin/env python3
"""Stage30 offline DNG OpcodeList2 GainMap-only diagnostic correction.

No Hasselblad/IQ assets. Strict opt-in to the neutral Stage24 DNG reference.
Parse standard big-endian DNG opcodes; execute only GainMap (opcode 9) on a
single-plane black/white range-mapped RGGB CFA before diagnostic demosaicing.
Unknown/unsupported opcodes and malformed records abort; never silently skip.
This is software DNG reference processing, not verified HNCS/Adobe DNG SDK
bit-exact photographic processing and not a production Android camera hook.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct
import math
import numpy as np
import cv2

MAX_LIST_BYTES = 32 * 1024 * 1024
MAX_OPCODES = 64
MAX_GRID_ELEMENTS = 1024 * 1024
HEADER = struct.Struct('>I4sII')
AREA_AND_GRID = struct.Struct('>10I4dI')

@dataclass(frozen=True)
class GainMap:
    top: int
    left: int
    bottom: int
    right: int
    plane: int
    planes: int
    row_pitch: int
    col_pitch: int
    points_v: int
    points_h: int
    spacing_v: float
    spacing_h: float
    origin_v: float
    origin_h: float
    map_planes: int
    gains: np.ndarray


def _read_gmap(payload: bytes, shape: tuple[int, int]) -> GainMap:
    height, width = shape
    if len(payload) < AREA_AND_GRID.size:
        raise ValueError('GainMap header truncated')
    (top, left, bottom, right, plane, planes, row_pitch, col_pitch,
     points_v, points_h, spacing_v, spacing_h, origin_v, origin_h,
     map_planes) = AREA_AND_GRID.unpack_from(payload)
    if not (0 <= top < bottom <= height and 0 <= left < right <= width):
        raise ValueError('GainMap area outside RAW image')
    # Deliberately restrict to the single-plane Bayer stage2 image. Four
    # separate CFA-site maps (each row/col pitch 2) are supported.
    if plane != 0 or planes != 1 or map_planes != 1:
        raise ValueError('Multi-plane or nonzero-plane GainMap unsupported for CFA')
    if not (row_pitch in (1, 2) and col_pitch in (1, 2)):
        raise ValueError('Unverified CFA pitch')
    if not (1 <= points_v <= 4096 and 1 <= points_h <= 4096 and
            points_v * points_h <= MAX_GRID_ELEMENTS):
        raise ValueError('GainMap grid exceeds bounded diagnostic domain')
    terms=(spacing_v, spacing_h, origin_v, origin_h)
    if not all(math.isfinite(v) for v in terms) or spacing_v <= 0 or spacing_h <= 0:
        raise ValueError('GainMap spacing/origin invalid')
    if not (-4 <= origin_v <= 4 and -4 <= origin_h <= 4 and
            spacing_v <= 4 and spacing_h <= 4):
        raise ValueError('GainMap coordinate domain unsupported')
    size = AREA_AND_GRID.size + 4 * points_v * points_h
    if len(payload) != size:
        raise ValueError('GainMap payload length inconsistent with grid')
    gains = np.frombuffer(payload, dtype='>f4', offset=AREA_AND_GRID.size,
                          count=points_v*points_h).astype(np.float32).reshape(points_v, points_h)
    if not np.isfinite(gains).all() or (gains <= 0).any() or (gains > 32).any():
        raise ValueError('GainMap contains invalid gains')
    return GainMap(top,left,bottom,right,plane,planes,row_pitch,col_pitch,
                   points_v,points_h,spacing_v,spacing_h,origin_v,origin_h,
                   map_planes,gains)


def parse_opcode_list2(blob: bytes, shape: tuple[int, int]) -> tuple[GainMap, ...]:
    """Require every declared opcode to be a fully supported GainMap.

    Reject even unknown optional opcodes: the goal is to avoid misleadingly
    labelling an incomplete offline result as 'DNG-corrected'. The opcode
    wrapper is big-endian, independent of TIFF endianness.
    """
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        raise ValueError('OpcodeList2 must be raw byte payload')
    data = bytes(blob)
    if len(data) < 4 or len(data) > MAX_LIST_BYTES:
        raise ValueError('OpcodeList2 invalid size')
    height, width = shape
    if not (height >= 4 and width >= 4 and height <= 65535 and width <= 65535):
        raise ValueError('Unsupported DNG dimensions')
    count = struct.unpack_from('>I', data)[0]
    if not 1 <= count <= MAX_OPCODES:
        raise ValueError('OpcodeList2 empty/exceeds bounded count')
    position = 4
    result: list[GainMap] = []
    for _ in range(count):
        if len(data) - position < HEADER.size:
            raise ValueError('Opcode header truncated')
        opcode_id, version, flags, param_len = HEADER.unpack_from(data, position)
        position += HEADER.size
        if flags & ~3:
            raise ValueError('Unrecognized DNG opcode flags')
        if version > bytes([1, 7, 1, 0]):
            raise ValueError('Unrecognized DNG opcode version')
        if param_len > MAX_LIST_BYTES or len(data) - position < param_len:
            raise ValueError('Opcode payload truncated')
        part = data[position:position+param_len]
        position += param_len
        if opcode_id != 9:
            raise ValueError(f'Unsupported DNG opcode ID {opcode_id}, optional={bool(flags & 1)}')
        if version < b'\x01\x03\x00\x00':
            raise ValueError('GainMap minimum version invalid')
        result.append(_read_gmap(part, shape))
    if position != len(data):
        raise ValueError('Trailing bytes after OpcodeList2')
    return tuple(result)


def apply_gainmaps(cfa_linear: np.ndarray, maps: tuple[GainMap, ...]) -> tuple[np.ndarray,dict]:
    """Apply GainMap on range-mapped single-plane CFA, before demosaic.

    The interpolation uses pixel-center normalized image coordinates and
    edge replication. The opcode specifies its own rectangle and pitch, so
    four independently sampled Bayer sites remain distinct.
    """
    if cfa_linear.ndim != 2 or cfa_linear.dtype != np.float32 or not np.isfinite(cfa_linear).all():
        raise ValueError('Expected finite float32 single-plane range-mapped CFA')
    if not maps:
        raise ValueError('No GainMap corrections requested')
    height,width = cfa_linear.shape
    result = cfa_linear.copy()
    changed = 0
    selected = 0
    for entry in maps:
        if (entry.top < 0 or entry.left < 0 or entry.bottom>height or entry.right>width or
                entry.row_pitch not in (1,2) or entry.col_pitch not in (1,2) or
                entry.gains.shape != (entry.points_v,entry.points_h)):
            raise ValueError('Malformed GainMap structure')
        rows = np.arange(entry.top,entry.bottom,entry.row_pitch,dtype=np.float64)
        cols = np.arange(entry.left,entry.right,entry.col_pitch,dtype=np.float64)
        row_idx = np.clip(((rows+.5)/height-entry.origin_v)/entry.spacing_v,0,entry.points_v-1)
        col_idx = np.clip(((cols+.5)/width-entry.origin_h)/entry.spacing_h,0,entry.points_h-1)
        rv=np.floor(row_idx).astype(np.intp);rh=np.minimum(rv+1,entry.points_v-1)
        cv=np.floor(col_idx).astype(np.intp);ch=np.minimum(cv+1,entry.points_h-1)
        dr=(row_idx-rv)[:,None];dc=(col_idx-cv)[None,:]
        gain=(entry.gains[rv[:,None],cv[None,:]]*(1-dr)*(1-dc)
            +entry.gains[rh[:,None],cv[None,:]]*dr*(1-dc)
            +entry.gains[rv[:,None],ch[None,:]]*(1-dr)*dc
            +entry.gains[rh[:,None],ch[None,:]]*dr*dc)
        dst=result[entry.top:entry.bottom:entry.row_pitch,
                   entry.left:entry.right:entry.col_pitch]
        if not np.isfinite(gain).all() or np.shape(dst)!=np.shape(gain):
            raise ValueError('GainMap coordinate calculation failed')
        new=np.minimum(dst.astype(np.float64)*gain,1.0).astype(np.float32)
        if not np.isfinite(new).all():
            raise ValueError('GainMap overflow')
        changed+=int(np.count_nonzero(new!=dst))
        selected+=int(dst.size)
        dst[:,:]=new
    return result,{'schema':'stage30-gainmap-mosaic-correction-v1',
                   'gainmap_count':len(maps),
                   'covered_CFA_site_writes':selected,
                   'CFA_site_value_changes':changed,
                   'partial_coverage_possible':True,
                   'gain_applied_after_range_mapping':True,
                   'gain_applied_before_demosaic':True,
                   'original_X2D_HNCS_applied':False,
                   'SDK_bit_exact_parity_proven':False}


def demosaic_linear_rg_reference(mosaic: np.ndarray) -> np.ndarray:
    """Explicit diagnostic RGGB bilinear CFA interpolation in linear float.

    This is not Photon, Hasselblad or DNG SDK demosaic. A separable 3x3 kernel
    normalized by each CFA site's support prevents channel-order swaps and
    avoids uint16 re-quantization of GainMap-corrected samples.
    """
    if mosaic.ndim!=2 or mosaic.dtype!=np.float32 or mosaic.shape[0]<4 or mosaic.shape[1]<4:
        raise ValueError('Expected 2D float32 RGGB CFA')
    kernel=np.asarray([[1,2,1],[2,4,2],[1,2,1]],dtype=np.float32)
    out=np.empty((*mosaic.shape,3),dtype=np.float32)
    specs=[((0,0),0),((0,1),1),((1,0),1),((1,1),2)]
    masks=[np.zeros(mosaic.shape,dtype=np.float32) for _ in range(3)]
    for (ry,rx),channel in specs:
        masks[channel][ry::2,rx::2]=1.0
    for channel,mask in enumerate(masks):
        weighted=cv2.filter2D(mosaic*mask,-1,kernel,borderType=cv2.BORDER_REFLECT_101)
        support=cv2.filter2D(mask,-1,kernel,borderType=cv2.BORDER_REFLECT_101)
        if (support<=0).any():
            raise ValueError('Demosaic CFA support lost')
        out[:,:,channel]=weighted/support
    if not np.isfinite(out).all():
        raise ValueError('Demosaic produced invalid channel')
    return out
