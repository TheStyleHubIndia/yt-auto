import sys, os, random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from common import load_cfg, authorize, authorize_manual, services, db
import drive_io, learner, titles, uploader

def next_publish_time(con, ch, slot, tz, max_per_day):
    """slot 'America/New_York 19:00' = us country ka local time. Bina zone ke default tz."""
    if " " in slot:
        zone, hhmm = slot.rsplit(" ", 1)
        tz = ZoneInfo(zone)
    else:
        hhmm = slot
    h, mi = map(int, hhmm.split(":"))
    now = datetime.now(tz)
    for d in range(0, 14):
        t = (now + timedelta(days=d)).replace(hour=h, minute=mi, second=0, microsecond=0)
        if t < now + timedelta(hours=1): continue
        iso = t.astimezone(timezone.utc).isoformat()
        n = con.execute("SELECT COUNT(*) c FROM uploads WHERE channel=? AND substr(publish_at,1,10)=?",
                        (ch, iso[:10])).fetchone()["c"]
        dup = con.execute("SELECT 1 FROM uploads WHERE channel=? AND substr(publish_at,1,16)=?",
                          (ch, iso[:16])).fetchone()
        if n < max_per_day and not dup:
            return t
    return None

def run_channel(cfg, c, con):
    ch = c["name"]; tz = ZoneInfo(cfg["timezone"])
    yt, ya, drive = services(ch)
    print(f"[{ch}] measured {learner.measure(ch, ya, con)} old uploads")
    f = drive_io.next_video(drive, c["drive_ready_folder_id"])
    if not f: print(f"[{ch}] ready folder empty"); return
    slot = learner.choose_slot(con, ch, c["slots"], cfg.get("explore_rate", 0.2))
    when = next_publish_time(con, ch, slot, tz, c.get("max_uploads_per_day", 3))
    if not when: print(f"[{ch}] schedule full"); return
    meta = drive_io.sidecar_meta(drive, c["drive_ready_folder_id"], f["name"])
    if not meta.get("title"):
        best, worst = learner.title_insights(con, ch)
        meta = {**titles.generate(cfg, c, f["name"], best, worst), **meta}
    path = drive_io.download(drive, f["id"], f["name"])
    iso = when.astimezone(timezone.utc).isoformat()
    vid = uploader.upload(yt, path, meta, iso, c["category_id"], c.get("default_tags", []), c["is_short"])
    con.execute("INSERT INTO uploads(video_id,channel,title,slot,publish_at) VALUES(?,?,?,?,?)",
                (vid, ch, meta["title"], slot, iso)); con.commit()
    drive_io.move(drive, f["id"], c["drive_ready_folder_id"], c["drive_uploaded_folder_id"])
    os.remove(path)
    print(f"[{ch}] scheduled https://youtu.be/{vid} at {when} (slot {slot})")

def report(cfg, con):
    for c in cfg["channels"]:
        print(f"\n== {c['name']} ==")
        for s, (score, n) in sorted(learner.slot_stats(con, c["name"]).items(),
                                    key=lambda x: -x[1][0]):
            print(f"  {s}: avg score {score:.0f} over {n} videos")

if __name__ == "__main__":
    cfg = load_cfg(); cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    con = db()
    if cmd == "auth": authorize(cfg, sys.argv[2])
    elif cmd == "authm": authorize_manual(cfg, sys.argv[2])
    elif cmd == "report": report(cfg, con)
    elif cmd == "daily":
        for c in cfg["channels"]:
            for _ in range(c.get("max_uploads_per_day", 2)):
                try: run_channel(cfg, c, con)
                except Exception as e:
                    print(f"[{c['name']}] ERROR: {e}"); break
    elif cmd == "run":
        for c in cfg["channels"]:
            try: run_channel(cfg, c, con)
            except Exception as e: print(f"[{c['name']}] ERROR: {e}")
