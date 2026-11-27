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
            script = {"id": "t", "title": "Earth", "sentences": ["Earth spins.", "Earth rotates.", "Earth has an axis."]}
            def fake_photo(photo, dst, used):
                dst.write_bytes(real.read_bytes()); return "NASA"
            with mock.patch.object(visuals, "_fetch", side_effect=AssertionError("AI must not run")), \
                 mock.patch.object(visuals, "local_card", side_effect=AssertionError("cards must not run")), \
                 mock.patch.object(visuals, "find_photo", side_effect=fake_photo), \
                 mock.patch.object(visuals, "_accept", return_value=True), \
                 mock.patch.object(visuals, "scene_plan", return_value=[(None, None)] * 3):
                visuals.illustrate(script, w, 0, {"real_images_only": True, "gemini_images": False})
            self.assertNotIn("motion graphic card", script["_sources"])

    def test_missing_real_photo_blocks_instead_of_drawing(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(visuals, "find_photo", return_value=None), \
             mock.patch.object(visuals, "local_card") as card:
            with self.assertRaisesRegex(RuntimeError, "No matching real photo for any scene"):
                visuals.illustrate({"id": "x", "title": "Earth", "sentences": ["Earth spins."]},
                                   Path(d), 0, {"real_images_only": True})
            card.assert_not_called()

    def test_missing_scene_holds_nearest_real_photo(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d); real = w / "real.jpg"
            visuals.local_card("x", real, 1)
            calls = []
            def fake(photo, dst, used):
                calls.append(1)
                if len(calls) == 2:
                    return None
                dst.write_bytes(real.read_bytes()); return "NASA"
            script = {"id": "y", "title": "T", "sentences": ["Mars.", "Moon.", "Sun."],
                      "photos": [{"source": "nasa", "query": q} for q in ("mars", "moon", "sun")]}
            with mock.patch.object(visuals, "find_photo", side_effect=fake), \
                 mock.patch.object(visuals.quality, "check_image", return_value=(True, "")):
                out = visuals.illustrate(script, w, 0, {"real_images_only": True})
            self.assertEqual(len(out), 3)
            self.assertEqual(out[1], out[0])

    def test_rotation_is_a_real_earth_search(self):
        self.assertEqual(visuals.matching_photo("Earth's rotation makes a day.", None,
                         {"source": "nasa", "query": "sun"}, "T"),
                         {"source": "nasa", "query": "earth blue marble"})

    def test_impact_uses_real_earth_crater_not_a_generic_planet(self):
        self.assertEqual(visuals.matching_photo("An asteroid impact struck Earth.", None,
                         {"source": "nasa", "query": "earth"}, "T"),
                         {"source": "nasa", "query": "meteor crater"})

    def test_mission_plan_preserved_for_pronoun(self):
        plan = {"source": "nasa", "query": "Voyager antenna"}
        self.assertEqual(visuals.matching_photo("It is still talking to us.", "Voyager spacecraft", plan, "T"), plan)

    def test_real_photography_is_not_excluded_as_graph(self):
        self.assertIsNone(visuals.NASA_SKIP.search("Meteor Crater in Arizona Earth photography"))
        self.assertIsNotNone(visuals.NASA_SKIP.search("Artist illustration of an impact"))


if __name__ == "__main__":
    unittest.main()
