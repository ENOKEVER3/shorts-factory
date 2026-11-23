"""Rolling 30-day, two-slot plan shared by preparation and the private workspace."""
from datetime import datetime, timedelta, timezone
from . import content
from .util import BASE, PROFILE, ROOT, load_json, save_json

PLAN = BASE / ('plan.json' if PROFILE else 'content/monthly-plan.json')

def build(cfg, posts, queued, now=None, previous=None):
    now = now or datetime.now(timezone.utc)
    today = (now - timedelta(hours=cfg.get('day_rollover_hour_utc', 0))).date()
    bank = {s['id']: s for s in content.allowed_scripts(cfg)}
    used = {p['script_id'] for p in posts}
    order = [q['script_id'] for q in queued]
    order += [r['script_id'] for r in (previous or {}).get('items', [])]
    order += list(bank)
    pending = []
    seen = set(used)
    for sid in order:
        if sid not in seen and sid in bank:
            pending.append(bank[sid]); seen.add(sid)
    rows = []
    last = bank.get(posts[-1]['script_id'], {}).get('theme') if posts else None
    queued_ids = {q['script_id'] for q in queued}
    for day in range(30):
        date = (today + timedelta(days=day)).isoformat()
        for slot in cfg['slots_utc'][:cfg['max_posts_per_day']]:
            posted = next((p for p in posts if p.get('date') == date and p.get('slot') == slot['name']), None)
            if posted:
                s = bank.get(posted['script_id'])
                if not s: continue
            else:
                if not pending: continue
                # Keep already-rendered videos first; alternate themes for new renders.
                index = 0 if pending[0]['id'] in queued_ids else next((i for i,s in enumerate(pending) if s.get('theme') != last), 0)
                s = pending.pop(index)
            last = s.get('theme')
            rows.append({'date': date, 'slot': slot['name'], 'hour_utc': slot['start_hour'],
                         'script_id': s['id'], 'title': s['title'], 'theme': s.get('theme', 'curiosity'),
                         'ending': s['sentences'][-1],
                         'ending_type': 'question' if s['sentences'][-1].rstrip().endswith('?') else 'payoff',
                         'status': 'published' if posted else ('ready' if s['id'] in queued_ids else 'planned')})
    return {'generated_at': now.isoformat(), 'start_date': today.isoformat(),
            'end_date': (today + timedelta(days=29)).isoformat(), 'items': rows}

def refresh(cfg, posts, queued, now=None):
    result = build(cfg, posts, queued, now, load_json(PLAN, {}))
    save_json(PLAN, result)
    return result

def next_script(plan, cfg, excluded):
    bank = {s['id']: s for s in content.allowed_scripts(cfg)}
    return next((dict(bank[r['script_id']]) for r in plan['items']
                 if r['script_id'] not in excluded and r['script_id'] in bank), None)