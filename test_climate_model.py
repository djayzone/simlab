import unittest

from climate_model import advance_drought, drought_target


class DroughtModelTests(unittest.TestCase):
    def test_normal_summer_converges_to_moderate_drought(self):
        target = drought_target('été', 25.0, 0.34, 0.10, 0.30)
        self.assertGreater(target, 0.25)
        self.assertLess(target, 0.60)

    def test_prolonged_extreme_summer_can_become_severe_without_saturating(self):
        drought = 0.20
        for _ in range(120):
            drought = advance_drought(drought, 'été', 36.0, 0.20, 0.02, 0.70)
        self.assertGreater(drought, 0.70)
        self.assertLess(drought, 0.90)

    def test_prolonged_wet_autumn_recovers_deep_drought(self):
        drought = 0.90
        for _ in range(30):
            drought = advance_drought(drought, 'automne', 13.0, 0.75, 0.55, 0.20)
        self.assertLess(drought, 0.30)
        self.assertGreaterEqual(drought, 0.08)

    def test_single_downpour_does_not_erase_deep_drought(self):
        drought = advance_drought(0.90, 'automne', 13.0, 0.80, 0.85, 0.20)
        self.assertGreater(drought, 0.80)
        self.assertLess(drought, 0.90)

    def test_drought_is_always_bounded(self):
        self.assertGreaterEqual(advance_drought(-3, 'hiver', -10, 0.9, 1, 0), 0.0)
        self.assertLessEqual(advance_drought(3, 'été', 50, 0, 0, 1), 0.98)


if __name__ == '__main__':
    unittest.main()
