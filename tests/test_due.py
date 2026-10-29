import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from fetchers import common


class DueTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.dir.name, "last_fetch.json")
        patcher = mock.patch.object(common, "LAST_FETCH_FILE", self.file)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)
        env = mock.patch.dict(os.environ, {"FORCE_FETCH": ""})
        env.start()
        self.addCleanup(env.stop)
        self.now = datetime(2026, 10, 29, 11, 39, tzinfo=timezone.utc)

    def write(self, when):
        with open(self.file, "w") as f:
            json.dump({"reed": when}, f)

    def test_never_fetched_is_due(self):
        self.assertTrue(common.due("reed", 2, self.now))

    def test_recent_fetch_is_not_due(self):
        self.write("2026-10-29T10:45:00Z")
        self.assertFalse(common.due("reed", 2, self.now))

    def test_odd_hour_after_gap_is_due(self):
        # the old clock rule skipped this (odd hour, minute >= 30)
        self.write("2026-10-29T08:15:00Z")
        self.assertTrue(common.due("reed", 2, self.now))

    def test_slightly_early_run_counts(self):
        self.write("2026-10-29T09:45:00Z")
        self.assertTrue(common.due("reed", 2, self.now))

    def test_manual_run_forces(self):
        self.write("2026-10-29T11:30:00Z")
        with mock.patch.dict(os.environ, {"FORCE_FETCH": "1"}):
            self.assertTrue(common.due("reed", 2, self.now))


if __name__ == "__main__":
    unittest.main()
