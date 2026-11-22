import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from src import plan, subscribers

class MonthlyPlanTest(unittest.TestCase):
    def setUp(self):
        self.cfg = {'slots_utc': [{'name':'afternoon','start_hour':16},{'name':'evening','start_hour':21}], 'max_posts_per_day':2}
        self.bank = [{'id':str(i),'title':f'Story {i}','theme':'curiosity' if i%2 == 0 else 'space','sentences':['Hook',f'Payoff {i}.']} for i in range(80)]
        self.now = datetime(2026,11,22,14,tzinfo=timezone.utc)
    def build(self, posts=None, queued=None):
        with patch('src.plan.content.allowed_scripts',return_value=self.bank):
            return plan.build(self.cfg,posts or [],queued or [],self.now)
    def test_thirty_days_two_distinct_shorts_daily(self):
        p = self.build()
        self.assertEqual(len(p['items']),60)
        self.assertEqual(p['start_date'],'2026-11-22')
        self.assertEqual(p['end_date'],'2026-12-21')
        self.assertEqual(len({r['script_id'] for r in p['items']}),60)
        self.assertEqual(len([r for r in p['items'] if r['date']=='2026-11-22']),2)
    def test_ending_is_actual_narration_ending(self):
        self.assertEqual(self.build()['items'][0]['ending'],'Payoff 0.')
    def test_ready_first_and_used_not_repeated(self):
        p = self.build([{'script_id':'0','date':'2026-11-21','slot':'evening'}],[{'script_id':'5'}])
        self.assertEqual(p['items'][0]['script_id'],'5')
        self.assertEqual(p['items'][0]['status'],'ready')
        self.assertNotIn('0',[r['script_id'] for r in p['items']])
    def test_prepare_selects_exact_next_planned_script(self):
        p = self.build()
        with patch('src.plan.content.allowed_scripts',return_value=self.bank):
            s = plan.next_script(p,self.cfg,{'0'})
        self.assertEqual(s['id'],p['items'][1]['script_id'])

class SubscriberTest(unittest.TestCase):
    def test_live_count_is_not_defaulted_to_zero(self):
        self.assertEqual(subscribers.count({'subscriberCount':'23'}),23)
        self.assertIsNone(subscribers.count({}))
        self.assertIsNone(subscribers.count({'subscriberCount':'23','hiddenSubscriberCount':True}))
    def test_history_persists_across_days(self):
        h = subscribers.record({},'channel',23,'2026-11-22T14:00:00Z')
        h = subscribers.record(h,'channel',24,'2026-11-23T14:00:00Z')
        self.assertEqual([p['count'] for p in h['points']],[23,24])
    def test_same_day_refresh_replaces_observation(self):
        h = subscribers.record({},'channel',23,'2026-11-22T14:00:00Z')
        h = subscribers.record(h,'channel',25,'2026-11-22T15:00:00Z')
        self.assertEqual(len(h['points']),1)
        self.assertEqual(h['points'][0]['count'],25)
    def test_wrong_channel_history_rejected(self):
        with self.assertRaises(ValueError): subscribers.record({'channel_id':'wrong'},'channel',1,'2026-11-22T14:00:00Z')