# FACTORA MINDS — Drive to YouTube Shorts Automation

This repository is configured to check Google Drive daily, schedule up to **3 Shorts per day**, generate metadata, analyze older uploads, learn which publishing slots perform better, and move successfully uploaded source videos to an Uploaded folder. It uses YouTube Data API and Google OAuth; automatic uploading requires that authorization to be completed.

## Schedule and learning
- GitHub Actions runs daily at **8:00 PM India time** (14:30 UTC).
- Each run attempts to schedule 3 videos in **three distinct configured time slots**, subject to videos being available, valid future slots, YouTube API quota, and successful authorization.
- Starting slots are test candidates, not a guarantee of peak audience times. The learner uses channel analytics from videos at least 48 hours old to compare performance and gradually favor better-performing slots.
- Analytics are refreshed on each daily run. The local `data.db` stores views, average view duration, average view percentage, minutes watched, score, and selected slot; the workflow commits this state back to the repository.
- To inspect analytics, open Actions → yt-auto → latest run logs. For a manual run, select **Run workflow**.
- YouTube Studio → Analytics → Audience → “When your viewers are on YouTube” is the best first-party reference for audience activity when enough data is available: https://support.google.com/youtube/answer/9314416

## One-time setup

### 1. Google Drive folders
- Ready/source folder ID: `19Fcgbj8SAo6kqAOOCRf0KDTTThj7xR_C`.
- Create a second Drive folder named `Uploaded`; copy its folder ID from the URL and replace `UPLOADED_FOLDER_ID` in `config.yaml`.
- Ensure the Google account used for OAuth can access both folders.

### 2. Google Cloud OAuth
1. Open Google Cloud Console and select/create a project.
2. Enable **YouTube Data API v3**, **YouTube Analytics API**, and **Google Drive API**.
3. Configure the OAuth consent screen. Add your Google account as a test user if the app is in Testing.
4. Create an OAuth Client ID of type **Desktop app** and download its JSON file.
5. On a computer with Python installed, place it in the repo folder as `client_secret.json`, then run:
   ```bash
   pip install -r requirements.txt
   cp config.example.yaml config.yaml
   # edit config.yaml and set drive_uploaded_folder_id
   python main.py auth channelA
   ```
   Sign in with the Google account that owns/manages the FACTORA MINDS YouTube channel. This creates `tokens/channelA.json`.
6. Never commit OAuth JSON files or tokens to GitHub.

### 3. Add GitHub Actions secrets
Open **Settings → Secrets and variables → Actions → New repository secret** in this repository and add:
- `CLIENT_SECRET_JSON`: entire contents of downloaded `client_secret.json`.
- `TOKEN_CHANNELA_JSON`: entire contents of `tokens/channelA.json`.
- `CONFIG_YAML`: entire contents of edited `config.yaml`.
- `GEMINI_API_KEY` (optional): Gemini key for AI-generated title, description and hashtags. Without it, basic template metadata is used.

Do not paste secrets into chat or commit them to the repository.

### 4. Test
1. Open the Actions tab and select `yt-auto`.
2. Click **Run workflow** and inspect logs.
3. Confirm three videos are scheduled (or read the exact reason fewer were scheduled).
4. Verify the scheduled dates in YouTube Studio and that processed videos moved to Uploaded.

## Optional per-video metadata
Place a JSON file next to a video with the same base filename, e.g. `clip01.json` for `clip01.mp4`:
```json
{"title":"A surprising AI fact","description":"A short, accurate explanation.\n\n#Shorts #AI #Facts","tags":["AI","facts","technology"]}
```
Fields supplied in this file override generated metadata.

## Important limitations
- Three uploads per day are a target, not guaranteed; Drive files, API quota, OAuth, upload limits, and configured slots can affect the count.
- YouTube Analytics data can be delayed. The learning loop only evaluates videos at least 48 hours old and adapts based on the data returned.
- Peak times vary by audience. Initial slots are hypotheses; validate them against YouTube Studio audience activity and actual video performance.
- API-uploaded videos may be restricted to private visibility until the API project meets YouTube's audit requirements.
- Upload only content you own or have permission to use. Avoid misleading metadata, repetitive mass uploads, and unlicensed material.
