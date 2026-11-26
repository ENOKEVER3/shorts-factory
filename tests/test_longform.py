import unittest
from src import longform
from src.util import load_json


class LongformTest(unittest.TestCase):
    def test_chapters_use_rendered_starts(self):
        s = {"chapters": [{"sentence_index": i, "title": str(i)} for i in range(3)],
             "_timeline": [(0, 11.4), (11.4, 27.8), (27.8, 50)], "_duration": 50}
        text = longform.chapter_text(s)
        self.assertEqual(text.splitlines()[1:], ["00:00 0", "00:11 1", "00:27 2"])

    def test_missing_confirmed_timings_rejected(self):
        with self.assertRaises(ValueError):
            longform.chapter_text({"chapters": [{"sentence_index": 0, "title": "Intro"}]})

    def test_chapters_reject_short_sections(self):
        for starts, duration in [([0, 9, 20], 40), ([0, 10, 20], 29), ([1, 11, 21], 40)]:
            with self.subTest(starts=starts, duration=duration), self.assertRaises(ValueError):
                longform.chapter_text({"chapters": [{"sentence_index": i, "title": str(i)} for i in range(3)],
                                      "_timeline": [(x, x + 10) for x in starts], "_duration": duration})

    def test_asteroid_section_indices(self):
        s = next(s for s in load_json(longform.BANK, []) if s["id"] == "lf-001-asteroid-defense")
        self.assertEqual([c["sentence_index"] for c in s["chapters"]], [0, 4, 12, 17, 21, 25, 30, 39, 42, 46])

    def test_no_gaming_long_videos(self):
        self.assertFalse(any(s.get("theme") == "gaming" for s in load_json(longform.BANK, [])))

    def test_empty_bank_means_nothing_to_post(self):
        if not load_json(longform.BANK, []):
            self.assertIsNone(longform.next_video([]))
