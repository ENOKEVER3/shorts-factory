import json, os, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = ("import json;from src import content,util;cfg=util.load_json(util.CONFIG);"
         "print(json.dumps({'ch':cfg['expected_channel_id'],'state':str(util.STATE_DIR),"
         "'ids':[s['id'] for s in content.allowed_scripts(cfg)]}))")


def probe(profile):
    env = {**os.environ, "SF_PROFILE": profile}
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class ProfileTest(unittest.TestCase):
    def test_uriel_channel_is_isolated(self):
        u = probe("uriel")
        self.assertEqual(u["ch"], "UC51tVC_mdH6q3oEp9Pzq9Pw")
        self.assertTrue(u["state"].endswith("channels/uriel/state"))
        self.assertTrue(u["ids"] and all(i.startswith("u-") for i in u["ids"]))

    def test_main_channel_unchanged(self):
        m = probe("")
        self.assertEqual(m["ch"], "UCA5IqyxUWCJxz-ibknXuZbA")
        self.assertFalse(any(i.startswith("u-") for i in m["ids"]))


if __name__ == "__main__":
    unittest.main()
