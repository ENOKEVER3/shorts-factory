"""Run ONCE on your own computer to authorise the uploader.

    pip install google-auth-oauthlib google-api-python-client
    python scripts/get_refresh_token.py path/to/client_secret.json

A browser opens -> sign in with the Google account that owns the channel -> pick the
channel (brand accounts are listed separately) -> allow. The script prints the three
values to paste into GitHub -> Settings -> Secrets and variables -> Actions.
Never commit client_secret.json or the printed values to the repository.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/get_refresh_token.py client_secret.json")
    secret_file = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("No refresh token returned. Remove the app at myaccount.google.com/permissions and retry.")

    channel = build("youtube", "v3", credentials=creds).channels().list(part="snippet", mine=True).execute()
    name = channel["items"][0]["snippet"]["title"] if channel.get("items") else "(no channel found!)"
    with open(secret_file, encoding="utf-8") as f:
        info = json.load(f)
    info = info.get("installed") or info.get("web")

    print("\nAuthorised channel:", name)
    print("\nAdd these as GitHub Actions secrets:\n")
    print("YT_CLIENT_ID      =", info["client_id"])
    print("YT_CLIENT_SECRET  =", info["client_secret"])
    print("YT_REFRESH_TOKEN  =", creds.refresh_token)
    print("\nKeep these private. Anyone with them can upload to your channel.")


if __name__ == "__main__":
    main()
