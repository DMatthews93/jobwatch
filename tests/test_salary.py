import unittest

from fetchers.common import infer_contract, parse_hours, parse_salary


class SalaryTests(unittest.TestCase):
    def test_annual_range(self):
        s = parse_salary("£52,530 to £81,618 a year")
        self.assertEqual((s["salary_min"], s["salary_max"]), (52530, 81618))
        self.assertTrue(s["salary_stated"])
        self.assertFalse(s["salary_converted"])

    def test_hourly_converted_to_full_time_annual(self):
        s = parse_salary("£12.71 an hour")
        self.assertAlmostEqual(s["salary_min"], 24784, delta=1)
        self.assertTrue(s["salary_converted"])

    def test_hourly_uses_known_hours(self):
        s = parse_salary("£10 per hour", hours=40)
        self.assertEqual(s["salary_min"], 20800)

    def test_day_rate(self):
        self.assertEqual(parse_salary("£150 per day")["salary_min"], 39000)

    def test_k_ranges(self):
        for text in ("£25k - £30k", "£25-30k per annum"):
            s = parse_salary(text)
            self.assertEqual((s["salary_min"], s["salary_max"]), (25000, 30000), text)

    def test_not_stated(self):
        for text in ("Competitive", "Not specified", "", None):
            self.assertFalse(parse_salary(text)["salary_stated"], text)

    def test_ignores_silly_amounts(self):
        self.assertFalse(parse_salary("£500 bonus per annum")["salary_stated"])


class HoursContractTests(unittest.TestCase):
    def test_explicit_hours(self):
        self.assertEqual(parse_hours("20 hours per week"), (20.0, False))
        self.assertEqual(parse_hours("37.5 hours a week"), (37.5, True))

    def test_full_and_part_time(self):
        self.assertEqual(parse_hours("Full-time"), (None, True))
        self.assertEqual(parse_hours("Part time"), (None, False))
        self.assertEqual(parse_hours("Full time or part time"), (None, None))

    def test_contract(self):
        self.assertEqual(infer_contract("Permanent"), "permanent")
        self.assertEqual(infer_contract("12 month fixed-term contract"), "fixed-term")
        self.assertEqual(infer_contract("Permanent or fixed term"), "unknown")
        self.assertEqual(infer_contract("Locum shifts"), "locum")


if __name__ == "__main__":
    unittest.main()
