"""Free Google Search trend signals; not YouTube rankings or guaranteed reach."""
from datetime import datetime, timezone, timedelta
import json
import re
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from .util import ROOT, save_json

FILE = ROOT / 'out/daily-trends.json'
REGIONS = ('US', 'GB', 'CA')


def refresh():
    queries, sources, errors = [], [], []
    for region in REGIONS:
        url = f'https://trends.google.com/trending/rss?geo={region}'
        try:
            with urlopen(Request(url, headers={'User-Agent': 'ShortsFactory/1.0'}), timeout=12) as response:
                root = ET.fromstring(response.read(1_000_000))
            for item in root.findall('.//item')[:100]:
                query = (item.findtext('title') or '').strip()
                if query and query.casefold() not in {q.casefold() for q in queries}:
                    queries.append(query)
            sources.append(url)
        except Exception as exc:
            errors.append({'region': region, 'error': type(exc).__name__})
    data = {'checked_at': datetime.now(timezone.utc).isoformat(), 'queries': queries,
            'sources': sources, 'errors': errors, 'signal': 'Google Search, not YouTube search volume'}
    save_json(FILE, data)
    print(f'Trend check: {len(queries)} queries; {len(errors)} unavailable feeds. Only exact subject matches are used.')
    return data


def matches(script, data=None, now=None):
    """Require the entire trend phrase in the title; never infer a trending claim."""
    if data is None:
        try:
            data = json.loads(FILE.read_text())
        except (OSError, ValueError):
            return []
    now = now or datetime.now(timezone.utc)
    try:
        checked = datetime.fromisoformat(data['checked_at'])
        if checked.tzinfo is None or not timedelta(0) <= now - checked <= timedelta(hours=24):
            return []
    except (KeyError, TypeError, ValueError):
        return []
    subject = re.sub(r'#\w+', '', script.get('search_title') or script.get('title', '')).casefold()
    result = []
    for query in data.get('queries', []):
        if not isinstance(query, str):
            continue
        words = re.findall(r'[a-z0-9]+', query.casefold())
        if not words or (len(words) == 1 and words[0] not in {'nasa', 'chatgpt', 'openai', 'alcatraz', 'voyager'}):
            continue
        if any(w in {'gta', 'gaming', 'minecraft', 'fortnite'} for w in words):
            continue
        if re.search(r'\b' + r'\s+'.join(map(re.escape, words)) + r'\b', subject):
            tag = '#' + ''.join(w.upper() if w == 'nasa' else w.capitalize() for w in words)
            if len(tag) <= 40 and tag not in [r['hashtag'] for r in result]:
                result.append({'query': query, 'hashtag': tag})
    return result[:1]


if __name__ == '__main__':
    refresh()