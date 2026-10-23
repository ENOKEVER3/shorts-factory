import unittest
from pathlib import Path

from src import visuals


class SegmentsTest(unittest.TestCase):
    TL = [(0.0, 3.0, "a"), (3.0, 6.0, "b"), (6.0, 9.0, "c")]

    def test_one_image_per_sentence(self):
        segs = visuals.segments([Path("1"), Path("2"), Path("3")], self.TL, 10.0)
        self.assertEqual([(s, e) for _p, s, e in segs], [(0.0, 3.0), (3.0, 6.0), (6.0, 10.0)])

    def test_failed_image_keeps_previous_on_screen(self):
        segs = visuals.segments([Path("1"), None, Path("3")], self.TL, 10.0)
        self.assertEqual([(str(p), s, e) for p, s, e in segs], [("1", 0.0, 6.0), ("3", 6.0, 10.0)])

    def test_all_failed_means_no_images(self):
        self.assertEqual(visuals.segments([None, None, None], self.TL, 10.0), [])

    def test_prompt_forbids_text(self):
        self.assertIn("no text", visuals.build_prompt("T", "A robot walks."))


if __name__ == "__main__":
    unittest.main()
