import io, json, os, tempfile
from googleapiclient.http import MediaIoBaseDownload

def next_video(drive, folder_id):
    q = f"'{folder_id}' in parents and trashed=false and mimeType contains 'video/'"
    r = drive.files().list(q=q, orderBy="createdTime", pageSize=1,
                           fields="files(id,name)").execute()
    return (r.get("files") or [None])[0]

def sidecar_meta(drive, folder_id, video_name):
    """Optional: 'myvideo.json' (title/description/tags) video ke saath folder me rakho."""
    base = os.path.splitext(video_name)[0]
    q = f"'{folder_id}' in parents and trashed=false and name='{base}.json'"
    r = drive.files().list(q=q, fields="files(id)").execute().get("files", [])
    if not r: return {}
    return json.loads(drive.files().get_media(fileId=r[0]["id"]).execute())

def download(drive, file_id, name):
    path = os.path.join(tempfile.gettempdir(), name)
    with io.FileIO(path, "wb") as fh:
        dl = MediaIoBaseDownload(fh, drive.files().get_media(fileId=file_id), chunksize=50*1024*1024)
        done = False
        while not done: _, done = dl.next_chunk()
    return path

def move(drive, file_id, from_folder, to_folder):
    drive.files().update(fileId=file_id, addParents=to_folder,
                         removeParents=from_folder, fields="id").execute()
