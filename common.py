import sqlite3
import yaml
import os
from pathlib import Path

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # localhost redirect ke liye

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/drive",
]


def load_cfg():
    path = Path("config.yaml")
    if not path.exists():
        raise SystemExit(
            "CONFIG ERROR: config.yaml was not created. Check the GitHub Actions "
            "CONFIG_YAML secret and the workflow's 'Write credentials and configuration' step."
        )
    try:
        with path.open(encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise SystemExit(
            "CONFIG ERROR: CONFIG_YAML is invalid YAML" + where +
            ". Replace the GitHub CONFIG_YAML secret with the complete config.example.yaml "
            "contents, preserve spaces/indentation, and do not use tabs. Parser detail: " + str(exc)
        ) from exc
    if not isinstance(cfg, dict):
        raise SystemExit("CONFIG ERROR: config.yaml must be a YAML mapping.")
    for key in ("client_secret_file", "timezone", "channels"):
        if key not in cfg:
            raise SystemExit(f"CONFIG ERROR: missing top-level key '{key}'. Copy config.example.yaml.")
    if not isinstance(cfg["channels"], list) or not cfg["channels"]:
        raise SystemExit("CONFIG ERROR: 'channels' must be a non-empty list.")
    required = ("name", "drive_ready_folder_id", "drive_uploaded_folder_id",
                "niche", "category_id", "slots")
    for i, channel in enumerate(cfg["channels"], start=1):
        if not isinstance(channel, dict):
            raise SystemExit(f"CONFIG ERROR: channels item {i} must be a mapping.")
        missing = [key for key in required if not channel.get(key)]
        if missing:
            raise SystemExit(f"CONFIG ERROR: channels item {i} missing: {', '.join(missing)}.")
        if str(channel["drive_uploaded_folder_id"]).upper() == "UPLOADED_FOLDER_ID":
            raise SystemExit(
                f"CONFIG ERROR: channel '{channel['name']}' still uses UPLOADED_FOLDER_ID. "
                "Set the real destination Drive folder ID in CONFIG_YAML."
            )
        if not isinstance(channel["slots"], list) or not channel["slots"]:
            raise SystemExit(f"CONFIG ERROR: channel '{channel['name']}' needs at least one slot.")
    return cfg


def token_path(ch):
    return f"tokens/{ch}.json"


def authorize(cfg, ch):
    """Ek baar chalao: browser khulega, us channel ka Google account chuno."""
    flow = InstalledAppFlow.from_client_secrets_file(cfg["client_secret_file"], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    Path(token_path(ch)).write_text(creds.to_json(), encoding="utf-8")
    print(f"[{ch}] token saved")


def get_creds(ch):
    creds = Credentials.from_authorized_user_file(token_path(ch), SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise RuntimeError(
                f"No refresh_token in {token_path(ch)}. Re-authorize with offline access and replace TOKEN secret."
            )
        creds.refresh(Request())
        Path(token_path(ch)).write_text(creds.to_json(), encoding="utf-8")
    return creds


def services(ch):
    credentials = get_creds(ch)
    return (
        build("youtube", "v3", credentials=credentials),
        build("youtubeAnalytics", "v2", credentials=credentials),
        build("drive", "v3", credentials=credentials),
    )


def db():
    con = sqlite3.connect("data.db")
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS uploads(
        video_id TEXT PRIMARY KEY, channel TEXT, title TEXT, slot TEXT,
        publish_at TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        views INTEGER, avg_view_pct REAL, avg_view_sec REAL, minutes_watched REAL,
        score REAL, measured INTEGER DEFAULT 0, source_file_id TEXT);
    """)
    # Safe, idempotent migration for existing data.db files.
    columns = {row["name"] for row in con.execute("PRAGMA table_info(uploads)").fetchall()}
    if "source_file_id" not in columns:
        con.execute("ALTER TABLE uploads ADD COLUMN source_file_id TEXT")
    con.commit()
    return con


def authorize_manual(cfg, ch):
    """Phone/Colab ke liye: localhost URL manually paste karke OAuth complete karein."""
    flow = InstalledAppFlow.from_client_secrets_file(
        cfg["client_secret_file"], SCOPES, redirect_uri="http://localhost:8080/")
    url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("\n1) Ye link browser me kholo aur channel wala account chuno:\n\n" + url)
    print("\n2) Allow ke baad page 'localhost refused' dikhayega. Address bar ka POORA URL copy karo.")
    resp = input("\n3) Wo URL yahan paste karo: ").strip()
    flow.fetch_token(authorization_response=resp.replace("https://", "http://", 1)
                     if resp.startswith("https://localhost") else resp)
    Path(token_path(ch)).write_text(flow.credentials.to_json(), encoding="utf-8")
    print(f"[{ch}] token saved")
