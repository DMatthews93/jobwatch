import unittest

from fetchers.common import make_job
from fetchers.flags import flag


def job(title, category="soc", snippet=""):
    return flag(make_job("reed", "1", title, "Employer", "https://x", category, snippet=snippet))


class CategoryTests(unittest.TestCase):
    def test_care_titles_stay_in_social_care(self):
        for t in ("Care Assistant", "Senior Support Worker", "Healthcare Assistant - Bank",
                  "Children's Social Worker", "Deputy Homecare Manager", "Advanced Practitioner - Safeguarding"):
            self.assertEqual(job(t)["category"], "soc", t)

    def test_other_titles_move_to_other_work(self):
        for t in ("IT Support Engineer", "Data Analyst Trainee", "Optical Assistant", "Customer Care Advisor"):
            self.assertEqual(job(t)["category"], "gen", t)

    def test_other_categories_untouched(self):
        self.assertEqual(job("Specialty Doctor", category="nhs")["category"], "nhs")


class NotAJobTests(unittest.TestCase):
    def test_paid_survey_ads_flagged(self):
        j = job("Work From Home - Paid Research", snippet="Share your opinion through paid surveys, focus groups")
        self.assertIn("not-a-job", j["flags"])
        self.assertEqual(j["category"], "gen")

    def test_real_job_not_flagged(self):
        self.assertNotIn("not-a-job", job("Care Assistant")["flags"])


if __name__ == "__main__":
    unittest.main()
