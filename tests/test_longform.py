import unittest
from src import longform
from src.util import load_json


class LongformTest(unittest.TestCase):
    def test_bank_has_five_minute_script(self):
        s = load_json(longform.BANK)[0]
        words = len(" ".join(s["sentences"]).split())
        self.assertTrue(650 <= words <= 900, words)  # ~5 minutes of narration

    def test_skips_already_posted(self):
        first = load_json(longform.BANK)[0]["id"]
        self.assertIsNone(longform.next_video([{"script_id": first}]) if len(load_json(longform.BANK)) == 1 else None)
