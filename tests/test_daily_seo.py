import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from src import trends, metadata, channel


class DailySEOTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 7, tzinfo=timezone.utc)
        self.data = {'checked_at': self.now.isoformat(), 'queries': ['Point Nemo', 'Alcatraz', 'GTA 6', 'thanksgiving']}

    def test_only_actual_title_subject_can_match(self):
        s = {'title': 'Why spacecraft go to die at Point Nemo', 'sentences': ['Thanksgiving is unrelated.']}
        self.assertEqual(trends.matches(s, self.data, self.now), [{'query': 'Point Nemo', 'hashtag': '#PointNemo'}])

    def test_unrelated_trends_are_not_added(self):
        self.assertEqual(trends.matches({'title': 'Why the Moon turns red'}, self.data, self.now), [])

    def test_expired_trends_are_not_used(self):
        self.assertEqual(trends.matches({'title': 'Point Nemo'}, self.data, self.now + timedelta(hours=25)), [])

    def test_gaming_is_excluded_even_if_trending(self):
        self.assertEqual(trends.matches({'title': 'GTA 6 explained'}, self.data, self.now), [])

    def test_missing_feed_keeps_evergreen_metadata(self):
        with patch.object(trends.FILE.__class__, 'read_text', side_effect=OSError):
            self.assertEqual(trends.matches({'title': 'Point Nemo'}), [])
            self.assertIn('#Moon', metadata.hashtags({'title': 'Why the Moon turns red', 'theme': 'space'}))

    def test_trend_keeps_hashtags_and_keyword_budget_bounded(self):
        s = {'title': 'Why spacecraft go to die at Point Nemo', 'theme': 'space', 'tags': [f'tag {i}' for i in range(100)]}
        with patch('src.trends.matches', return_value=[{'query': 'Point Nemo', 'hashtag': '#PointNemo'}]):
            self.assertIn('#PointNemo', metadata.hashtags(s))
            self.assertLessEqual(len(metadata.hashtags(s)), 5)
            self.assertLessEqual(len(metadata.tags(s)), 30)
            self.assertLessEqual(sum(len(t) + 3 for t in metadata.tags(s)), 500)

    def test_daily_checks_all_but_caps_changes(self):
        videos = [{'id': str(i), 'title': 'old', 'description': '', 'tags': [],
                   'suggested': {'id': str(i), 'title': 'new', 'description': '', 'tags': []}} for i in range(87)]
        edits, report = channel.daily_changes(videos)
        self.assertEqual(report['reviewed'], 87)
        self.assertEqual(len(edits), 20)
        self.assertEqual(report['deferred'], 67)

    def test_unchanged_videos_do_not_use_update_quota(self):
        edit = {'id': 'abc', 'title': 'title', 'description': '', 'tags': []}
        edits, report = channel.daily_changes([dict(edit, suggested=edit)])
        self.assertEqual(edits, [])
        self.assertEqual(report['reviewed'], 1)

    def test_uriel_keeps_separate_brand(self):
        with patch.dict('os.environ', {'SF_PROFILE': 'uriel'}), patch('src.trends.matches', return_value=[]):
            h = metadata.hashtags({'title': 'How three men escaped Alcatraz', 'theme': 'escape'})
            self.assertIn('#Uriel', h)
            self.assertNotIn('#MAKOKOGW', h)

    def test_unmapped_video_preserves_credits_and_narration(self):
        v = {'id': 'abcdef12345', 'title': 'Why spacecraft go to Point Nemo',
             'description': 'Original story.\nPhoto credits:\n- NASA\n\n#Shorts', 'tags': []}
        with patch('src.trends.matches', return_value=[]):
            edit = channel.suggestion(v, {}, {})
        self.assertIn('Original story.\nPhoto credits:\n- NASA', edit['description'])


if __name__ == '__main__':
    unittest.main()