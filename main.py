import sys
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common import load_cfg, authorize, authorize_manual, services, db
import drive_io
import learner
import titles
import uploader


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
        rows = con.execute("SELECT publish_at FROM uploads WHERE channel=?", (ch,)).fetchall()
        for row in rows:
            try:
                if datetime.fromisoformat(row["publish_at"].replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m-%d") == local_day:
                    day_count += 1
            except (TypeError, ValueError):
                continue
        duplicate = con.execute(
            "SELECT 1 FROM uploads WHERE channel=? AND publish_at=?", (ch, iso)
        ).fetchone()
        if day_count < max_per_day and not duplicate:
            return t
    return None


def run_channel(cfg, channel, con, used_slots=None):
    ch = channel["name"]
    tz = ZoneInfo(cfg["timezone"])
    yt, ya, drive = services(ch)
    measured = learner.measure(ch, ya, con)
    print(f"[{ch}] analytics refreshed; {measured} eligible upload records checked")

    video = drive_io.next_video(drive, channel["drive_ready_folder_id"])
    if not video:
        print(f"[{ch}] ready folder empty; nothing to upload")
        return False

    # If upload already succeeded but Drive move failed, finish the move instead of duplicating it.
    previous = con.execute(
        "SELECT video_id FROM uploads WHERE channel=? AND source_file_id=?",
        (ch, video["id"]),
    ).fetchone()
    if previous:
        drive_io.move(drive, video["id"], channel["drive_ready_folder_id"],
                      channel["drive_uploaded_folder_id"])
        print(f"[{ch}] source was already uploaded as https://youtu.be/{previous['video_id']}; moved to Uploaded")
        return True

    used_slots = used_slots if used_slots is not None else set()
    available_slots = [slot for slot in channel["slots"] if slot not in used_slots]
    if not available_slots:
        print(f"[{ch}] all configured slots used in this run")
        return False

    slot = learner.choose_slot(con, ch, available_slots, cfg.get("explore_rate", 0.2))
    when = next_publish_time(con, ch, slot, tz, channel.get("max_uploads_per_day", 3))
    if not when:
        print(f"[{ch}] no valid publish time found for slot {slot}")
        return False
    used_slots.add(slot)

    meta = drive_io.sidecar_meta(drive, channel["drive_ready_folder_id"], video["name"])
    if not meta.get("title") or not meta.get("description"):
        best, worst = learner.title_insights(con, ch)
        generated = titles.generate(cfg, channel, video["name"], best, worst)
        meta = {**generated, **meta}
    meta["title"] = str(meta.get("title", video["name"]))[:100]
    meta["description"] = str(meta.get("description", ""))[:5000]
    meta["tags"] = meta.get("tags") if isinstance(meta.get("tags"), list) else []

    path = drive_io.download(drive, video["id"], video["name"])
    try:
        publish_iso = when.astimezone(timezone.utc).isoformat()
        video_id = uploader.upload(
            yt, path, meta, publish_iso, channel["category_id"],
            channel.get("default_tags", []), channel.get("is_short", True),
        )
        con.execute(
            "INSERT INTO uploads(video_id,channel,title,slot,publish_at,source_file_id) VALUES(?,?,?,?,?,?)",
            (video_id, ch, meta["title"], slot, publish_iso, video["id"]),
        )
        con.commit()
        drive_io.move(drive, video["id"], channel["drive_ready_folder_id"],
                      channel["drive_uploaded_folder_id"])
        print(f"[{ch}] scheduled https://youtu.be/{video_id} at {when.isoformat()} (slot {slot})")
        return True
    finally:
        if os.path.exists(path):
            os.remove(path)


def report(cfg, con):
    for channel in cfg["channels"]:
        ch = channel["name"]
        print(f"\n== {ch} ==")
        stats = learner.slot_stats(con, ch)
        for slot, (score, count) in sorted(stats.items(), key=lambda item: -(item[1][0] or 0)):
            print(f"  {slot}: avg score {score or 0:.0f} over {count} videos")
        rows = con.execute(
            "SELECT title, views, avg_view_pct, avg_view_sec, minutes_watched, score, measured "
            "FROM uploads WHERE channel=? ORDER BY publish_at DESC LIMIT 15", (ch,)
        ).fetchall()
        print("Recent video analytics (metrics may be pending until YouTube reports them):")
        for row in rows:
            print(f"  {row['title']} | views={row['views']} | retention={row['avg_view_pct']}% "
                  f"| avg_sec={row['avg_view_sec']} | watch_min={row['minutes_watched']} "
                  f"| score={row['score']} | measured={row['measured']}")


if __name__ == "__main__":
    cfg = load_cfg()
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    con = db()
    failed = False

    if command == "auth":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: python main.py auth CHANNEL_NAME")
        authorize(cfg, sys.argv[2])
    elif command == "authm":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: python main.py authm CHANNEL_NAME")
        authorize_manual(cfg, sys.argv[2])
    elif command == "report":
        report(cfg, con)
    elif command in ("daily", "run"):
        for channel in cfg["channels"]:
            used_slots = set()
            attempts = channel.get("max_uploads_per_day", 3) if command == "daily" else 1
            for _ in range(attempts):
                try:
                    worked = run_channel(cfg, channel, con, used_slots)
                    if not worked:
                        break
                except Exception as exc:
                    failed = True
                    print(f"[{channel.get('name', 'unknown')}] ERROR: {type(exc).__name__}: {exc}")
                    break
    else:
        raise SystemExit(f"Unknown command '{command}'. Use daily, run, report, auth, or authm.")

    con.close()
    if failed:
        raise SystemExit(1)
