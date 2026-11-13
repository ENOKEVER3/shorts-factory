import unittest
from unittest.mock import Mock
from src import youtube

TARGET = "UCA5IqyxUWCJxz-ibknXuZbA"

class ChannelGuardTest(unittest.TestCase):
    def client(self, channel_id):
        yt = Mock()
        yt.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": channel_id, "snippet": {"title": "New channel"}}]}
        return yt

    def test_new_channel_is_allowed(self):
        self.assertEqual(youtube.verify_channel(self.client(TARGET), TARGET), "New channel")

    def test_previous_channel_is_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "Posting blocked"):
            youtube.verify_channel(self.client("previous-channel"), TARGET)

    def test_missing_target_is_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "expected_channel_id"):
            youtube.verify_channel(self.client(TARGET), "")