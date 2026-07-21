"""Sync users to Google Sheets (no passwords)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

HEADERS = [
    "ID",
    "ФИО",
    "Email",
    "Телефон",
    "Роль",
    "Подписка",
    "Имя родителя",
    "Телефон родителя",
    "Дата регистрации",
]


def sheets_configured() -> bool:
    return bool(settings.google_sheets_id and (
        settings.google_service_account_json
        or settings.google_service_account_file
    ))


def _credentials_info() -> dict | None:
    if settings.google_service_account_json:
        raw = settings.google_service_account_json.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        path = Path(raw)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    if settings.google_service_account_file:
        path = Path(settings.google_service_account_file)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _open_worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    info = _credentials_info()
    if not info:
        raise RuntimeError("Google service account credentials not found")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(settings.google_sheets_id)
    try:
        return spreadsheet.worksheet(settings.google_sheets_worksheet)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=settings.google_sheets_worksheet,
            rows=1000,
            cols=len(HEADERS),
        )
        ws.append_row(HEADERS)
        return ws


def _user_row(user: Any) -> list[str]:
    created = ""
    created_at = getattr(user, "created_at", None)
    if created_at:
        created = created_at.strftime("%Y-%m-%d %H:%M")
    return [
        str(getattr(user, "id", "")),
        getattr(user, "full_name", None) or "",
        getattr(user, "email", None) or "",
        getattr(user, "phone", None) or "",
        getattr(user, "role", None) or "",
        getattr(user, "subscription_status", None) or "",
        getattr(user, "parent_name", None) or "",
        getattr(user, "parent_phone", None) or "",
        created,
    ]


def upsert_user_row(user: Any) -> bool:
    """Insert or update a single user row. Never writes password."""
    if not sheets_configured():
        return False
    try:
        ws = _open_worksheet()
        values = ws.get_all_values()
        if not values:
            ws.append_row(HEADERS)
            values = [HEADERS]

        header = values[0]
        if header != HEADERS:
            # Ensure header row exists / is correct
            ws.update(range_name="A1", values=[HEADERS])
            values = ws.get_all_values()

        user_id = str(getattr(user, "id", ""))
        row_index = None
        for i, row in enumerate(values[1:], start=2):
            if row and row[0] == user_id:
                row_index = i
                break

        row_data = _user_row(user)
        if row_index:
            ws.update(range_name=f"A{row_index}", values=[row_data])
        else:
            ws.append_row(row_data)
        return True
    except Exception:
        logger.exception("Google Sheets upsert failed for %s", getattr(user, "email", "?"))
        return False


def sync_all_users(users: list[Any]) -> int:
    """Replace sheet contents with full user list (headers + rows, no passwords)."""
    if not sheets_configured():
        return 0
    try:
        ws = _open_worksheet()
        rows = [HEADERS] + [_user_row(u) for u in users]
        ws.clear()
        ws.update(range_name="A1", values=rows)
        return len(users)
    except Exception:
        logger.exception("Google Sheets full sync failed")
        return 0
