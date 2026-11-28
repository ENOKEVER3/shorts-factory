"""The regeneration follow-up is eligible only for the science channel."""
import json
import unittest
from pathlib import Path

from src.content import _valid
from src import visuals
from tests.test_profiles import probe


class OctopusStory(unittest.TestCase):
    def test_story_is_eligible_for_makokogw_not_uriel(self):
        story_id = "bio-octopus-regeneration"
        self.assertIn(story_id, probe("")["ids"])
        self.assertNotIn(story_id, probe("uriel")["ids"])

    def test_every_sentence_has_a_resolvable_real_photo_plan(self):
        root = Path(__file__).resolve().parent.parent
        story = json.loads((root / "content/generated/bio-octopus-regeneration.json").read_text())
        self.assertTrue(_valid(story))
        self.assertEqual(story["theme"], "biology")
        self.assertEqual(len(story["photos"]), 7)
        self.assertEqual(len(story["photos"]), len(story["sentences"]))
        for sentence, visual, photo in zip(story["sentences"], story["visuals"], story["photos"]):
            self.assertIsNotNone(visuals.matching_photo(sentence, visual, photo, story["title"]))


if __name__ == "__main__":
    unittest.main()
