"""Authorize only the configured new channel. Never share or commit printed credentials."""
import json
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
def main():
    if len(sys.argv) != 2:
        sys.exit('Usage: python scripts/get_refresh_token.py client_secret.json')
    cfg = json.loads((Path(__file__).resolve().parent.parent / 'config.json').read_text())
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
    if not creds.refresh_token:
        sys.exit('No refresh token returned. Authorize again.')
    items = build('youtube', 'v3', credentials=creds).channels().list(part='snippet', mine=True).execute().get('items', [])
    if len(items) != 1 or items[0].get('id') != cfg.get('expected_channel_id'):
        sys.exit('Wrong channel selected. Choose the new channel and authorize again. No credentials printed.')
    info = json.loads(Path(sys.argv[1]).read_text())
    info = info.get('installed') or info.get('web')
    print('Authorized channel:', items[0]['snippet']['title'])
    print('Channel ID:', items[0]['id'])
    print('Add these as GitHub Actions secrets; never send them in chat:')
    print('YT_CLIENT_ID =', info['client_id'])
    print('YT_CLIENT_SECRET =', info['client_secret'])
    print('YT_REFRESH_TOKEN =', creds.refresh_token)
if __name__ == '__main__':
    main()
