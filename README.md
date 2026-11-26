# Shorts Factory: automatic Shorts on AI, the planet, biology and future tech

Makes and publishes **2 original YouTube Shorts a day for 30 days** using only free tools.
After setup it runs on GitHub's servers. Your computer can stay off.

```
GitHub Actions (15 short check-ins/day, UTC; 2 of them post)
   -> pick next script (112 pre-written on 4 subjects - AI in technology, the planet, biology, future technology -
      rotated so two Shorts in a row are never the same subject; optional Gemini free tier after that)
   -> Kokoro voice (free/offline), falling back to edge-tts and Piper
   -> animated background (ffmpeg, 5 styles x 6 palettes, nothing downloaded)
   -> one picture per sentence that matches what is said: studio scenes if uploaded, else a real free photo
      (NASA for space/planets), else a Gemini image (only if your Google project has billing), else a free
      stock photo (Pexels/Pixabay key) or free AI illustration - all drawn from a written scene plan
   -> big word-by-word captions + title + progress bar + soft music bed
      (Whisper word timing, with sentence timing if transcription fails)
   -> YouTube Data API upload (resumable, retries)
   -> log the video in state/posted.json (so nothing is ever posted twice)
```

---

## 1. Honest limits (read this first)

| Thing | Free limit | What it means for you |
|---|---|---|
| **YouTube API "unverified app" lock** | Apps created after July 2020 that have not passed Google's free API audit have every uploaded video **locked to Private**. | **This is the big one.** Until Google approves your audit (step 6), uploads work but nobody else can see them. Approval usually takes days to a few weeks and is not guaranteed. |
| YouTube API quota | 10,000 units/day. One upload = 1,600 units (+1 for the channel check). | Max ~6 uploads/day. This system uses 2 (about 3,200 units). |
| Unverified-channel upload cap | Channels that aren't phone-verified have lower daily upload limits. | Verify your channel by phone at youtube.com/verify. |
| OAuth refresh token | Expires after **7 days** if the Google app is left in "Testing". | You **must** switch it to "In production" (step 3). Then it lasts until you revoke it, change your password, or leave it unused for 6 months. |
| GitHub Actions minutes | Public repo: standard hosted runners have no minute charge. Private repo: free account allowance is 2,000 min/month. | Rendering, Kokoro/Whisper model downloads and CPU inference vary substantially. Private repositories can exceed the allowance; inspect actual usage rather than assuming the campaign fits. |
| GitHub scheduled runs | Can start 5-60+ min late at busy times, and are sometimes skipped entirely. Turned off after 60 days without repo activity. | Every window has several runs, and a later run catches up on a missed Short. Each post commits to the repo, so it stays active. |
| edge-tts voice | Free, no key, but an **unofficial** Microsoft endpoint. It can break or be blocked without warning. | The system automatically falls back to Piper, a free offline voice. It sounds a bit less natural. |
| Gemini API (`GEMINI_API_KEY`) | **Text** (scene plans, new scripts): free tier with per-minute and per-day limits that Google changes often; it sometimes answers "high demand, try later". **Images**: Google's free tier currently allows **0** images - you need billing on the Google Cloud project (paid per image, a few US cents each, check Google's pricing page). Older model names such as `gemini-2.5-flash` are no longer available to new keys, so the config uses `gemini-3.5-flash`. | One plan request per video is far below the free text limits. Without billing, the pipeline tries one Gemini image, sees there is no quota, and switches to the free picture sources for the rest of the video, so nothing breaks and nothing is charged. Set `"gemini_images": false` in config.json to skip even that one try. |
| Pollinations.ai images | Free, no key, **1 image every 45 s**; availability is not guaranteed. | MAKOKOGW's real-only mode bypasses AI image services and drawn cards entirely. Other profiles retain their existing fallback behavior. No matching real photo means preparation is held, never silently replaced by an unrelated or drawn scene. |
| Matching pictures | Every built-in script can carry a written scene plan per sentence (what to show + a photo search). Space sentences use real NASA photos (public domain, no key). Optional free `PEXELS_API_KEY` / `UNSPLASH_ACCESS_KEY` / `PIXABAY_API_KEY` secrets add real stock photos for everyday things. Optional free `GEMINI_API_KEY` writes the plan at run time for scripts that don't have one yet. | Without a plan, the AI picture is drawn from the sentence text, which matches less well. Photo credits are added to each video description. Google Images and Shutterstock pictures are **not** used: they are copyrighted or paid and can get the channel struck. |
| Illustration Studio scenes (optional) | Made on the guide site with Lovable AI; uses workspace credits, not free-tier. | Best-looking option. Generate one scene per sentence on the site's Illustration Studio page, download the ZIP, and upload the images to `content/scenes/<script_id>/` (named `scene_01.png`, `scene_02.png`, ...). The pipeline uses them as-is and skips the online/local fallbacks for those sentences. |
| Artifacts | Rendered videos are kept for 7 days. | Download any video from the run page if you want a copy. |

**Money reality check.** To earn ad money from Shorts you need the YouTube Partner Program: 1,000 subscribers plus
10 million Shorts views in 90 days. Shorts pay far less per view than long videos, often cents per 1,000 views.
YouTube also demonetises "inauthentic" content (mass-produced, repetitive videos). That's why every script here is
unique and every video is labelled as AI-narrated. Growth is not guaranteed. Watch the analytics when you're back.

**Why this doesn't re-upload other people's videos.** Clipping and reposting other channels' content gets copyright
strikes (3 strikes = channel deleted) and is never monetised. This system only makes original videos.

---

## 2. Put the code on GitHub (5 min)

1. Create a free account at github.com.
2. Click **New repository** and name it `shorts-factory`. Choose **Public** (unlimited minutes; your secrets stay hidden either way) or Private.
3. On the empty repo page, click **uploading an existing file**. Drag in **everything inside** this folder, including the
   hidden `.github` folder. On Mac press `Cmd+Shift+.` in Finder to see it. Then click **Commit**.
   - Or with git: `git init && git add . && git commit -m init && git branch -M main && git remote add origin https://github.com/YOU/shorts-factory.git && git push -u origin main`
4. Check that `.github/workflows/shorts.yml` appears in the repo.

## 3. Create the Google app (10 min)

1. Go to **console.cloud.google.com**, sign in with the Google account that owns the YouTube channel, and create a project called `shorts-factory`.
2. **APIs & Services -> Library**: search **YouTube Data API v3**, then click **Enable**.
3. **Google Auth Platform** (formerly "OAuth consent screen"):
   - **Branding**: app name `Shorts Factory`, plus your email for support and developer contact.
   - **Audience**: User type **External**. Then click **Publish app** so the status says **In production**.
     (In "Testing", your token dies after 7 days.) Google will say the app is "unverified". That's fine for personal use.
   - **Data Access**: add the scopes `.../auth/youtube.upload` and `.../auth/youtube.readonly`.
4. **Clients -> Create client -> Application type: Desktop app**. Click **Download JSON** and save it as `client_secret.json`.
   **Never upload this file to GitHub.**

## 4. Get your refresh token (once, on your computer)

### Switching away from a compromised channel

Keep the workflow disabled until fresh authorization is verified. The configured target is
`UCA5IqyxUWCJxz-ibknXuZbA`. A channel URL alone cannot authorize uploads.
Secure the Google account first: change its password, remove unknown sessions/apps and enable two-step verification.
Run the helper below while signed into the new channel's owner account. It refuses to print credentials for
the wrong channel. Replace `YT_REFRESH_TOKEN` in GitHub Secrets; if using a new Google OAuth app, replace
`YT_CLIENT_ID` and `YT_CLIENT_SECRET` too. Never send credentials in chat.
The uploader checks `expected_channel_id` before rendering and again before upload. Preserve posting history
to avoid script reuse; do not erase the old posting log when switching channels.

Install Python 3.10+ from python.org, then in a terminal inside this folder:

```bash
pip install google-auth-oauthlib google-api-python-client
python scripts/get_refresh_token.py /path/to/client_secret.json
```

A browser opens. Pick the account, then **pick the channel**. Brand channels are listed separately.
You'll see "Google hasn't verified this app": click **Advanced -> Go to Shorts Factory (unsafe)**. It's your own app.
Then allow access. The terminal prints the authorised channel name and three values.

In GitHub: **repo -> Settings -> Secrets and variables -> Actions -> New repository secret**, then add:

| Name | Value |
|---|---|
| `YT_CLIENT_ID` | printed value |
| `YT_CLIENT_SECRET` | printed value |
| `YT_REFRESH_TOKEN` | printed value |
| `GEMINI_API_KEY` | *(optional, already added for you)* key from aistudio.google.com. Writes picture plans for scripts without one, new scripts after the built-in ones run out, and Gemini images if the Google project has billing. |
| `PEXELS_API_KEY` | *(optional)* free key from pexels.com/api. Real stock photos for everyday things. |
| `PIXABAY_API_KEY` | *(optional)* free key from pixabay.com/api/docs. Backup stock photos. |
| `UNSPLASH_ACCESS_KEY` | *(optional)* free Access Key from unsplash.com/developers (demo apps: 50 searches/hour). Extra stock photos. |

Delete `client_secret.json` from your Downloads folder afterwards.

## 5. Test it (5 min)

1. Repo -> **Actions** tab -> if asked, click **I understand my workflows, go ahead and enable them**.
2. **Shorts Factory -> Run workflow**, leave **dry run** ticked, then click **Run**. After ~3 min, open the run. Under
   **Artifacts**, download the video and watch it.
3. Run it again with **dry run unticked** and **force ticked**. This publishes video #1 now and starts the 30-day campaign.
   Check that it appears in YouTube Studio.

## 6. Make the videos public: the API audit (do it before you leave)

Without this, YouTube keeps all API uploads private.

1. Fill in the **YouTube API Services Audit and Quota Extension Form**: https://support.google.com/youtube/contact/yt_api_form
2. Say it's an internal tool that uploads **your own original videos to your own channel**. Give your Google Cloud project number and channel link, and explain there are no other users.
3. Google may email follow-up questions. **Check your inbox** or they'll close the request.
4. Once approved, new uploads go public. Videos uploaded **before** approval stay private, and only you can change them
   in YouTube Studio. Google won't change them for you.

If you can't wait for approval, a fallback is to set `"privacy_status": "private"` in `config.json`. The videos pile up,
and you publish them by hand when you're back.

## 7. Leave

That's it. The schedule (UTC) is in `.github/workflows/shorts.yml`:

| Window | UTC | Lagos (WAT) | Runs (UTC) |
|---|---|---|---|
| Afternoon Short (peak) | 16:00-21:00 | 17:00-22:00 | 14:37, 15:37 (early, in case GitHub is late), 16:17, 17:07, 17:52, 18:37, 19:37 |
| Evening Short (peak) | 21:00-04:00 next day | 22:00-05:00 | 20:07 (early), 21:07, 21:52, 22:37, 23:22, 00:17, 01:17, 02:17 |

GitHub often starts scheduled runs 1-3 hours late or skips them at busy times, so each window has many runs.
Runs that arrive before a window opens, or when nothing is due, finish in ~30 s. The evening window stays open until
04:00 UTC, so evening runs GitHub delays past midnight still post that day's Short (`day_rollover_hour_utc` in
`config.json`). If every afternoon run was dropped, the evening runs post the missed Short too (at least 45 min
apart). Manual test uploads (`force`) never count toward the 2-a-day schedule.

After 30 days from the first upload, it stops by itself.
To get failure emails, open GitHub **Settings -> Notifications -> Actions** and choose **Only notify for failed workflows**.

---

## Retries and safety built in

- Voice: 3 tries per sentence, then an automatic switch to the offline Piper voice.
- Upload: resumable upload with up to 8 retries and exponential backoff for network errors and Google 5xx errors.
- Quota or daily-limit errors: the run stops cleanly, and the next scheduled run tries again.
- Missed window: a later run in the same window posts it; if the whole afternoon window was dropped, the evening runs catch up, even when GitHub delays them past midnight. Never more than 2 scheduled Shorts a day.
- No duplicates: each upload is written to `state/posted.json` **immediately** and committed with 5 push retries.
- Credentials are checked **before** rendering, so a bad token fails fast with a clear message.
- Videos are flagged `containsSyntheticMedia` (AI disclosure) and `madeForKids: false`.

## Customise

`config.json`: channel name (shown on every video), posting windows, voice (`edge-tts --list-voices`), privacy,
music on/off, campaign length. Scripts: `content/scripts.json`. Each script has a title, 6-9 sentences and tags.
Run tests with `python -m unittest discover tests`.

### Orbital animations and render speed

`config.json` keys that control how fast a Short is built and how space scenes look:

- `orbital_animations` — eligible Earth spin and Earth-centred orbit scenes use the official NASA
  Earth mesh, reduced to 12,000 triangles, with NASA geographic texture and a 23.44° tilted axis.
  At most two scenes per Short; other planets, transfer/flyby scenes and Uriel are not replaced.
  Spin is time-compressed and orbital trails are schematic, not measured mission trajectories.
  ModernGL renders off-screen through free Mesa/EGL; failure keeps the matched real photo.
- `picture_budget_seconds` — MAKOKOGW uses 20 seconds with four parallel workers, four-second
  request timeouts, pooled duplicate queries, persistent photo/search cache and no AI planner wait.
  Photos start alongside narration. Explicit Earth rotation and asteroid-impact sentences override
  generic plans; impacts use real Earth crater photographs, not invented impact photographs.
- `real_images_only` — no drawn cards or animated graphic backgrounds. If a scene has no matching
  image, hold a prior image only for the same subject; otherwise block that Short for review.
- `video.preset` / `video.crf` — MAKOKOGW uses `veryfast` + 17, still 1080×1920 H.264/AAC, not 4K.

The complete production target is 120 seconds with cached voice/caption models, excluding runner
setup, model downloads, quality inspection and YouTube upload. Timing is measured in each run;
network outages, cold models and runner variation mean the target is not a universal guarantee.
NASA asset sources and resolutions are recorded in `assets/earth/SOURCES.md`.

## Troubleshooting

| Error in the Actions log | Fix |
|---|---|
| `invalid_grant` | The app is still in Testing, or the token was revoked. Publish the app (step 3), redo step 4, and update `YT_REFRESH_TOKEN`. |
| `quotaExceeded` | Wait for the daily reset at midnight Pacific time. It retries automatically. |
| `uploadLimitExceeded` | Verify the channel by phone at youtube.com/verify. |
| Videos all private | The API audit isn't approved yet (step 6). |
| Nothing runs | Check that the Actions tab is enabled, and that the workflow file is at `.github/workflows/shorts.yml` on the default branch. |
| `Script bank is empty` | Add more scripts or a `GEMINI_API_KEY`. |

All tools used are free and open source (ffmpeg, Piper, edge-tts, Google API client).
The caption font, Anton, uses the SIL Open Font License (`assets/fonts/OFL.txt`).

## Providers and spending limits (free-first)
All Shorts are made with free services by default. Paid services (Gemini images, ElevenLabs voice) are only used when their key is a GitHub secret, they are listed in `config.json -> providers.enabled_paid`, and `daily_limit_usd`, `monthly_limit_usd` and `max_paid_calls_per_video` allow it (all 0 by default). Kling and Veo have slots but no adapter yet, so they always show "unavailable". Every paid call is logged with its estimated cost in `state/usage.json`. Each run's summary lists the source of every scene; scene motion is FFmpeg pan/zoom of still pictures, not AI video. If no voice engine works the run fails with a clear message instead of making a silent video.

## Ready queue and word-timed captions

The private Monthly Plan page shows a rolling 30-day schedule, two distinct scripts per day, the exact final narration line, and planned/ready/published states. `src/plan.py` builds `content/monthly-plan.json`; preparation consumes that order while excluding used scripts. Ready means the MP4 passed checks and its artifact was stored before queue state was committed. Planned dates are targets, not guarantees; campaign limits and delayed posting still apply.

`prepare.yml` renders and quality-checks one Short per run, up to 2 ready Shorts, with three scheduled checks daily. Posting downloads a prepared artifact instead of rendering when available. An empty queue falls back to live rendering; this is not a guarantee against service outages. Kokoro and Whisper run locally with no API fee, but model downloads and CPU inference consume runner time. The pinned PyAV dependency avoids the `metadata_errors` incompatibility. The Scenes summary records which engines actually ran.

## Channel optimization and analytics

### Daily relevant search trends (both channels)

`daily-seo.yml` checks both owned channels daily at 07:23 UTC (GitHub may delay runs).
It reviews all bot-tracked Shorts and older videos up to three minutes, skips unchanged metadata,
and updates at most 20 changed videos per channel per run to leave quota for uploads. Remaining
changes wait for later daily checks. Backups and results stay in private 14-day Actions artifacts.
Each upload also checks free Google Trends RSS for US, GB and CA, including already-rendered queue items.
Only an exact trend phrase already in the video's title is eligible: no unrelated news, gaming or
"viral" bait. One matching hashtag can appear in the title if it fits without cutting the title;
keywords belong in YouTube's tags field, not as a list in the title. Description hashtags remain small.
These are Google Search trends, **not verified YouTube search volume**. Often there is no relevant
trend; evergreen topic tags remain instead. Failed feeds and data older than 24 hours add no trend tags.
No paid service or key is needed; no search or recommendation improvement is guaranteed.
Existing uploads still need video-editing authorization. If absent, the daily review reports the
failure and stops editing; it does not replace tokens, change schedules, or stop the separate upload jobs.

The guide site's Optimization and Performance pages are restricted to the approved channel account. `channel.yml` reads the channel daily and on request; private Actions artifacts hold snapshots and pre-edit backups for 14 days. Analytics are never committed to the public repository. Edits preserve category, language, privacy and video footage, and verify channel ownership and YouTube read-back. Future uploads use topic-matched tags instead of unrelated channel-wide defaults.

Editing existing videos requires a newly authorized token including `youtube.force-ssl`. Watch time requires enabling **YouTube Analytics API** in Google Cloud and authorizing `yt-analytics.readonly`. Re-run the updated OAuth helper and replace the GitHub `YT_REFRESH_TOKEN` secret; old tokens do not gain scopes automatically. Until then, sync can show available public counts while clearly marking unavailable analytics and update failures.

The dashboard polls after a requested refresh and shows the latest confirmed subscriber count and timestamp, not a continuously streaming estimate. Each successful sync records the last confirmed count for that UTC day. Private `subscriber-history` artifacts carry the history forward (90-day retention per artifact); regular successful syncs preserve older observations inside newer artifacts. If every history artifact expires, continuity is lost. Missing or hidden subscriber counts remain unknown. An existing upload token does not need to change for these counts; editing and watch-time access still require the applicable Google permissions.

Views/likes/comments are lifetime counts; watch time and average duration cover a labeled 28-day window ending two days ago to allow reporting delay. The API does not expose Shorts' **Viewed vs swiped away** rate: see it in YouTube Studio, not an invented estimate here. Thumbnails shown are current YouTube thumbnails; select Shorts thumbnails through YouTube's supported app/Studio controls. The web workspace uses Lovable Cloud sign-in and saved edits, subject to its free allowance; ongoing $0 cost is not guaranteed if that allowance is exceeded. No keyword volume, ranking, reach or revenue is guaranteed.
