import unittest
import cv2
import numpy as np
from test_colour41q import apply_colour, colour_gate, fit_colour, to_lab


class ColourTests(unittest.TestCase):
    def test_noop_on_random_and_boundary_pixels(self):
        rng = np.random.default_rng(41)
        rgb = np.vstack([rng.uniform(0, 1, (1000, 3)), np.eye(3), np.zeros((1, 3)), np.ones((1, 3))]).astype(np.float32)
        for mode in ('global', 'protected', 'lightness'):
            shape = (4, 2) if mode == 'lightness' else (2, 2)
            np.testing.assert_allclose(apply_colour(rgb, np.zeros(shape), mode), rgb, atol=6e-8)

    def test_protection_at_neutral_and_lightness_endpoints(self):
        lab = np.array([[50, 0, 0], [0, 20, -20], [100, -20, 20], [50, 30, 40]], np.float64)
        gate = colour_gate(lab, 'protected')
        np.testing.assert_array_equal(gate[:3], np.zeros(3))
        self.assertGreater(gate[3], .9)
        self.assertLess(gate[3], 1)
        np.testing.assert_array_equal(apply_colour(np.array([[0., 0., 0.], [1., 1., 1.]], np.float32), np.ones((2, 2)), 'protected'), [[0., 0., 0.], [1., 1., 1.]])

    def test_synthetic_transform_reduces_error_for_new_colours(self):
        rng = np.random.default_rng(412)
        train = rng.uniform(.15, .8, (2000, 3)).astype(np.float32)
        test = rng.uniform(.15, .8, (400, 3)).astype(np.float32)
        known = np.array([[.07, -.03], [.02, -.09]])
        for mode in ('global', 'protected', 'lightness'):
            coefficients = np.vstack([known, [[.02, .01], [-.03, .02]]]) if mode == 'lightness' else known
            ref = apply_colour(train, coefficients, mode)
            learned, info = fit_colour([train], [ref], mode)
            target = apply_colour(test, coefficients, mode)
            prediction = apply_colour(test, learned, mode)
            before = np.abs(test - target).mean()
            after = np.abs(prediction - target).mean()
            self.assertLess(after, before * .2)
            self.assertFalse(info['degenerate_neutral_training'])

    def test_finite_bounded_output_and_reject_bad_coefficients(self):
        rgb = np.linspace(0, 1, 90).reshape(30, 3).astype(np.float32)
        for mode in ('global', 'protected'):
            result = apply_colour(rgb, np.array([[2., -3.], [-1., 4.]]), mode)
            self.assertTrue(np.isfinite(result).all())
            self.assertTrue(((result >= 0) & (result <= 1)).all())
        with self.assertRaises(ValueError):
            apply_colour(rgb, np.full((2, 2), np.nan), 'global')
        with self.assertRaises(ValueError):
            apply_colour(rgb, np.zeros((3, 3)), 'global')


if __name__ == '__main__':
    unittest.main()
