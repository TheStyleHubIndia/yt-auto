"""Analytics -> score -> slot bandit + title pattern insights."""
import random, re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MEASURE_AFTER_HOURS = 48

def measure(ch, ya, con):
    """48h+ purane videos ke metrics nikalo aur score save karo."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=MEASURE_AFTER_HOURS)).isoformat()
    rows = con.execute("SELECT * FROM uploads WHERE channel=? AND measured=0 AND publish_at<=?",
                       (ch, cutoff)).fetchall()
    for r in rows:
        start = r["publish_at"][:10]
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        res = ya.reports().query(
            ids="channel==MINE", startDate=start, endDate=end,
            metrics="views,averageViewDuration,averageViewPercentage,estimatedMinutesWatched",
            filters=f"video=={r['video_id']}").execute()
        if not res.get("rows"): continue
        views, avg_sec, avg_pct, mins = res["rows"][0]
        # Score: reach + retention dono (retention weight zyada, YouTube ka signal wahi hai)
        t1 = tier1_views(ya, r["video_id"], start, end)
        weighted = views if t1 is None else (t1 + 0.2 * (views - t1))
        score = weighted * (0.5 + (avg_pct or 0) / 100)
        con.execute("""UPDATE uploads SET views=?,avg_view_sec=?,avg_view_pct=?,
                       minutes_watched=?,score=?,measured=1 WHERE video_id=?""",
                    (views, avg_sec, avg_pct, mins, score, r["video_id"]))
    con.commit()
    return len(rows)

def slot_stats(con, ch):
    rows = con.execute("""SELECT slot, AVG(score) s, COUNT(*) n FROM uploads
                          WHERE channel=? AND measured=1 GROUP BY slot""", (ch,)).fetchall()
    return {r["slot"]: (r["s"], r["n"]) for r in rows}

def choose_slot(con, ch, slots, explore_rate):
    """Epsilon-greedy: kam-test hue slots ko pehle try karo, phir best ko exploit."""
    stats = slot_stats(con, ch)
    untested = [s for s in slots if stats.get(s, (0, 0))[1] < 3]
    if untested and (random.random() < 0.7 or len(untested) == len(slots)):
        return random.choice(untested)
    if random.random() < explore_rate or not stats:
        return random.choice(slots)
    return max(stats, key=lambda s: stats[s][0])

def title_features(t):
    return {"has_number": bool(re.search(r"\d", t)), "is_question": "?" in t,
            "short": len(t) <= 50}

def title_insights(con, ch, top=5):
    """Best aur worst titles Claude ke prompt me jaate hain -> pattern seekhna."""
    best = con.execute("SELECT title FROM uploads WHERE channel=? AND measured=1 "
                       "ORDER BY score DESC LIMIT ?", (ch, top)).fetchall()
    worst = con.execute("SELECT title FROM uploads WHERE channel=? AND measured=1 "
                        "ORDER BY score ASC LIMIT ?", (ch, top)).fetchall()
    return [r["title"] for r in best], [r["title"] for r in worst]


TIER1 = {"US", "CA", "GB", "AU", "NZ", "IE", "DE", "FR", "NL", "SE", "NO", "DK", "FI", "CH", "AT", "BE"}

def tier1_views(ya, vid, start, end):
    try:
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, metrics="views",
                               dimensions="country", filters=f"video=={vid}").execute()
        return sum(v for c, v in r.get("rows", []) if c in TIER1)
    except Exception:
        return None
