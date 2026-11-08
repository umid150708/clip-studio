---
name: podcast-clip-studio
description: Turn long podcasts, interviews and press conferences into finished vertical shorts for clipping campaigns. Finds the moments viewers actually replay (comment timestamps, the "most replayed" heatmap, laughter), cuts a hook-first clip, reframes with a head-tracking camera, adds relevant 3-second cutaways and burned-in captions, and verifies the result before anything is exported. Use when asked to clip a podcast or interview, make Shorts, Reels or TikToks from someone else's long video, find the best moments in an episode, or edit for a paid clipping campaign. Pairs with the herk-edit-kit skills (cut-silences, cut-mistakes, short-form-edit) for the cutting and captioning steps.
---

# Podcast clip studio

This skill clips **other people's long shows**: a guest on a podcast, a press conference, an interview. It decides which 20-60 seconds are worth cutting, makes the clip, and checks it. The herk-edit-kit skills edit **the user's own recordings**. The two meet in the middle: this skill finds and frames the moment, then hands the tight cutting and captioning to the kit when it is installed (see "Working with herk-edit-kit").

Everything here comes from clipping real episodes for a paid campaign. Where something is unverified, it says so.

## Rules for the assistant (read first)

These exist because the user's time and usage limit are limited.

1. **Ask before you spend or fetch.** Always ask before a download (name the source, the window and the size), before spending any credits (Crayo, AI image tools), before uploading into the user's accounts, and before any export. Never post or publish a clip.
2. **Use the exact thing the user names.** If they name a sound, an app screen, a clip, a font or a tool, find that real thing and use it. Do not draw a lookalike from memory or synthesise a stand-in. If you cannot find it, say so and ask.
3. **Local first.** Rendering on the user's machine is free. Use a paid tool once per clip, after inspecting the project, not as a way to experiment.
4. **Verify with evidence.** Look at frames, measure audio, read every caption. You cannot hear audio, so say that, and say what you could not check.
5. **No guessing at facts.** Look up the spec, the licence or the timestamp. State what you used.

## Pipeline

### 1. Read the brief
Get the campaign brief or the user's goals. Typical constraints: 9:16, 20-60 s, the hook inside the first 2 seconds, word-by-word captions burned in, no other editors' watermarks, one hot take or one story or one argument per clip, a minimum number of clips per week. Ask which source channels are allowed.

### 2. Find sources
Prefer the rightsholder's own channels, and prefer **recent** shows over old ones. Prefer famous guests and funny or happy moments over heavy ones. List a channel's uploads with `yt-dlp --flat-playlist --print "%(id)s | %(duration_string)s | %(title)s"`. Check the upload date: a "podcast" may have ended a year ago.

### 3. Score the moments
```bash
printf '%s\n' ID1 ID2 ID3 | xargs -P 3 -n 1 bash scripts/fetch_meta.sh      # comments + replay heatmap + captions, metadata only
python3 -I scripts/find_moments.py meta subs moments.json [--bonus ID=1.5:Guest] [--ad SponsorWord]
```
It combines the timestamps people type in comments (weighted by likes), the "most replayed" peaks, the share of comments with laughter, and a sponsor-read filter. A high score means "look here", not "clip this". **Read the transcript at that spot** (`scripts/window.py subs ID 1230 1290`) before deciding. More in `references/find-moments.md`.

### 4. Choose the clip and show the user
Choose one hot take, one story or one argument. The first line is the hook; cut everything before it. End on the line that lands. Start on a word that begins cleanly (see "Pitfalls": captions are recognised from the audio, and a cut that starts mid-word gets misheard).

Show the user a ranked table: clip, in and out times, the hook line, the evidence, and flags (sponsor read, brand risk, speaker unclear, third-party footage). Wait for a choice.

### 5. Download only the window
After approval: `bash scripts/fetch_window.sh VIDEO_ID START-END NAME`. Pad 10-20 s each side. `DRY=1` checks the video without downloading. Keep yt-dlp up to date; old builds get HTTP 403.

### 6. Transcript and a tight cut
Word-level timing is the base for everything. YouTube's auto-captions (`json3`) work and are free; the kit's transcription skills are more accurate. Cut dead air and filler by using the kit's **cut-silences** and **cut-mistakes** on the clip, or `reel.py`'s built-in tightening. Cut between phrases, never inside one.

### 7. Reframe with a head-tracking camera
```bash
bash scripts/build_facetrack.sh          # macOS only: compiles scripts/facetrack.swift (Apple Vision, no downloads)
./facetrack segments/01.mp4 faces/01.json 10
```
The **head-tracking effect** means the speaker's head stays locked in the centre of the 9:16 frame while the background slides around them. `reel.py` does this with almost no lag and picks **one** person to follow: when several people are laughing it stays on one for at least 1.5 s before it may switch. Details in `references/edit-rules.md`.

### 8. Cutaways
Put 5-7 cutaways of about 3 seconds each through the clip, each one relevant to the words being said, with the original audio running underneath and the captions still on top. Show the thing being discussed, and show the **action**, not the ceremony (the punches, not the referee raising an arm). Research the buzz first (comments, Reddit, news) so the footage matches how people felt. Preview every crop before rendering: `python3 -I scripts/reel.py --plan plan.json --out x.png --peek`. Never put a cutaway over the first 2 seconds. Details and rights in `references/footage-and-rights.md`.

### 9. Captions and a title card
Two routes:
- **Crayo** (API plus its advanced editor): `reel.py --plain` renders the head-tracked picture, the narration and each cutaway as separate files; `crayo_compose.py` assembles one Crayo project with captions and a title card. See `references/crayo.md`.
- **HyperFrames**: hand the cut clip to the kit's `short-form-edit` skill.

Caption rules: 2-4 words at a time, high contrast, burned in. Anything the viewer must read (a typed message, a title) goes **above** the caption zone, which sits at roughly 81-89% of the frame height. **Censor profanity** (F*ck, sh*t, a**). Captions come from speech recognition, so read every line. Fix a wrong word in the editor's caption text box, not by regenerating, because regenerating costs credits and undoes other fixes.

### 10. Verify before saying "ready"
Run the checks in `references/verification.md`: decode test, first and last frames, the final word not clipped, the picture changing at least every ~3.5 s (`scripts/stillness.py`), loudness near -16 LUFS, every caption read, no bad words, hook inside 2 s, length and aspect ratio.

### 11. Hand over
Give the user the files plus a notes file: the post title for each clip (name first, ALL CAPS, one emoji at the end), the hook, the source episode, and every piece of third-party footage with its source. The user decides whether to export and post.

## Style profiles
- **Campaign profile (default here):** head-tracking, 5-7 cutaways, no sound effects, no music, voice only, captions burned in.
- **Kit house style:** if the user wants music and synchronised sound effects, follow the kit's `short-form-edit` playbook instead. The user's brief always wins.

## Working with herk-edit-kit
Install it from https://github.com/nateherkai/herk-edit-kit (MIT; its brand assets are not for reuse). This skill does not copy any of its files.

| Step | Use |
|---|---|
| Find and choose the moment, download the window | this skill |
| Remove pauses and dead air | kit: `cut-silences` |
| Remove stutters and false starts (review-gated) | kit: `cut-mistakes` |
| Hook, payoff and pacing judgement | kit: `short-form-edit` |
| Head-tracking reframe, cutaways, Crayo assembly | this skill |
| Motion graphics and HyperFrames render | kit: `hyperframes`, `short-form-edit` |
| Final checks | `references/verification.md` |

## Pitfalls that cost time
- **Captions from audio:** a clip that begins mid-word gets the word misheard ("titanium jaw" became "THIS. JAR"). Start on a clean word or a little earlier.
- **Crayo AutoClip** cannot take timestamps (only a 500-character prompt) and fails with "no moment strong enough" on a hand-spliced source. Give it the uncut window and trim the export.
- **Crayo's first 2-3 exported frames can be garbled.** `scripts/fix_start.sh` holds one clean frame over them.
- **Crayo allows one request at a time** per account; the client retries.
- **Replay spikes can be ads.** Check the words before trusting a peak.
- **YouTube rate-limits caption downloads (HTTP 429).** `scripts/retry_subs.sh` retries every 4 minutes. Age-restricted videos hide their comments.
- **ffmpeg may lack `drawtext`** (common Homebrew build). Draw text with Pillow.
- **Shell traps:** zsh errors on an unmatched glob; BSD `xargs -I` has a short command limit, so use a script with `-n 1`.
- **Never click "Create subtitles"** in Crayo's editor to "refresh" captions. It regenerates all of them and spends credits.
- **A scene with its own animation** (a typing screen) is flagged by `stillness.py` even though it moves. Judge those by eye.
