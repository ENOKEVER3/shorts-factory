"""Verify OAuth destination without uploading."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import youtube
from src.util import ROOT, load_json
cfg = load_json(ROOT / "config.json")
print("Verified channel:", youtube.verify_channel(youtube.client(), cfg.get("expected_channel_id", "")))
