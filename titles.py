import os, json

def _prompt(channel, filename, best, worst):
    return "\n".join([
        "Channel niche: %s. Video file name: %s." % (channel["niche"], filename),
        "This is a YouTube Short for a Tier-1 English-speaking audience (US, UK, Canada, Australia).",
        "Top-performing titles on this channel: %s" % (best or "no data yet"),
        "Worst-performing titles: %s" % (worst or "no data yet"),
        "Follow the pattern of the top titles and avoid the worst. Be honest, no fake clickbait.",
        "Write everything in English.",
        'Return ONLY JSON: {"title": "<=70 chars", "description": "2-3 lines, then a blank line and 4-5 relevant hashtags", "tags": ["..."]}',
    ])

def _parse(txt):
    txt = txt.strip().strip("`").strip()
    if txt.lower().startswith("json"):
        txt = txt[4:]
    return json.loads(txt.strip())

def _gemini(prompt):
    import urllib.request
    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (
        model, os.environ["GEMINI_API_KEY"])
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json"}}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return r["candidates"][0]["content"]["parts"][0]["text"]

def _claude(cfg, prompt):
    import anthropic
    r = anthropic.Anthropic().messages.create(
        model=cfg.get("anthropic_model", "claude-sonnet-5-5"), max_tokens=500,
        messages=[{"role": "user", "content": prompt}])
    return r.content[0].text

def generate(cfg, channel, filename, best, worst):
    p = _prompt(channel, filename, best, worst)
    try:
        if os.getenv("GEMINI_API_KEY"): return _parse(_gemini(p))
        if os.getenv("ANTHROPIC_API_KEY"): return _parse(_claude(cfg, p))
    except Exception as e:
        print("AI title failed, template use ho raha hai:", e)
    return template_meta(channel["niche"])


HOOKS = [
    "Don't Give Up: Your Time Will Come",
    "When Everything Feels Hard, Watch This",
    "Small Steps Every Day Lead to Big Success",
    "Believe in Yourself, Everything Is Possible",
    "This 30-Second Reminder Can Change Your Day",
    "Hard Work Always Pays Off",
    "Keep Going: Your Goals Are Closer Than You Think",
    "Stay Consistent and Success Will Follow",
]

def template_meta(niche):
    import random
    if "motivat" in niche.lower():
        hook = random.choice(HOOKS)
        tags = ["motivation", "motivational quotes", "success mindset", "inspiration", "never give up", "shorts"]
        hashtags = "#Shorts #Motivation #Mindset #Success #Inspiration #NeverGiveUp"
        body = "Keep moving forward, one step at a time. If this inspired you, like, share and subscribe for daily motivation."
    else:
        hook = niche.title()
        tags = [w for w in niche.lower().split() if len(w) > 2] + ["shorts"]
        hashtags = "#Shorts " + " ".join("#" + w.capitalize() for w in niche.split() if len(w) > 2)
        body = "If you enjoyed this, like and subscribe for more."
    return {"title": (hook + " #Shorts")[:100],
            "description": hook + "\n\n" + body + "\n\n" + hashtags, "tags": tags}
