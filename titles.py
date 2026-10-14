import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError


def _clean_topic(filename):
    stem = Path(filename).stem
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = re.sub(r"\b(final|final edit|export|1080p|720p|4k)\b", "", stem, flags=re.I)
    stem = re.sub(r"\s+", " ", stem).strip(" -_")
    return stem[:100] or "Amazing Facts"


def _prompt(channel, filename, best, worst):
    topic = _clean_topic(filename)
    return "\n".join([
        "Channel niche: %s." % channel["niche"],
        "Video filename/topic clue: %s." % topic,
        "The primary audience is in India. Use concise, natural English by default; use Hindi/Hinglish only when the filename/topic clue clearly indicates it.",
        "Optimize for YouTube Shorts discovery without keyword stuffing or misleading clickbait.",
        "Create metadata relevant to the filename/topic only; do not claim to have watched the video.",
        "Top-performing titles: %s" % (best or "no data yet"),
        "Low-performing titles to avoid copying: %s" % (worst or "no data yet"),
        "Write in natural English. Be accurate, specific, and non-misleading.",
        "Title must be <= 90 characters and include the topic.",
        "Description: 1-3 useful sentences, then 3-5 relevant hashtags including #Shorts.",
        "Tags: 5-12 relevant plain-text keywords, no # symbols.",
        'Return ONLY valid JSON: {"title":"...","description":"...","tags":["..."]}',
    ])


def _parse(txt):
    txt = txt.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.I)
    data = json.loads(txt)
    if not isinstance(data, dict):
        raise ValueError("AI metadata must be a JSON object")
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    tags = data.get("tags", [])
    if not title or not description or not isinstance(tags, list):
        raise ValueError("AI response is missing title, description, or tags")
    clean_tags = list(dict.fromkeys(str(x).strip().lstrip("#")[:100] for x in tags if str(x).strip()))
    if not clean_tags:
        raise ValueError("AI response returned no usable tags")
    return {"title": title[:100], "description": description[:5000], "tags": clean_tags[:20]}


def _gemini(prompt):
    import urllib.request
    key = os.environ["GEMINI_API_KEY"]
    preferred = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    models = list(dict.fromkeys([preferred, "gemini-3.8-flash", "gemini-3.1-pro-preview"]))
    # Discover models available to this key; availability differs by project.
    try:
        list_req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": key},
        )
        with urllib.request.urlopen(list_req, timeout=30) as response:
            available = json.loads(response.read()).get("models", [])
        discovered = [
            item["name"].split("/")[-1] for item in available
            if item.get("name") and "generateContent" in item.get("supportedGenerationMethods", [])
        ]
        models = list(dict.fromkeys([preferred] + discovered[:2] + models))
    except (HTTPError, URLError, TimeoutError, ValueError):
        pass
    errors = []
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }).encode()
    for model in models:
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        req = urllib.request.Request(
            url, body,
            {"Content-Type": "application/json", "x-goog-api-key": key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read())
            parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = next((part.get("text") for part in parts if part.get("text")), None)
            if not text:
                raise ValueError("Gemini response did not contain text")
            return text
        except HTTPError as exc:
            # A missing/unsupported model can be retried using a known model.
            try:
                api_detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                api_detail = ""
            errors.append("%s: HTTP %s %s" % (model, exc.code, api_detail))
            # Try a small number of alternate models for model-specific quota/availability issues.
            # If all fail, main.py can still create safe filename-based metadata and continue.
            if exc.code not in (400, 404, 429):
                raise RuntimeError("Gemini API request failed (%s)" % exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Gemini network request failed: %s" % type(exc).__name__) from exc
    raise RuntimeError("No configured Gemini model worked (" + ", ".join(errors) + "). Check model access and API key.")


def generate(cfg, channel, filename, best, worst):
    """Generate metadata with Gemini only; do not silently publish fallback metadata."""
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to GitHub Actions secrets.")
    return _parse(_gemini(_prompt(channel, filename, best, worst)))


def template_meta(niche, filename=""):
    """Explicit offline helper; daily publishing does not use this fallback."""
    topic = _clean_topic(filename) if filename else niche.title()
    words = re.findall(r"[A-Za-z0-9]+", (topic + " " + niche).lower())
    tags = list(dict.fromkeys([w for w in words if len(w) > 2] + ["facts", "shorts"]))[:15]
    hashtags = ["#Shorts"]
    for tag in tags:
        if tag in {"facts", "science", "technology", "tech", "ai", "space", "history", "nature"}:
            hashtags.append("#" + tag.capitalize())
        if len(hashtags) >= 5:
            break
    if len(hashtags) < 3:
        hashtags.extend(["#Facts", "#LearnSomethingNew"])
    title = topic if topic.lower().endswith("#shorts") else topic + " #Shorts"
    description = (
        "Discover: %s.\n\n"
        "Follow FACTORA MINDS for more interesting facts and explainers. "
        "Like and subscribe for more videos.\n\n%s"
    ) % (topic, " ".join(list(dict.fromkeys(hashtags))[:5]))
    return {"title": title[:100], "description": description[:5000], "tags": tags}
