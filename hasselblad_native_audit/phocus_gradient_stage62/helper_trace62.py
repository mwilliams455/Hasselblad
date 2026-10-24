"""Host-side observations of *original* red/blue interpolation call boundaries.

No vendor code, DNG content, calibration, or disassembly is embedded here.
A captured sample may contain private photograph pixel values and original
process addresses. Never commit captured records or print them to CI logs.
"""
from collections import Counter


BLUE = '_ZN20CGradientInterpolate12GetBlueAtRedEPKtS1_ii'
RED_BLUE = '_ZN20CGradientInterpolate17GetRedBlueAtGreenEPKtS1_S1_RtS2_ii'
LABELS = {BLUE: 'blue_at_red', RED_BLUE: 'red_blue_at_green'}


class HelperTrace62:
    """Non-mutating instruction-hook observer; CPU register IDs supplied by caller.

    The mangled signatures motivate *tentative* register interpretations:
      GetBlueAtRed       X0,X1 pointers, W2,W3 integers; low W0 return.
      GetRedBlueAtGreen  X0..X2 pointers, X3,X4 output references,
                         W5,W6 integers.
    These are observations to verify in original binary, not proven contracts.
    No method synthesizes output or changes emulated registers/memory.
    """

    def __init__(self, entries, sample_limit=16):
        assert set(entries.values()) == set(LABELS.values())
        assert sample_limit >= 0
        self.entries = dict(entries)
        self.sample_limit = sample_limit
        self.counts = Counter()
        self.returns = Counter()
        self.readable_refs = Counter()
        self.fixture_counts = Counter()
        self.samples = []
        self.pending = []
        self.fixture = None

    def start_fixture(self, label):
        if self.pending:
            raise AssertionError('Unreturned native helper before next fixture')
        self.fixture = str(label)
        self.fixture_counts.clear()

    def end_fixture(self):
        if self.pending:
            raise AssertionError('Unreturned native helper: ' + str(len(self.pending)))
        self.fixture = None

    @staticmethod
    def _read16(read, addr):
        # Invalid guesses about pointer arguments are recorded as unreadable,
        # never dereferenced directly through host ctypes.
        if not isinstance(addr, int) or addr < 0x10000 or addr & 1:
            return None
        try:
            data = bytes(read(addr, 2))
            if len(data) != 2:
                return None
            return int.from_bytes(data, 'little')
        except (ValueError, OverflowError, OSError, RuntimeError, TypeError):
            return None
        except Exception as exc:
            # Unicorn raises UcError, not necessarily one of the types above.
            if exc.__class__.__name__ != 'UcError':
                raise
            return None

    def _source_probe(self, read, args, kind):
        """A limited *private* stencil, for later reconstruction of pointer use.

        Integers in argument registers have not yet been established as strides:
        record candidate rows without treating any hypothesis as proved.
        """
        candidates = sorted({int(value & 0xffffffff) for value in args[2:]
                             if 8 <= (value & 0xffffffff) <= 4096})
        probes = []
        for i in range(2 if kind == 'blue_at_red' else 3):
            base = args[i]
            nearby = [(off, self._read16(read, base + 2*off))
                      for off in (-4, -2, -1, 0, 1, 2, 4)]
            rows = []
            for stride in candidates[:4]:
                rows.append({'candidate_stride': stride,
                             'codes': [[self._read16(read, base + 2*(dy*stride+dx))
                                        for dx in (-2, -1, 0, 1, 2)]
                                       for dy in (-2, -1, 0, 1, 2)]})
            probes.append({'arg_index': i, 'nearby': nearby, 'candidate_rows': rows})
        return probes

    def observe(self, address, regs, link, read):
        """Call before each original native instruction at PC=address.

        regs(i) reads X0+i; link() reads X30; read(addr,n) reads guest bytes.
        It is safe to observe a return site that also calls another helper.
        """
        if self.pending and address == self.pending[-1]['return_pc']:
            frame = self.pending.pop()
            kind = frame['kind']
            self.returns[kind] += 1
            if frame['sample'] is not None:
                result = frame['sample']
                if kind == 'blue_at_red':
                    result['return_low16'] = int(regs(0)) & 0xffff
                else:
                    after = [self._read16(read, p) for p in frame['refs']]
                    result['references_after'] = after
                    if all(v is not None for v in after):
                        self.readable_refs[kind] += 1
                self.samples.append(result)
        kind = self.entries.get(address)
        if kind is None:
            return
        self.counts[kind] += 1
        self.fixture_counts[kind] += 1
        n = self.fixture_counts[kind]
        # First calls catch boundary setup; later calls sample differing sites.
        collect = self.sample_limit > 0 and (n <= min(8, self.sample_limit) or n % 257 == 0)
        collect = collect and sum(s['kind'] == kind and s['fixture'] == self.fixture
                                  for s in self.samples) + sum(
                                      f['sample'] is not None and f['kind'] == kind
                                      for f in self.pending) < self.sample_limit
        args = tuple(int(regs(i)) for i in range(8))
        refs = args[3:5] if kind == 'red_blue_at_green' else ()
        sample = None
        if collect:
            sample = {'fixture': self.fixture, 'kind': kind, 'arguments_raw_x0_x7': args,
                      'caller_return_pc': int(link()),
                      'source_probes': self._source_probe(read, args, kind)}
            if refs:
                sample['references_before'] = [self._read16(read, p) for p in refs]
        self.pending.append({'kind': kind, 'return_pc': int(link()),
                             'refs': refs, 'sample': sample})

    def public_summary(self):
        # Deliberately omit *all* original executable addresses, raw registers,
        # sample source values and output pixel values.
        return {'native_entry_counts': dict(self.counts),
                'native_return_counts': dict(self.returns),
                'private_sample_counts': dict(Counter(s['kind'] for s in self.samples)),
                'sampled_red_blue_writable_references_readable':
                    self.readable_refs.get('red_blue_at_green', 0),
                'all_helper_calls_returned': not self.pending}

    def private_payload(self):
        return {'schema': 'stage62-private-native-helper-observations-v1',
                'warning': 'PRIVATE: pointers and RAW pixel data. Do not publish.',
                'register_contract_status': 'UNVERIFIED', 'samples': self.samples}
