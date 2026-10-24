"""Pure-Python lifecycle tests for the tracing probe; no vendor APK required."""
import unittest
from helper_trace62 import HelperTrace62


class Fake:
    def __init__(self):
        self.values = [0]*8
        self.lr = 0
        self.mem = bytearray(0x50000)

    def reg(self, i):
        return self.values[i]

    def read(self, addr, size):
        if not 0 <= addr < len(self.mem) or addr+size > len(self.mem):
            raise ValueError('unmapped')
        return self.mem[addr:addr+size]

    def set16(self, addr, value):
        self.mem[addr:addr+2] = value.to_bytes(2, 'little')


class TraceTests(unittest.TestCase):
    def make(self, limit=16):
        return HelperTrace62({0x1000: 'blue_at_red', 0x2000: 'red_blue_at_green'}, limit)

    def event(self, tracer, fake, pc):
        tracer.observe(pc, fake.reg, lambda: fake.lr, fake.read)

    def test_return_value_and_no_cpu_mutation(self):
        f = Fake(); f.lr = 0x3000
        f.values = [0x20000, 0x21000, 12, 24, 0, 0, 0, 0]
        f.set16(0x20000, 123); f.set16(0x21000, 234)
        t = self.make(); t.start_fixture('synthetic')
        original = bytes(f.mem)
        self.event(t, f, 0x1000)
        self.assertEqual(bytes(f.mem), original)
        f.values[0] = 0xabcdef5678
        self.event(t, f, 0x3000)
        t.end_fixture()
        self.assertEqual(t.samples[0]['return_low16'], 0x5678)
        self.assertEqual(t.public_summary()['native_entry_counts'], {'blue_at_red': 1})
        self.assertEqual(t.public_summary()['native_return_counts'], {'blue_at_red': 1})
        self.assertNotIn('source_probes', str(t.public_summary()))
        self.assertNotIn('arguments_raw', str(t.public_summary()))

    def test_output_ref_writes_and_unreadable_guesses(self):
        f = Fake(); f.lr = 0x3200
        f.values = [0x21000, 0x22000, 0x23000, 0x24000, 0x25000, 12, 20, 0]
        f.set16(0x24000, 41); f.set16(0x25000, 42)
        t = self.make(); t.start_fixture('edge')
        self.event(t, f, 0x2000)
        f.set16(0x24000, 110); f.set16(0x25000, 220)
        self.event(t, f, 0x3200); t.end_fixture()
        s=t.samples[0]
        self.assertEqual(s['references_before'], [41, 42])
        self.assertEqual(s['references_after'], [110, 220])
        self.assertEqual(t.public_summary()['sampled_red_blue_writable_references_readable'], 1)
        t.start_fixture('bad_ptr')
        f.values[3] = 0; f.values[4] = 0xffffffffffffffff
        self.event(t, f, 0x2000)
        self.event(t, f, 0x3200); t.end_fixture()
        self.assertEqual(t.samples[1]['references_after'], [None, None])

    def test_nested_call_order_and_empty_stack_guard(self):
        f = Fake(); t = self.make(); t.start_fixture('nested')
        f.lr = 0x3000
        self.event(t, f, 0x1000)
        f.lr = 0x1004
        self.event(t, f, 0x2000)
        self.event(t, f, 0x1004)
        self.assertEqual(t.returns['red_blue_at_green'], 1)
        self.event(t, f, 0x3000)
        t.end_fixture()
        self.assertEqual(t.returns['blue_at_red'], 1)
        t.start_fixture('unreturned')
        self.event(t, f, 0x1000)
        with self.assertRaises(AssertionError):
            t.end_fixture()

    def test_sample_limits_and_counts_remain_separate(self):
        f = Fake(); t = self.make(limit=3); t.start_fixture('impulse')
        f.lr = 0x3000
        for _ in range(400):
            self.event(t, f, 0x1000)
            self.event(t, f, 0x3000)
        t.end_fixture()
        self.assertEqual(t.counts['blue_at_red'], 400)
        self.assertEqual(len(t.samples), 3)
        self.assertEqual(t.returns['blue_at_red'], 400)
        self.assertEqual(t.public_summary()['private_sample_counts'], {'blue_at_red': 3})

    def test_can_disable_private_probes(self):
        f = Fake(); t = self.make(limit=0); t.start_fixture('none'); f.lr=0x3000
        self.event(t, f, 0x1000); self.event(t, f, 0x3000); t.end_fixture()
        self.assertEqual(t.samples, [])
        self.assertEqual(t.returns['blue_at_red'], 1)


if __name__ == '__main__':
    unittest.main()
