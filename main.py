import sys, os, random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from common import load_cfg, authorize, authorize_manual, services, db
import drive_io, learner, titles, uploader

def next_publish_time(con, ch, slot, tz, max_per_day):
    """Find the next valid publish time in the selected slot's own timezone."""
    if " " in slot:
        zone, hhmm = slot.rsplit(" ", 1)
        tz = ZoneInfo(zone)
    else:
        hhmm = slot
    h, mi = map(int, hhmm.split(":"))
    now = datetime.now(tz)
    for d in range(0, 14):
        t = (now + timedelta(days=d)).replace(hour=h, minute=mi, second=0, microsecond=0)
        if t < now + timedelta(hours=1):
            continue
        iso = t.astimezone(timezone.utc).isoformat()
        local_day = t.strftime("%Y-%m-%d")
        day_count = 0
        for row in con.execute("SELECT publish_at FROM uploads WHERE channel=?", (ch,)).fetchall():
            try:
                if datetime.fromisoformat(row["publish_at"].replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m-%d") == local_day:
                    day_count += 1
            except Exception:
                continue
        dup = con.execute("SELECT 1 FROM uploads WHERE channel=? AND publish_at=?",
                          (ch, iso)).fetchone()
        if day_count < max_per_day and not dup:
            return t
    return None

def run_channel(cfg, c, con, used_slots=None):
    ch = c["name"]
    tz = ZoneInfo(cfg["timezone"])
    yt, ya, drive = services(ch)
    measured = learner.measure(ch, ya, con)
    print(f"[{ch}] analytics refreshed; {measured} eligible upload records checked")
    f = drive_io.next_video(drive, c["drive_ready_folder_id"])
    if not f:
        print(f"[{ch}] ready folder empty")
        return
    used_slots = used_slots if used_slots is not None else set()
    available_slots = [s for s in c["slots"] if s not in used_slots]
    if not available_slots:
        print(f"[{ch}] all configured slots used in this run")
        return
    slot = learner.choose_slot(con, ch, available_slots, cfg.get("explore_rate", 0.2))
    used_slots.add(slot)
    when = next_publish_time(con, ch, slot, tz, c.get("max_uploads_per_day", 3))
    if not when:
        print(f"[{ch}] no valid publish time found for slot {slot}")
        return
    meta = drive_io.sidecar_meta(drive, c["drive_ready_folder_id"], f["name"])
    if not meta.get("title"):
        best, worst = learner.title_insights(con, ch)
        meta = {**titles.generate(cfg, c, f["name"], best, worst), **meta}
    path = drive_io.download(drive, f["id"], f["name"])
    try:
        iso = when.astimezone(timezone.utc).isoformat()
        vid = uploader.upload(yt, path, meta, iso, c["category_id"], c.get("default_tags", []), c["is_short"])
        con.execute("INSERT INTO uploads(video_id,channel,title,slot,publish_at) VALUES(?,?,?,?,?)",
                    (vid, ch, meta["title"], slot, iso))
        con.commit()
        drive_io.move(drive, f["id"], c["drive_ready_folder_id"], c["drive_uploaded_folder_id"])
        print(f"[{ch}] scheduled https://youtu.be/{vid} at {when.isoformat()} (slot {slot})")
    finally:
        if os.path.exists(path):
            os.remove(path)

def report(cfg, con):
    for c in cfg["channels"]:
        print(f"\n== {c['name']} ==")
        for s, (score, n) in sorted(learner.slot_stats(con, c["name"]).items(),
                                    key=lambda x: -x[1][0]):
            print(f"  {s}: avg score {score:.0f} over {n} videos")
        rows = con.execute(
            "SELECT title, views, avg_view_pct, avg_view_sec, minutes_watched, score, measured "
            "FROM uploads WHERE channel=? ORDER BY publish_at DESC LIMIT 15", (c["name"],)
        ).fetchall()
        print("Recent video analytics (metrics may be pending until YouTube reports them):")
        for r in rows:
            print(f"  {r['title']} | views={r['views']} | retention={r['avg_view_pct']}% "
                  f"| avg_sec={r['avg_view_sec']} | watch_min={r['minutes_watched']} "
                  f"| score={r['score']} | measured={r['measured']}")

if __name__ == "__main__":
    cfg = load_cfg()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    con = db()
    if cmd == "auth":
        authorize(cfg, sys.argv[2])
    elif cmd == "authm":
        authorize_manual(cfg, sys.argv[2])
    elif cmd == "report":
        report(cfg, con)
    elif cmd == "daily":
        for c in cfg["channels"]:
            used_slots = set()
            for _ in range(c.get("max_uploads_per_day", 3)):
                try:
                    run_channel(cfg, c, con, used_slots)
                except Exception as e:
                    print(f"[{c['name']}] ERROR: {e}")
                    break
    elif cmd == "run":
        for c in cfg["channels"]:
            try:
                run_channel(cfg, c, con)
            except Exception as e:
                print(f"[{c['name']}] ERROR: {e}")
