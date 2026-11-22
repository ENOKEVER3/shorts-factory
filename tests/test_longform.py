import unittest
from src import longform
from src.util import load_json


class LongformTest(unittest.TestCase):
    def test_no_gaming_long_videos(self):
        self.assertFalse(any(s.get("theme") == "gaming" for s in load_json(longform.BANK, [])))

    def test_empty_bank_means_nothing_to_post(self):
        if not load_json(longform.BANK, []):
            self.assertIsNone(longform.next_video([]))
