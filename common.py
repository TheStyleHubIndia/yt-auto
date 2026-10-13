import sqlite3, yaml, os
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
    return yaml.safe_load(open("config.yaml"))

def token_path(ch): return f"tokens/{ch}.json"

def authorize(cfg, ch):
    """Ek baar chalao: browser khulega, us channel ka Google account chuno."""
    flow = InstalledAppFlow.from_client_secrets_file(cfg["client_secret_file"], SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    open(token_path(ch), "w").write(creds.to_json())
    print(f"[{ch}] token saved")

def get_creds(ch):
    creds = Credentials.from_authorized_user_file(token_path(ch), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        open(token_path(ch), "w").write(creds.to_json())
    return creds

def services(ch):
    c = get_creds(ch)
    return (build("youtube", "v3", credentials=c),
            build("youtubeAnalytics", "v2", credentials=c),
            build("drive", "v3", credentials=c))

def db():
    con = sqlite3.connect("data.db")
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS uploads(
        video_id TEXT PRIMARY KEY, channel TEXT, title TEXT, slot TEXT,
        publish_at TEXT, uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        views INTEGER, avg_view_pct REAL, avg_view_sec REAL, minutes_watched REAL,
        score REAL, measured INTEGER DEFAULT 0);
    """)
    return con


def authorize_manual(cfg, ch):
    """Phone/Colab ke liye: link kholo, login karo, jo localhost wala URL error page pe aaye use paste karo."""
    flow = InstalledAppFlow.from_client_secrets_file(
        cfg["client_secret_file"], SCOPES, redirect_uri="http://localhost:8080/")
    url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("\n1) Ye link browser me kholo aur channel wala account chuno:\n\n" + url)
    print("\n2) Allow ke baad page 'localhost refused' dikhayega. Address bar ka POORA URL copy karo.")
    resp = input("\n3) Wo URL yahan paste karo: ").strip()
    flow.fetch_token(authorization_response=resp.replace("https://", "http://", 1)
                     if resp.startswith("https://localhost") else resp)
    open(token_path(ch), "w").write(flow.credentials.to_json())
    print(f"[{ch}] token saved")
