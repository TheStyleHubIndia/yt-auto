# FACTORA MINDS — Drive to YouTube Shorts Automation

This repository checks a Google Drive folder daily, generates English metadata (Gemini when configured; otherwise a basic template), uploads one Short, schedules it, and moves the source video to an Uploaded folder. It uses the YouTube Data API and Google OAuth; **fully automatic uploading is not possible without YouTube authorization/API access**.

## Schedule
- Daily at **8:00 PM India time** (GitHub Actions cron: 14:30 UTC).
- One video per run by default.
- Use the **Actions → yt-auto → Run workflow** button for a manual run.
- Check the Actions run logs before assuming an upload succeeded.

## One-time setup

### 1. Google Drive folders
- Ready/source folder ID is already set to `19Fcgbj8SAo6kqAOOCRf0KDTTThj7xR_C`.
- Create a second Drive folder named `Uploaded`; copy its folder ID from the URL. The automation moves successfully uploaded videos there.
- Ensure the Google account used for OAuth can access both folders.

### 2. Google Cloud OAuth
1. Open Google Cloud Console and select/create a project.
2. Enable **YouTube Data API v3**, **YouTube Analytics API**, and **Google Drive API**.
3. Configure OAuth consent screen. Add your Google account as a test user if the app is in Testing.
4. Create an OAuth Client ID of type **Desktop app** and download its JSON file.
5. On a computer with Python installed, put that file in this repo folder as `client_secret.json`, then run:
   ```bash
   pip install -r requirements.txt
   cp config.example.yaml config.yaml
   # edit config.yaml and set drive_uploaded_folder_id
   python main.py auth channelA
   ```
   Sign in using the exact Google/YouTube account that owns the FACTORA MINDS channel. This creates `tokens/channelA.json`.
6. Do not commit either JSON file to GitHub.

### 3. Add GitHub Actions secrets
Open **GitHub → TheStyleHubIndia/yt-auto → Settings → Secrets and variables → Actions → New repository secret**. Add:

- `CLIENT_SECRET_JSON`: entire contents of downloaded `client_secret.json`.
- `TOKEN_CHANNELA_JSON`: entire contents of `tokens/channelA.json`.
- `CONFIG_YAML`: entire contents of your edited `config.yaml`.
- `GEMINI_API_KEY` (optional): Gemini API key for generated titles, descriptions and hashtags. If omitted, basic template metadata is used.

Never paste these secrets into chat or commit them to the repository. If you rotate OAuth credentials/token, update the matching GitHub secret.

### 4. Test before relying on the schedule
1. Open the **Actions** tab and select **yt-auto**.
2. Click **Run workflow**.
3. Open the latest run and read the logs. Confirm it says the video was scheduled and shows a YouTube URL.
4. Confirm the source video moved to the Uploaded folder and verify its scheduled date/time in YouTube Studio.

## Optional per-video metadata
Place a JSON file next to a video in the Ready folder with the same base filename, for example `clip01.json` for `clip01.mp4`:
```json
{"title":"A surprising AI fact","description":"A short, accurate explanation.\n\n#Shorts #AI #Facts","tags":["AI","facts","technology"]}
```
This overrides generated metadata fields you provide.

## Important limitations
- GitHub Actions is free within applicable usage limits; Google API quota and account restrictions still apply.
- YouTube may initially keep API-uploaded videos private until the API project meets YouTube's audit requirements.
- Scheduled publish time is selected from the configured slots; test timezone and scheduling in YouTube Studio.
- Only upload videos you own or have permission to use. Avoid misleading metadata, repetitive mass uploads, and unlicensed material.
