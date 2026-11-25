import unittest
from pathlib import Path
from unittest.mock import Mock, patch
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

    def test_every_post_render_upload_uses_a_fresh_connection(self):
        fresh = Mock()
        path = Path("rendered.mp4")
        cfg = {"expected_channel_id": TARGET}
        with patch.object(youtube, "client", return_value=fresh) as client, \
                patch.object(youtube, "upload", return_value="video123") as upload:
            result = youtube.upload_after_render(path, "Title", "Description", ["space"], cfg)
        self.assertEqual(result, "video123")
        client.assert_called_once_with()
        upload.assert_called_once_with(fresh, path, "Title", "Description", ["space"], cfg)
