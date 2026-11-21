"""Private Actions snapshot and channel-verified metadata updates. Never commits analytics."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timedelta, timezone
from . import content, metadata, youtube
from .util import ROOT, load_json, save_json


def validate_edit(e):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', e.get('id', '')): raise ValueError('Invalid video ID')
    t, d, tags = e.get('title', '').strip(), e.get('description', ''), e.get('tags', [])
    if not t or len(t) > 100 or '<' in t or '>' in t: raise ValueError('Title must be 1–100 characters without angle brackets')
    if len(d) > 4900 or '<' in d or '>' in d: raise ValueError('Description limit is 4900 characters without angle brackets')
    if not isinstance(tags, list) or len(tags) > 30 or any(not isinstance(x, str) or not x.strip() for x in tags): raise ValueError('Use at most 30 nonempty tags')
    if sum(len(x) + (2 if ' ' in x else 0) for x in tags) + max(0, len(tags)-1) > 500: raise ValueError('Tags exceed 500 characters')
    return {'id': e['id'], 'title': t, 'description': d, 'tags': tags}


def update_video(yt, cfg, edit):
    youtube.verify_channel(yt, cfg['expected_channel_id'])
    e = validate_edit(edit)
    items = yt.videos().list(part='snippet', id=e['id']).execute().get('items', [])
    if not items or items[0]['snippet']['channelId'] != cfg['expected_channel_id']: raise ValueError('Video belongs to another channel')
    old = items[0]['snippet']
    snippet = {k: old[k] for k in ('categoryId', 'defaultLanguage', 'defaultAudioLanguage') if k in old}
    snippet.update({k: e[k] for k in ('title', 'description', 'tags')})
    yt.videos().update(part='snippet', body={'id': e['id'], 'snippet': snippet}).execute()
    fresh = yt.videos().list(part='snippet', id=e['id']).execute()['items'][0]['snippet']
    if fresh['title'] != e['title'] or fresh.get('description', '') != e['description']: raise RuntimeError('Read-back mismatch')
    return {'id': e['id'], 'before': old, 'after': fresh}


def suggestion(v, bank, cfg):
    s = bank.get(v.get('script_id'))
    if not s: return {'id': v['id'], 'title': metadata.title(v), 'description': v['description'], 'tags': v['tags']}
    s = dict(s)
    if 'Photo credits:' in v['description']:
        s['_credits'] = [x.strip('- ').strip() for x in v['description'].split('Photo credits:', 1)[1].split('\n') if x.startswith('- ')]
    return {'id': v['id'], 'title': metadata.title(s), 'description': metadata.description(s, cfg), 'tags': metadata.tags(s)}


def snapshot(yt, cfg):
    c = yt.channels().list(part='snippet,contentDetails', mine=True).execute()['items'][0]
    posts = {p['video_id']: p for p in load_json(ROOT/'state/posted.json', {'posts': []})['posts']}
    ids, token = [], None
    while True:
        p = yt.playlistItems().list(part='contentDetails', playlistId=c['contentDetails']['relatedPlaylists']['uploads'], maxResults=50, **({'pageToken': token} if token else {})).execute()
        ids.extend(x['contentDetails']['videoId'] for x in p.get('items', [])); token = p.get('nextPageToken')
        if not token: break
    videos = []
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part='snippet,statistics', id=','.join(ids[i:i+50])).execute().get('items', []):
            s = v['snippet']
            if v['id'] not in posts and '#shorts' not in s['title'].lower(): continue
            thumbs = s.get('thumbnails', {})
            thumb = next((thumbs[k]['url'] for k in ('maxres','standard','high','medium','default') if k in thumbs), '')
            videos.append({'id': v['id'], 'script_id': posts.get(v['id'],{}).get('script_id'), 'title': s['title'], 'description': s.get('description',''), 'tags': s.get('tags',[]), 'thumbnail': thumb, 'published_at': s['publishedAt'], 'views': int(v.get('statistics',{}).get('viewCount',0)), 'likes': int(v.get('statistics',{}).get('likeCount',0)), 'comments': int(v.get('statistics',{}).get('commentCount',0)), 'watch_minutes': None, 'average_view_seconds': None, 'analytics_views': None, 'swipe_away_rate': None})
    end = datetime.now(timezone.utc).date()-timedelta(days=2); start = end-timedelta(days=27); error = None
    try:
        from googleapiclient.discovery import build
        a = build('youtubeAnalytics','v2',credentials=yt._http.credentials,cache_discovery=False)
        result = a.reports().query(ids='channel==MINE',startDate=start.isoformat(),endDate=end.isoformat(),metrics='views,estimatedMinutesWatched,averageViewDuration',dimensions='video',maxResults=200,sort='-views').execute()
        rows = {r[0]:r for r in result.get('rows',[])}
        for v in videos:
            r = rows.get(v['id'])
            if r: v.update(analytics_views=r[1],watch_minutes=r[2],average_view_seconds=r[3])
    except Exception as exc:
        error = 'Enable YouTube Analytics API and authorize yt-analytics.readonly to see watch time.'
        print('Analytics request failed:',str(exc))
    bank = {s['id']:s for s in content.all_scripts()}
    for v in videos: v['suggested'] = suggestion(v,bank,cfg)
    return {'channel_id':c['id'],'channel_name':c['snippet']['title'],'synced_at':datetime.now(timezone.utc).isoformat(),'period_start':start.isoformat(),'period_end':end.isoformat(),'analytics_error':error,'swipe_note':'Swipe-away rate is not exposed by the YouTube Analytics API; use Viewed vs swiped away in YouTube Studio.','videos':videos,'queue':load_json(ROOT/'state/queue.json',{'items':[]})}


def main():
    cfg = load_json(ROOT/'config.json'); yt = youtube.client(); youtube.verify_channel(yt,cfg['expected_channel_id'])
    mode = os.environ.get('CHANNEL_MODE','sync'); snap = snapshot(yt,cfg); report = {'updated':[],'errors':[]}
    if mode in ('apply','optimize'):
        edits = json.loads(os.environ.get('VIDEO_EDITS','[]')) if mode == 'apply' else [v['suggested'] for v in snap['videos']]
        save_json(ROOT/'out/channel-backup.json',snap)
        for e in edits:
            try: report['updated'].append(update_video(yt,cfg,e)['id'])
            except Exception as exc:
                report['errors'].append({'id':e.get('id'),'error':str(exc)}); print('Metadata update failed:',str(exc))
                if 'insufficient' in str(exc).lower():
                    report['errors'].extend({'id':pending.get('id'),'error':'Not attempted: YouTube authorization lacks video editing permission.'} for pending in edits[len(report['updated'])+len(report['errors']):])
                    break
        snap = snapshot(yt,cfg)
    snap['update_report'] = report; save_json(ROOT/'out/channel.json',snap)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write(f"## Channel sync\n{len(snap['videos'])} Shorts synced. {len(report['updated'])} updated; {len(report['errors'])} failed.\n")
            if snap['analytics_error']: f.write(snap['analytics_error']+'\n')
            f.write(snap['swipe_note']+'\n')
    if report['errors']: raise RuntimeError('Metadata updates failed; see channel artifact')

if __name__ == '__main__': main()
