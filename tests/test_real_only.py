import tempfile, unittest
from pathlib import Path
from unittest import mock
from src import visuals


class RealOnly(unittest.TestCase):
    def test_no_drawn_cards_when_real_only(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d)
            real = w / "real.jpg"
            visuals.local_card("x", real, 1)  # stands in for a real photo file
            script = {"id": "t", "title": "Sun", "sentences": ["a", "b", "c"]}
            def fake_photo(photo, dst, used):
                if "real.jpg" in used:
                    return None
                used.add("real.jpg"); dst.write_bytes(real.read_bytes()); return "NASA"
            with mock.patch.object(visuals, "_fetch", side_effect=RuntimeError("down")), \
                 mock.patch.object(visuals, "find_photo", side_effect=fake_photo), \
                 mock.patch.object(visuals, "_accept", return_value=True), \
                 mock.patch.object(visuals, "scene_plan", return_value=[(None, None)] * 3):
                visuals.illustrate(script, w, 0, {"real_images_only": True, "gemini_images": False})
            self.assertNotIn("motion graphic card", script["_sources"])


if __name__ == "__main__":
    unittest.main()
