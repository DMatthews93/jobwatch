import unittest

import geo
from fetchers.reed import stated_location


class StatedLocationTests(unittest.TestCase):
    def test_reads_location_from_advert(self):
        text = "Care Worker Job Type: 6 Month Contract Location: Orkney Pay: 18 per hour Shift Pattern: Day"
        self.assertEqual(stated_location(text), "Orkney")

    def test_stops_at_brackets_and_full_stops(self):
        self.assertEqual(stated_location("Location: Gateshead (Site-Based). Hours: 37.5"), "Gateshead")
        self.assertEqual(stated_location("Location: Sunderland. Salary: £25k"), "Sunderland")

    def test_none_stated(self):
        self.assertEqual(stated_location("A great role in a friendly team."), "")

    def test_island_names_resolve_to_their_main_town(self):
        self.assertEqual(geo._place_key("Orkney"), "p3:kirkwall")
        self.assertEqual(geo._place_key("Shetland Islands"), "p3:lerwick")


if __name__ == "__main__":
    unittest.main()
