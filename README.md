# clip-studio

This repository holds one Claude Code skill, `podcast-clip-studio`.

It clips long podcasts, interviews and press conferences into vertical shorts, and was built while clipping real episodes for a paid campaign.

It finds the moments viewers actually replay, cuts a hook-first clip, reframes it with a head-tracking camera, adds relevant 3-second cutaways and burned-in captions, and runs a checklist before anything is exported. It pairs with Nate Herk's [herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) for the tight cutting and captioning steps.

## What it does

1. **Scores moments** from public data: timestamps people type in comments, the "most replayed" heatmap, laughter in the comments, and a sponsor-read filter (`scripts/find_moments.py`).
2. **Downloads only the window** you approve (`scripts/fetch_window.sh`).
3. **Reframes** with a head-tracking camera that keeps the speaker's head centred and holds one person at a time when several are laughing (`scripts/facetrack.swift`, `scripts/reel.py`).
4. **Cuts away** to 5-7 relevant 3-second shots of what is being discussed.
5. **Assembles in Crayo** (API plus its advanced editor) or hands off to HyperFrames through the kit (`scripts/crayo.py`, `scripts/crayo_compose.py`).
6. **Verifies**: decode test, first and last frames, the picture changing every ~3.5 s, loudness, every caption read, bad words censored (`references/verification.md`).

## Install

```bash
git clone https://github.com/umid150708/clip-studio
cp -R clip-studio/skills/podcast-clip-studio ~/.claude/skills/
```

Optional but recommended: install [herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) so the `cut-silences`, `cut-mistakes` and `short-form-edit` skills are available.

## Requirements
- macOS for the face tracker (it uses Apple's Vision framework). Everything else is cross-platform in principle but was only run on macOS (Apple silicon).
- `ffmpeg`, `yt-dlp` (kept current), `node` (YouTube's JavaScript checks), Python 3 with `numpy`, `opencv-python` and `Pillow`.
- Optional: a Crayo account and API key (`bash scripts/save-crayo-key.sh`). Crayo costs credits; the skill asks before spending any.

## Use it
Ask Claude something like:
> Clip the best 30-second moments from this episode: https://youtube.com/watch?v=...

The skill will look up the moments, show you a ranked table, and wait before downloading anything.

## What was tested
Every script in `scripts/` was run against real episodes during development, and the Crayo steps against a real account. What was **not** verified: other operating systems, other Crayo plans, and the audio of any export (the assistant cannot listen, so a human should play each clip once).

## Rights
Clipping is only as clean as your permission to clip. Use sources you are allowed to use, credit them, flag any third-party footage, and never use another person's face or branding as your channel's identity. See `references/footage-and-rights.md`.

## Licence
MIT for the original material in this repository (see `LICENSE`). `NOTICE.md` lists the tools and projects it works with.
