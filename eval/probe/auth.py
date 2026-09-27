"""One-time sign-in for the tool probe. Dummy account only.

Signs in once with every scope the app_tools modules use and writes the six
per-service token files they expect (app_tools/cred/*_token.json, gitignored).
Nothing is saved unless the signed-in account matches --account.

Run from the repo root:
    .venv/Scripts/python.exe eval/probe/auth.py --account <dummy-address>

In the consent screen, tick every permission box. Refresh tokens from an OAuth
app in "Testing" mode expire after 7 days; rerun this when the probe says so.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

from app_tools.auth.service_decoder import SCOPES  # noqa: E402

CRED_DIR = REPO / "app_tools" / "cred"
TOKEN_FILES = [
    "gmail_token.json",
    "calendar_token.json",
    "gdrive_token.json",
    "gdocs_token.json",
    "gsheet_token.json",
    "gtask_token.json",
]
ACCOUNT_FILE = Path(__file__).parent / "out" / "account.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--account", required=True, help="the dummy account you will sign in with")
    expected = parser.parse_args().account.strip().lower()

    scopes = sorted({scope for group in SCOPES.values() for scope in group})
    flow = InstalledAppFlow.from_client_secrets_file(str(CRED_DIR / "setup_cred.json"), scopes)
    creds = flow.run_local_server(port=0)

    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    actual = gmail.users().getProfile(userId="me").execute()["emailAddress"].lower()
    if actual != expected:
        sys.exit(f"Signed in as {actual}, expected {expected}. Nothing saved.")

    granted = set(getattr(creds, "granted_scopes", None) or creds.scopes or [])
    missing = sorted(set(scopes) - granted)
    if missing:
        sys.exit(f"These permissions were not granted (tick every box): {missing}. Nothing saved.")

    token_json = creds.to_json()
    for name in TOKEN_FILES:
        (CRED_DIR / name).write_text(token_json, encoding="utf-8")
    ACCOUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_FILE.write_text(json.dumps({"account": actual}), encoding="utf-8")
    print(f"Signed in as {actual}. Wrote {len(TOKEN_FILES)} token files to {CRED_DIR}.")


if __name__ == "__main__":
    main()
