# YouTube Multi-Channel Automation

## Setup (ek baar)
1. console.cloud.google.com -> naya project -> enable: YouTube Data API v3,
   YouTube Analytics API, Google Drive API.
2. OAuth consent screen + "Desktop app" OAuth client -> `client_secret.json` download karo.
3. `pip install -r requirements.txt`
4. `cp config.example.yaml config.yaml` aur channels/folder IDs bharo
   (folder ID = Drive folder URL ka last part).
5. Har channel ke liye: `python main.py auth channelA`
   (consent screen pe wahi channel/brand account chuno). VPS pe ho to laptop pe
   auth karke `tokens/` folder copy kar do.
6. Drive `ready` folder me video daalo. Optional: same naam ka `.json`
   `{"title": "...", "description": "...", "tags": []}`.

## Chalana
- `python main.py run`      -> har channel ka 1 video schedule karta hai
- `python main.py report`   -> slot-wise performance
- Cron (har 6 ghante): `0 */6 * * * cd /path/yt_auto && python main.py run`
- ANTHROPIC_API_KEY set karo to titles Claude generate karega, past winners se seekhkar.

## Seekhne ka tareeka
- Upload `private + publishAt` se schedule hota hai (quota bachta hai, exact time pe live).
- 48h baad views x retention se score banta hai.
- Slot choose: pehle har slot 3 baar test, phir best slot (80%) + explore (20%).
- Best/worst titles agle title generation prompt me jaate hain.

## Dhyan
- Upload = 1,600 quota units; default 10k/day => ~6 uploads/day/project.
- Unverified API project ke uploads private lock ho sakte hain: audit form bharo.
- YouTube Analytics API me hour-of-day nahi milta, isliye slots experiment se seekhe jaate hain.
- Sirf original, unique content. Mass-produced/duplicate pe monetization hat sakta hai.
