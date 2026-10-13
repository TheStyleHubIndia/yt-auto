from googleapiclient.http import MediaFileUpload

def upload(yt, path, meta, publish_at_iso, category_id, tags, is_short):
    desc = meta.get("description", "")
    if is_short and "#Shorts" not in desc: desc += "\n\n#Shorts"
    body = {
        "snippet": {"title": meta["title"][:100], "description": desc,
                    "tags": (meta.get("tags") or []) + tags, "categoryId": category_id},
        "status": {"privacyStatus": "private", "publishAt": publish_at_iso,
                   "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]
