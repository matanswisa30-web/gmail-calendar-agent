"""Google OAuth and API service construction.

Follows the reference flow from the assignment's Appendix A:

    credentials.json (the "Client", downloaded from Google Auth Platform)
        --> first-run consent in the browser -->
    token.json (the "Token", a scoped, refreshable credential stored locally)

The token is reused and silently refreshed on later runs.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import Settings


def get_credentials(settings: Settings) -> Credentials:
    """Return valid user credentials, running the consent flow if needed."""
    creds: Credentials | None = None
    token_path = Path(settings.token_file)
    creds_path = Path(settings.credentials_file)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(
            str(token_path), settings.scopes
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Missing '{creds_path}'. Download an OAuth client of type "
                    "'Desktop app' from the Google Auth Platform and save it as "
                    f"'{creds_path}'. See README / Appendix A."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), settings.scopes
            )
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_services(settings: Settings):
    """Authenticate and return (gmail_service, calendar_service)."""
    creds = get_credentials(settings)
    gmail_service = build("gmail", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    return gmail_service, calendar_service
