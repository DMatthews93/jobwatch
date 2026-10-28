import unittest
from datetime import datetime, timezone

from fetchers.common import make_job
from fetchers.flags import flag
from merge import merge
from state import update


def job(source, sid, title, employer, location="Leeds", closing="2026-12-01", **kw):
    return make_job(source, sid, title, employer, f"https://x/{source}/{sid}", "priv",
                    location=location, closing=closing, **kw)


class MergeTests(unittest.TestCase):
    def test_same_job_on_two_sources_merges(self):
        a = job("nhs", "1", "Specialty Doctor, Obstetrics and Gynaecology", "Leeds Teaching Hospitals NHS Trust")
        b = job("reed", "9", "Specialty Doctor - Obstetrics & Gynaecology", "Leeds Teaching Hospitals", salary_stated=True,
                salary_min=60000, salary_max=80000)
        merged = merge([b, a])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "nhs")  # NHS Jobs wins as primary
        self.assertEqual(len(merged[0]["links"]), 2)
        self.assertEqual(merged[0]["salary_min"], 60000)  # salary filled from the other source

    def test_different_jobs_stay_separate(self):
        a = job("nhs", "1", "Consultant Obstetrician", "Leeds Teaching Hospitals NHS Trust")
        b = job("nhs", "2", "Clinical Fellow in Paediatrics", "Leeds Teaching Hospitals NHS Trust")
        self.assertEqual(len(merge([a, b])), 2)

    def test_far_apart_closing_dates_are_different_adverts(self):
        a = job("nhs", "1", "Trust Grade Doctor", "Leeds Teaching Hospitals", closing="2026-11-01")
        b = job("reed", "2", "Trust Grade Doctor", "Leeds Teaching Hospitals", closing="2027-02-01")
        self.assertEqual(len(merge([a, b])), 2)


class FlagTests(unittest.TestCase):
    def test_admin_only_matches_whole_word(self):
        j = flag(job("nhs", "1", "Doctor, Gynaecology (Administration duties)", "X", snippet=""))
        self.assertNotIn("non-doctor-role", j["flags"])
        j = flag(job("nhs", "2", "Admin Assistant", "X"))
        self.assertIn("non-doctor-role", j["flags"])

    def test_og_job_never_flagged_as_other_specialty(self):
        j = flag(job("nhs", "1", "Obstetrics and Gynaecology Registrar (children's unit)", "X"))
        self.assertNotIn("other-specialty", j["flags"])


class StateTests(unittest.TestCase):
    NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)

    def merged(self, sid="1", source="nhs"):
        return merge([job(source, sid, "Specialty Doctor", "Leeds Hospitals")])[0]

    def test_new_job_gets_first_seen_and_open_status(self):
        out = update([], [self.merged()], now=self.NOW)
        self.assertEqual(out[0]["status"], "open")
        self.assertTrue(out[0]["first_seen"].startswith("2026-11-01"))

    def test_id_is_stable_across_runs(self):
        first = update([], [self.merged()], now=self.NOW)
        second = update(first, [self.merged()], now=self.NOW)
        self.assertEqual(first[0]["id"], second[0]["id"])
        self.assertEqual(first[0]["first_seen"], second[0]["first_seen"])

    def test_vanished_job_becomes_stale_then_closed_then_dropped(self):
        first = update([], [self.merged()], now=self.NOW)
        d = lambda day: datetime(2026, 11, day, 12, 0, tzinfo=timezone.utc)
        s1 = update(first, [], now=d(1))
        self.assertEqual(s1[0]["status"], "stale")
        s2 = update(s1, [], now=d(4))
        self.assertEqual(s2[0]["status"], "closed")
        self.assertEqual(update(s2, [], now=d(10)), [])

    def test_failed_source_leaves_jobs_alone(self):
        first = update([], [self.merged()], now=self.NOW)
        later = datetime(2026, 11, 20, tzinfo=timezone.utc)
        out = update(first, [], failed_sources={"nhs"}, now=later)
        self.assertEqual(out[0]["status"], "open")

    def test_passed_closing_date_is_closed(self):
        j = merge([job("nhs", "1", "Doctor", "Leeds Hospitals", closing="2026-10-01")])[0]
        self.assertEqual(update([], [j], now=self.NOW)[0]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
