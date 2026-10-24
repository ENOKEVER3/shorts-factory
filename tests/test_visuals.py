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


class LocalCardTest(unittest.TestCase):
    def test_local_card_produces_valid_image(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "card.jpg"
            visuals.local_card("A robot walks.", dst, seed=3)
            self.assertTrue(visuals._valid_image(dst))

    def test_local_card_is_deterministic_per_sentence(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            a = visuals.local_card("Same sentence.", Path(tmp) / "a.jpg", seed=1)
            b = visuals.local_card("Same sentence.", Path(tmp) / "b.jpg", seed=1)
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
