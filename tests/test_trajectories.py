import tempfile
import time
import unittest
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


if __name__ == "__main__":
    unittest.main()
