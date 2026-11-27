import unittest
from src import photo_plan, visuals


class PhotoPlan(unittest.TestCase):
    def test_limb_story_without_stored_plans_gets_real_searches(self):
        s = {"title": "Can humans regrow a whole limb?",
             "sentences": ["Why can your body repair a cut but not regrow a missing arm?",
                           "Regenerative medicine is promising."]}
        photo_plan.ensure(s)
        self.assertEqual(s["photos"], [
            {"source": "pexels", "query": "human hand"},
            {"source": "pexels", "query": "medical laboratory"}])

    def test_explicit_mission_plan_and_earth_rotation_preserved(self):
        s = {"title": "Space", "sentences": ["It is still talking to us.", "Earth spins."],
             "photos": [{"source": "nasa", "query": "Voyager antenna"}]}
        photo_plan.ensure(s)
        self.assertEqual(s["photos"], [{"source": "nasa", "query": "Voyager antenna"},
                                     {"source": "nasa", "query": "earth blue marble"}])

    def test_every_active_script_and_long_video_has_searchable_scenes(self):
        from src import content
        from src.util import CONFIG, ROOT, load_json
        scripts = content.allowed_scripts(load_json(CONFIG)) + load_json(ROOT / "content" / "longform.json")
        self.assertGreater(len(scripts), 150)
        for original in scripts:
            s = dict(original)
            photo_plan.ensure(s)
            self.assertEqual(len(s["photos"]), len(s["sentences"]))
            for sentence, photo in zip(s["sentences"], s["photos"]):
                self.assertIsNotNone(visuals.matching_photo(sentence, None, photo, s["title"]))
                self.assertTrue(photo["query"].strip())