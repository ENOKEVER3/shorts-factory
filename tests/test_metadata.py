import unittest
from src.metadata import hashtags, tags, title, search_queries
from src.main import build_description


class HashtagTest(unittest.TestCase):
    def test_moon_has_no_unrelated_earth_or_ai_tags(self):
        s = {"title": "What if the Moon disappeared? #Shorts", "theme": "space"}
        self.assertEqual(title(s), "What would happen if the Moon disappeared?")
        self.assertIn("#Moon", hashtags(s))
        self.assertNotIn("AI", tags(s))
        self.assertNotIn("#PlanetEarth", hashtags(s))

    def test_lunar_eclipse_is_not_solar_energy(self):
        h = hashtags({"title": "Why a lunar eclipse turns red", "theme": "space"})
        self.assertIn("#LunarEclipse", h)
        self.assertNotIn("#SolarEnergy", h)
        self.assertNotIn("#SolarEclipse", h)

    def test_no_gaming_hashtags(self):
        h = hashtags({"title": "GTA 6 mods explained", "theme": "curiosity"})
        self.assertNotIn("#GTA6", h)
        self.assertNotIn("#Gaming", h)
    def test_protein_topic_not_generic_ai(self):
        result = hashtags({"title": "Can a protein carry a watermark?", "theme": "biology"})
        self.assertEqual(result, ["#ProteinScience", "#Biology", "#Shorts", "#MAKOKOGW"])

    def test_title_precedes_secondary_narration_topics(self):
        result = hashtags({"title": "Why catching a rocket is so hard", "theme": "future-tech",
                           "sentences": ["AI and robots help protect Earth."]})
        self.assertEqual(result[0], "#RocketScience")
        self.assertLessEqual(len(result), 5)
        self.assertEqual(len(result), len(set(result)))

    def test_stale_and_unrelated_hashtags_are_removed(self):
        result = hashtags({"title": "What if Earth had rings?", "theme": "planet",
                           "hashtags": ["#Seunenoch", "#Viral", "#AI"]})
        self.assertEqual(result, ["#PlanetEarth", "#EarthScience", "#Shorts", "#MAKOKOGW"])

    def test_description_preserves_photo_credits(self):
        script = {"title": "How fusion works", "sentences": ["Atoms combine."],
                  "theme": "future-tech", "_credits": ["NASA"]}
        description = build_description(script, {"description_footer": "Original narration."})
        self.assertIn("Photo credits:\n- NASA", description)
        self.assertTrue(description.endswith("#FusionEnergy #FutureTechnology #Shorts #MAKOKOGW"))

class SearchPhrasingTest(unittest.TestCase):
    def test_what_if_becomes_search_phrasing(self):
        s = {"title": "What if Earth stopped spinning?", "theme": "planet"}
        self.assertEqual(title(s), "What would happen if Earth stopped spinning?")
        self.assertIn("what happens if earth stopped spinning", tags(s))

    def test_why_title_gets_why_query_tags(self):
        q = search_queries({"title": "Why space is freezing if the Sun is so hot"})
        self.assertEqual(q[0], "why space is freezing if the sun is so hot")
        self.assertIn("space is freezing if the sun is so hot explained", q)

    def test_explicit_search_title_wins(self):
        self.assertEqual(title({"title": "Point Nemo", "search_title": "Why spacecraft go to die at Point Nemo"}),
                         "Why spacecraft go to die at Point Nemo")
