import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from src import trajectories


class Trajectories(unittest.TestCase):
    def test_kind_matching(self):
        self.assertEqual(trajectories.kind_for("Voyager used a gravity assist from Jupiter"), "transfer")
        self.assertEqual(trajectories.kind_for("The ISS orbits Earth every 90 minutes"), "orbit")
        self.assertEqual(trajectories.kind_for("Earth spins on a tilted axis"), "rotation")
        self.assertIsNone(trajectories.kind_for("Bank robbers dug a tunnel"))

    def test_disabled_for_other_channels(self):
        segs = [("a.jpg", 0, 3)]
        self.assertEqual(trajectories.animate({"theme": "crime", "sentences": ["orbit"]}, ["a.jpg"], segs, Path("."),
                                              {"orbital_animations": {"enabled": True}}), segs)
        self.assertEqual(trajectories.animate({"theme": "space", "sentences": ["orbit"]}, ["a.jpg"], segs, Path("."), {}), segs)

    def test_clip_renders_fast(self):
        with tempfile.TemporaryDirectory() as d:
            start = time.time()
            out = trajectories.render_clip("orbit", 1.0, Path(d) / "o.mp4")
            self.assertTrue(out.exists())
            self.assertLess(time.time() - start, 15)

    def test_mars_rotation_never_uses_earth_model(self):
        segs = [("mars.jpg", 0, 3)]
        with mock.patch.object(trajectories, "render_clip") as render:
            out = trajectories.animate({"theme": "space", "sentences": ["Mars spins on its axis."]},
                                       ["mars.jpg"], segs, Path("."),
                                       {"orbital_animations": {"enabled": True}})
            self.assertEqual(out, segs)
            render.assert_not_called()

    def test_earth_rotation_uses_nasa_model(self):
        script = {"theme": "space", "sentences": ["Earth spins on its axis."], "_sources": ["photo"]}
        with mock.patch.object(trajectories, "render_clip", return_value=Path("earth.mp4")) as render:
            out = trajectories.animate(script, ["earth.jpg"], [("earth.jpg", 0, 3)], Path("."),
                                       {"orbital_animations": {"enabled": True}})
            self.assertEqual(out[0][0], Path("earth.mp4"))
            render.assert_called_once()
            self.assertIn("NASA 3D Earth model", script["_sources"][0])


if __name__ == "__main__":
    unittest.main()
