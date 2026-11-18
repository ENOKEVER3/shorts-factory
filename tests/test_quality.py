import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from src import quality, render

CFG = {"video": {"width": 1080, "height": 1920, "fps": 30}}
GOOD = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920,
                     "avg_frame_rate": "30/1"}, {"codec_type": "audio", "codec_name": "aac"}],
        "format": {"duration": "42.0"}}


def _detailed(path, shift=0):
    im = Image.new("RGB", (800, 800), "black")
    d = ImageDraw.Draw(im)
    for i in range(0, 800, 40):
        d.line([(i + shift, 0), (800 - i, 800)], fill=(255, (i * 3) % 255, 90), width=6)
    im.save(path)


class ImageCheckTest(unittest.TestCase):
    def test_blank_picture_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.png"
            Image.new("RGB", (800, 800), (40, 40, 40)).save(p)
            self.assertFalse(quality.check_image(p)[0])

    def test_small_picture_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.png"
            _detailed(p)
            Image.open(p).resize((300, 300)).save(p)
            self.assertFalse(quality.check_image(p)[0])

    def test_detailed_picture_passes_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / "a.png", Path(t) / "b.png"
            _detailed(a)
            _detailed(b)
            seen = []
            self.assertTrue(quality.check_image(a, seen)[0])
            self.assertFalse(quality.check_image(b, seen)[0])


class VideoCheckTest(unittest.TestCase):
    def test_good_video_passes(self):
        r = quality.evaluate(GOOD, 0.0, -18.0, -1.0, CFG)
        self.assertTrue(r["passed"])
        self.assertEqual(r["score"], 100)

    def test_missing_audio_blocks_upload(self):
        info = {**GOOD, "streams": GOOD["streams"][:1]}
        self.assertFalse(quality.evaluate(info, 0.0, None, None, CFG)["passed"])

    def test_wrong_resolution_blocks_upload(self):
        info = {**GOOD, "streams": [{**GOOD["streams"][0], "width": 720}, GOOD["streams"][1]]}
        self.assertFalse(quality.evaluate(info, 0.0, -18.0, -1.0, CFG)["passed"])

    def test_silent_narration_blocks_upload(self):
        self.assertFalse(quality.evaluate(GOOD, 0.0, -45.0, -20.0, CFG)["passed"])

    def test_over_60_seconds_blocks_upload(self):
        info = {**GOOD, "format": {"duration": "75"}}
        self.assertFalse(quality.evaluate(info, 0.0, -18.0, -1.0, CFG)["passed"])


class CameraMoveTest(unittest.TestCase):
    def test_consecutive_scenes_move_differently(self):
        moves = [render.camera_move(n, 90) for n in range(5)]
        self.assertEqual(len(set(moves)), 5)
