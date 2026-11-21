import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import align, captions, queue

TL = [(0.0, 2.0, "Why is Mars red?"), (2.14, 6.0, "Iron dust rusted over 4 billion years.")]


class SafeZoneTest(unittest.TestCase):
    def test_everything_inside_youtube_safe_zone(self):
        with tempfile.TemporaryDirectory() as t:
            out = captions.build_ass(TL, 6.5, "MAKOKOGW", Path(t) / "c.ass", 1080, 1920,
                                     "Why Mars is red and what that means")
            text = out.read_text()
        z = captions.safe_zone(1080, 1920)
        for x, y in re.findall(r"\\pos\((\d+),(\d+)\)", text):
            self.assertTrue(z["left"] <= int(x) <= z["right"])
            self.assertTrue(z["top"] <= int(y) <= z["bottom"])
        self.assertLessEqual(z["right"], 1080 - 190)  # clear of like/comment/share buttons
        self.assertLessEqual(z["bottom"], int(1920 * 0.72))  # clear of title + Subscribe

    def test_long_words_are_squeezed_to_fit(self):
        width = captions.safe_zone(1080, 1920)["right"] - captions.safe_zone(1080, 1920)["left"]
        sc = captions.fit_scale("ELECTROMAGNETIC", captions.CAP_SIZE, width)
        self.assertLessEqual(15 * captions.CAP_SIZE * captions.CHAR_W * sc / 100, width)


class WhisperAlignTest(unittest.TestCase):
    def test_script_words_take_spoken_times(self):
        heard = [(0.1, 0.3, "Why"), (0.35, 0.5, "is"), (0.9, 1.3, "Mars"), (1.4, 1.8, "red?")]
        words = align.map_to_script(heard, TL[:1])[0]
        self.assertEqual([w[2] for w in words], ["Why", "is", "Mars", "red?"])
        self.assertAlmostEqual(words[2][0], 0.9)

    def test_captions_start_when_word_is_spoken(self):
        heard = [(0.1, 0.3, "Why"), (0.35, 0.5, "is"), (0.9, 1.3, "Mars"), (1.4, 1.8, "red?")]
        words = align.map_to_script(heard, TL[:1])
        with tempfile.TemporaryDirectory() as t:
            text = captions.build_ass(TL[:1], 2.5, "K", Path(t) / "c.ass", 1080, 1920, "", words).read_text()
        self.assertIn("0:00:01.40,0:00:02.00,Cap", text)  # "red?" appears when spoken


class QueueTest(unittest.TestCase):
    def test_prune_drops_posted_and_stale(self):
        now = datetime(2026, 11, 21, tzinfo=timezone.utc)
        q = {"items": [
            {"script_id": "a", "created_at": now.isoformat()},
            {"script_id": "b", "created_at": now.isoformat()},
            {"script_id": "c", "created_at": (now - timedelta(days=11)).isoformat()},
        ]}
        q = queue.prune(q, {"b"}, {"queue": {"max_age_days": 10}}, now)
        self.assertEqual([i["script_id"] for i in q["items"]], ["a"])
        self.assertTrue(queue.needs_more(q, {"queue": {"target_ready": 2}}))


if __name__ == "__main__":
    unittest.main()
