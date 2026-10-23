"""YouTube Data API v3: OAuth refresh-token auth + resumable upload with retries."""
from __future__ import annotations

import os
import random
import time
from pathlib import Path

from .util import fail, log

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
RETRIABLE_STATUS = {500, 502, 503, 504}
MAX_RETRIES = 8


def client():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    missing = [k for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        fail(f"Missing GitHub secrets: {', '.join(missing)}. See README step 4.")

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        fail(
            "Google rejected the refresh token (invalid_grant). Most common cause: the OAuth consent screen is "
            "still in 'Testing' mode, which expires tokens after 7 days. Publish the app to 'In production', "
            f"re-run scripts/get_refresh_token.py and update YT_REFRESH_TOKEN. Detail: {exc}"
        )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_title(yt) -> str:
    res = yt.channels().list(part="snippet", mine=True).execute()
    items = res.get("items", [])
    if not items:
        fail("This Google account has no YouTube channel. Create one, then redo the OAuth step.")
    return items[0]["snippet"]["title"]


def upload(yt, path: Path, title: str, description: str, tags: list[str], cfg: dict) -> str:
    import httplib2
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:30],
            "categoryId": cfg["category_id"],
            "defaultLanguage": cfg["language"],
            "defaultAudioLanguage": cfg["language"],
        },
        "status": {
            "privacyStatus": cfg["privacy_status"],
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
            "embeddable": True,
        },
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response, attempt = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log(f"Upload {int(status.progress() * 100)}%")
            continue
        except HttpError as exc:
            reason = ""
            try:
                reason = exc.error_details[0].get("reason", "") if exc.error_details else ""
            except Exception:  # noqa: BLE001
                pass
            if reason in ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded"):
                fail(f"YouTube refused the upload: {reason}. It resets daily (midnight Pacific). Next run will retry.")
            if exc.resp.status not in RETRIABLE_STATUS:
                raise
            err = f"HTTP {exc.resp.status}"
        except (OSError, TimeoutError, httplib2.HttpLib2Error) as exc:
            err = f"network error {exc}"
        attempt += 1
        if attempt > MAX_RETRIES:
            raise RuntimeError(f"Upload failed after {MAX_RETRIES} retries ({err})")
        sleep = min(2**attempt + random.random(), 120)
        log(f"Retriable upload problem ({err}); retry {attempt}/{MAX_RETRIES} in {sleep:.0f}s")
        time.sleep(sleep)

    if "id" not in response:
        raise RuntimeError(f"Unexpected upload response: {response}")
    return response["id"]
