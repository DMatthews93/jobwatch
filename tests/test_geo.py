import unittest

import geo


def place(name, kind, lat=1.0):
    return {"name_1": name, "local_type": kind, "latitude": lat, "longitude": 0.0}


class PlaceTests(unittest.TestCase):
    def test_city_centre_dropped(self):
        self.assertEqual(geo._place_key("Newcastle City Centre"), "p2:newcastle")
        self.assertEqual(geo._place_key("Leeds Town Centre, West Yorkshire"), "p2:leeds")

    def test_prefers_city_over_same_named_suburb(self):
        results = [place("Newcastle", "Suburban Area", 56.0), place("Newcastle Emlyn", "Town", 52.0),
                   place("Newcastle upon Tyne", "City", 54.97)]
        self.assertEqual(geo.best_place("newcastle", results)["latitude"], 54.97)

    def test_prefers_city_over_hamlet(self):
        results = [place("Sunderland", "Hamlet", 54.0), place("Sunderland", "City", 54.9)]
        self.assertEqual(geo.best_place("sunderland", results)["latitude"], 54.9)

    def test_exact_town_beats_longer_name(self):
        results = [place("Washington", "Town", 54.9), place("Washington Village", "Suburban Area", 54.8)]
        self.assertEqual(geo.best_place("washington", results)["latitude"], 54.9)

    def test_ignores_names_that_only_contain_the_query(self):
        self.assertIsNone(geo.best_place("leeds", [place("New Leeds", "Village")]))


if __name__ == "__main__":
    unittest.main()
