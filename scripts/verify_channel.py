"""Verify fresh OAuth without rendering or uploading a video."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import youtube
from src.util import ROOT, load_json
cfg = load_json(ROOT / 'config.json')
yt = youtube.client()
items = yt.channels().list(part='snippet', mine=True).execute().get('items', [])
if len(items) != 1 or items[0].get('id') != cfg.get('expected_channel_id'):
    raise SystemExit('Wrong channel authorized. Do not enable the workflow. Replace YT_REFRESH_TOKEN.')
print('Verified channel:', items[0]['snippet']['title'])
print('Channel ID:', items[0]['id'])
