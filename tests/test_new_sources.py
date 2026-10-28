import unittest
from datetime import date

from fetchers import bmj, hospitals

LINK = ("https://www.bmj.com/careers/job/860852/specialty-doctor-obstetrics-and-gynaecology/"
        "?TrackID=8&utm_source=rss&utm_medium=feed&utm_campaign=general")
DESC = ("\n£63,696 to £102,689 Per annum:\n\nNorth Cumbria Integrated Care NHS Foundation Trust:\n"
        "The Specialty Doctor is responsible for the Consultants in Obstetrics and Gynaecology.\nCarlisle\n")


class BmjTests(unittest.TestCase):
    def test_feed_item(self):
        j = bmj.parse_item("North Cumbria Integrated Care NHS Foundation Trust: Specialty Doctor Obstetrics "
                           "and Gynaecology", DESC, LINK, "nhs")
        self.assertEqual(j["title"], "Specialty Doctor Obstetrics and Gynaecology")
        self.assertEqual(j["employer"], "North Cumbria Integrated Care NHS Foundation Trust")
        self.assertEqual(j["source_id"], "860852")
        self.assertEqual(j["url"], "https://www.bmj.com/careers/job/860852/specialty-doctor-obstetrics-and-gynaecology/")
        self.assertEqual(j["location"], "Carlisle")
        self.assertEqual(j["category"], "nhs")
        self.assertEqual((j["salary_min"], j["salary_max"]), (63696, 102689))
        self.assertIn("Specialty Doctor is responsible", j["snippet"])

    def test_non_nhs_employer_is_private(self):
        desc = "\nCompetitive:\n\nLondon Women's Clinic:\nJoin our team.\nLondon\n"
        j = bmj.parse_item("London Women's Clinic: Fertility Doctor", desc, LINK, "nhs")
        self.assertEqual(j["category"], "priv")
        self.assertFalse(j["salary_stated"])

    def test_nhs_group_without_nhs_in_name_stays_nhs(self):
        desc = "\nPA PR:\n\nHumber Health Partnership:\nSee the job description.\nKingston upon Hull\n"
        j = bmj.parse_item("Humber Health Partnership: Consultant Obstetrics & Gynaecology", desc, LINK, "nhs")
        self.assertEqual(j["category"], "nhs")

    def test_skips_bmj_notices(self):
        desc = "\nN/A:\n\nWill be holding a byelection:\nVote now.\nLondon (Central)\n"
        self.assertIsNone(bmj.parse_item("BMA: BMA UK Council by elections coming soon", desc, LINK, "nhs"))

    def test_detail_page(self):
        page = '"Contract Type": "Fixed Contract", "Hours": "Full Time", "Location": "CA2 7HY",'
        j = bmj.parse_item("North Cumbria Integrated Care NHS Foundation Trust: Specialty Doctor", DESC, LINK, "nhs")
        bmj._add_detail(j, bmj.parse_detail(page))
        self.assertEqual((j["full_time"], j["contract_type"]), (True, "fixed-term"))
        self.assertEqual(j["location"], "Carlisle, CA2 7HY")
        self.assertTrue(j["detail_done"])


class HospitalTests(unittest.TestCase):
    def test_role_category(self):
        cases = {"Resident Medical Officer": "priv", "Gynaecology Clinic Doctor": "priv",
                 "Healthcare Assistant FTC": "soc", "Bank Engineering Administrator": "gen",
                 "Outpatient Receptionist": "gen", "Aesthetic Practitioner": "aes",
                 "Theatre Porter": None, "Bank Hand Specialist Physiotherapist": None,
                 "Women's Health Physiotherapist - Pelvic Health (Bank)": None,
                 "Gynaecology Nurse Specialist": None,
                 "Theatre Practitioner - Anaesthetics & Recovery": None}
        for title, want in cases.items():
            self.assertEqual(hospitals.role_category(title), want, title)

    def test_workday_posted(self):
        today = date(2026, 10, 28)
        self.assertEqual(hospitals.workday_posted("Posted Today", today), "2026-10-28")
        self.assertEqual(hospitals.workday_posted("Posted Yesterday", today), "2026-10-27")
        self.assertEqual(hospitals.workday_posted("Posted 3 Days Ago", today), "2026-10-25")
        self.assertIsNone(hospitals.workday_posted("Posted 30+ Days Ago", today))

    def test_place(self):
        self.assertEqual(hospitals._place("EDINBURGH, MIDLOTHIAN, United Kingdom"), "Edinburgh, Midlothian")
        self.assertEqual(hospitals._place("Chorley"), "Chorley")
        self.assertEqual(hospitals._place("2 Locations"), "")


if __name__ == "__main__":
    unittest.main()
