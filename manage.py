import sys, argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from common import load_cfg, services, db
import titles

cfg = load_cfg()
CH = cfg["channels"][0]
FMT = "%Y-%m-%dT%H:%M:%S.000Z"

def utc_iso(s):
    t = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(cfg["timezone"]))
    return t.astimezone(timezone.utc).strftime(FMT)

def update(yt, vid, title=None, desc=None, tags=None, at=None):
    items = yt.videos().list(part="snippet,status", id=vid).execute()["items"]
    if not items: sys.exit("video nahi mila: " + vid)
    sn, st = items[0]["snippet"], items[0]["status"]
    snippet = {"title": title[:100] if title else sn["title"],
               "description": desc if desc is not None else sn.get("description", ""),
               "tags": tags if tags is not None else sn.get("tags", []),
               "categoryId": sn["categoryId"]}
    keys = ("privacyStatus", "embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids")
    status = {k: st[k] for k in keys if k in st}
    if at:
        if st["privacyStatus"] != "private":
            sys.exit("Video already public/unlisted hai, schedule nahi ho sakta")
        status["publishAt"] = at
    elif "publishAt" in st:
        status["publishAt"] = st["publishAt"]
    yt.videos().update(part="snippet,status",
                       body={"id": vid, "snippet": snippet, "status": status}).execute()
    con = db()
    con.execute("UPDATE uploads SET title=?, publish_at=COALESCE(?,publish_at) WHERE video_id=?",
                (snippet["title"], at, vid))
    con.commit()

def recent(n):
    return [r[0] for r in db().execute(
        "SELECT video_id FROM uploads ORDER BY uploaded_at DESC LIMIT ?", (n,))]

def cmd_list(yt):
    ids = recent(10)
    if not ids: return print("koi upload nahi")
    for v in yt.videos().list(part="snippet,status", id=",".join(ids)).execute()["items"]:
        s = v["status"]
        print("https://youtu.be/" + v["id"])
        print("  " + v["snippet"]["title"])
        print("  ", s["privacyStatus"], "| publishAt:", s.get("publishAt"), "|", s["uploadStatus"])

def cmd_auto(yt, n):
    for vid in recent(n):
        m = titles.template_meta(CH["niche"])
        update(yt, vid, m["title"], m["description"], m["tags"])
        print("updated", vid, "|", m["title"])

def cmd_schedule(yt, vid, when):
    if when:
        at = utc_iso(when)
    else:
        from main import next_publish_time
        import learner
        con = db()
        slot = learner.choose_slot(con, CH["name"], CH["slots"], cfg.get("explore_rate", 0.2))
        t = next_publish_time(con, CH["name"], slot, ZoneInfo(cfg["timezone"]),
                              CH.get("max_uploads_per_day", 3))
        if not t: sys.exit("schedule full")
        at = t.astimezone(timezone.utc).strftime(FMT)
        print("slot", slot, "->", t)
    update(yt, vid, at=at)
    print("scheduled (UTC):", at)

def cmd_audience():
    from datetime import date, timedelta
    from learner import TIER1
    ya = services(CH["name"])[1]
    end = date.today(); start = end - timedelta(days=28)
    r = ya.reports().query(ids="channel==MINE", startDate=str(start), endDate=str(end),
                           metrics="views", dimensions="country", sort="-views", maxResults=200).execute()
    rows = r.get("rows", [])
    tot = sum(v for _, v in rows) or 1
    for c, v in rows[:10]:
        print(f"{c}: {v} views ({100*v/tot:.0f}%)" + (" [tier1]" if c in TIER1 else ""))
    t1 = sum(v for c, v in rows if c in TIER1)
    print(f"Tier-1 share: {100*t1/tot:.0f}% of {tot} views (last 28 days)")

if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "list"
    yt = services(CH["name"])[0]
    if cmd == "audience": cmd_audience()
    elif cmd == "list": cmd_list(yt)
    elif cmd == "auto": cmd_auto(yt, int(a[1]) if len(a) > 1 else 1)
    elif cmd == "schedule": cmd_schedule(yt, a[1], a[2] if len(a) > 2 else None)
    elif cmd == "set":
        p = argparse.ArgumentParser()
        for k in ("vid",): p.add_argument(k)
        for k in ("--title", "--desc", "--tags", "--at"): p.add_argument(k)
        x = p.parse_args(a[1:])
        update(yt, x.vid, x.title, x.desc, x.tags.split(",") if x.tags else None,
               utc_iso(x.at) if x.at else None)
        print("done")
