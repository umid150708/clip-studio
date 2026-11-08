# Crayo: what is verified

Crayo is an AI video editor with a public REST API and a browser editor. This file records what was observed while using it. Check https://crayo.ai/docs (and `https://crayo.ai/docs/openapi.json`) before relying on any number; plans and prices change.

## Setup
- Base URL `https://api.crayo.ai`, header `Authorization: Bearer crayo_sk_...`. Create a key on the Developers page.
- Save the key with `bash scripts/save-crayo-key.sh` (hidden prompt, file mode 600, `~/.config/podcast-clip-studio/crayo.env`). A key pasted into a chat is exposed: ask the user to rotate it afterwards. The assistant should not type a user's key into anything; the user saves it.
- A paste into a terminal can double the key (82 characters instead of 41). The client reports "Invalid, expired or revoked API key" in that case.
- Free accounts return HTTP 402 on anything that costs credits.

## Costs seen (Hobby plan)
- Uploads, imports, project creation, polling, listing: free.
- AutoClip: 1 video credit per requested clip, minimum 2 per job.
- Export: 1 export credit per second of finished video.
- Captions on a project: 1 voiceover credit per second of **narration**. Patching a project's scenes does **not** re-bill captions.
- Transcripts API (word timings of a finished file): 1 voiceover credit per second.
- Check `python3 -I scripts/crayo.py account` before and after any paid step and report the difference. If the numbers moved and you did not spend, say that something else changed them.

## AutoClip
`POST /v1/autoclip` takes `asset_id`, `clip_count` (2-20), `clip_length` (30, 60 or 90), `edit_level`, `formats`, `prompt` (500 characters, steers the moment), `mode`, `language`. It takes **no start or end times**. Source length 1 minute to 3 hours.

Layouts (`formats`) as rendered:
- `split` and `black-box`: a real face-tracked, full-bleed 9:16 crop with captions.
- `title-subtitles` and `full-video`: the wide 16:9 frame letterboxed in the middle of the vertical canvas. Not what a "chest-up" brief wants.
- Several formats at once: a blurred fill band.

It returns "no moment strong enough to stand alone" on a hand-spliced source. Feed it the uncut window and trim the export.

## Building a project yourself (what `crayo_compose.py` does)
1. `reel.py --plain` writes the head-tracked picture (no captions), the narration (`.narration.mp3`), and every cutaway as its own 9:16 clip.
2. Upload them (a signed-URL upload; cached by path, size and time so nothing is uploaded twice).
3. `POST /v1/projects` with `scenes` (picture and cutaway slices, `volume: 0`), `narration`, `subtitles` (`style_id`, `position: bottom`) and `texts` (the title card).
4. Open the project in the **advanced editor** (`crayo.ai/edit/<id>`) and inspect. Then export once: `crayo.py export <id> --out dir --yes`.
5. `fix_start.sh` holds one clean frame over the garbled first frames.

Scene files must be at least as long as their slot; the script checks. A project's `PATCH` replaces scenes in place, which avoids piles of duplicate projects.

## Editing captions in the editor
Select a caption block on the timeline, open **Edit Caption > This line**, click the text box, select all, type the corrected line. Keep the same word count so the timing holds. Wait for the "All changes saved" indicator before leaving the page. Do not use "AI subtitles > Create subtitles": it regenerates every caption and spends credits.

## Timing quirks
- One request in flight per account for uploads and project calls (HTTP 429 `CONCURRENT_REQUEST`); the client waits and retries.
- The file host rejects Python's default user agent with 403; the client sends its own.
- Rate limits are about 2 requests/second per key.
