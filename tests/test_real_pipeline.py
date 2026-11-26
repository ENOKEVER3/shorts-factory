"""Opt-in live benchmark: SF_RUN_BENCHMARK=1 python -m unittest tests.test_real_pipeline.

Requires cached Kokoro/Whisper and Mesa EGL. No credentials, uploads, AI image APIs or mocks.
"""
import json
import os
import unittest

from src import main, quality
from src.util import CONFIG, load_json


@unittest.skipUnless(os.environ.get("SF_RUN_BENCHMARK") == "1", "opt-in live photo + narration benchmark")
class RealPipeline(unittest.TestCase):
    def test_complete_real_short_under_120_seconds(self):
        script = {
            "id": "benchmark-earth-globe", "title": "Why Earth keeps spinning beneath our satellites",
            "theme": "space",
            "sentences": [
                "Earth's rotation turns night into day as sunlight reaches each continent.",
                "Earth spins on an axis tilted by about twenty three degrees.",
                "Satellites orbit Earth while the planet keeps turning beneath them.",
                "An asteroid impact can leave a huge crater on Earth's surface.",
                "Earth's rotation carries that crater around with everything else on the planet.",
                "Earth's axis stays tilted as the world turns, changing which hemisphere receives more sunlight.",
                "Satellites orbit Earth at different heights depending on their jobs, from weather observations to communications.",
                "That meteor crater is a scar from the past, preserved in Arizona's dry landscape.",
                "Earth is always moving, even when the ground beneath your feet seems completely still.",
            ],
            "photos": [{"source": "nasa", "query": q} for q in
                       ["earth blue marble", "earth blue marble", "earth satellite", "meteor crater", "earth blue marble",
                        "earth blue marble", "earth satellite", "meteor crater", "earth blue marble"]],
        }
        cfg = load_json(CONFIG)
        video = main.produce(script, 0, cfg)
        report = quality.inspect_video(video, cfg)
        print(json.dumps({"production_seconds": script["_production_seconds"],
                          "photo_seconds": script["_photo_seconds"], "quality": report,
                          "sources": script["_sources"]}, indent=2))
        self.assertLess(script["_production_seconds"], 120)
        self.assertTrue(report["passed"], report)
        self.assertTrue(any("NASA 3D Earth model" in source for source in script["_sources"]))
        self.assertTrue(any("NASA 3D Earth model (orbit" in source for source in script["_sources"]))
        self.assertTrue(all("card" not in source and "AI" not in source for source in script["_sources"]))