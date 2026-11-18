import os
import unittest
from unittest import mock

from src import providers

CFG_OFF = {"providers": {"enabled_paid": [], "daily_limit_usd": 0, "monthly_limit_usd": 0, "max_paid_calls_per_video": 0}}
CFG_ON = {"providers": {"enabled_paid": ["elevenlabs"], "daily_limit_usd": 1, "monthly_limit_usd": 5, "max_paid_calls_per_video": 1}}


class ProviderRules(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(providers, "_ledger", return_value={"calls": []}); p.start(); self.addCleanup(p.stop)
        s = mock.patch.object(providers, "save_json"); s.start(); self.addCleanup(s.stop)

    def test_paid_never_called_when_not_enabled(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "x"}):
            self.assertFalse(providers.Budget(CFG_OFF, "t").allow("elevenlabs"))

    def test_paid_needs_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(providers.Budget(CFG_ON, "t").allow("elevenlabs"))

    def test_per_video_limit(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "x"}):
            b = providers.Budget(CFG_ON, "t")
            self.assertTrue(b.allow("elevenlabs"))
            b.record("elevenlabs")
            self.assertFalse(b.allow("elevenlabs"))

    def test_daily_limit(self):
        led = {"calls": [{"at": providers.datetime.now(providers.timezone.utc).isoformat(), "cost": 0.99}]}
        with mock.patch.object(providers, "_ledger", return_value=led), mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "x"}):
            self.assertFalse(providers.Budget(CFG_ON, "t").allow("elevenlabs"))

    def test_video_slots_without_adapter_are_unavailable(self):
        with mock.patch.dict(os.environ, {"KLING_API_KEY": "x", "VEO_API_KEY": "x"}):
            self.assertEqual(providers.status("kling", CFG_ON), "unavailable")
            self.assertEqual(providers.status("veo", CFG_ON), "unavailable")

    def test_free_always_allowed(self):
        self.assertTrue(providers.Budget(CFG_OFF, "t").allow("edge_tts"))


if __name__ == "__main__":
    unittest.main()
