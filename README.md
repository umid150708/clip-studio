# clip-studio

This repository holds two Claude Code skills, both for making vertical shorts from long video.

| Skill | For | Style |
|---|---|---|
| `podcast-clip-studio` | clipping podcasts, interviews and press conferences for a paid campaign | calm, head-tracked reframe, 3-second cutaways, no sound effects |
| `energetic-stream-edit` | viral-style shorts from streams, reactions and events | loud, colour-coded captions, zoom jumps, annotations, real sound effects |

The first finds the moments viewers replay, cuts a hook-first clip, reframes it with a head-tracking camera, adds relevant 3-second cutaways and burned-in captions, and runs a checklist before anything is exported. It pairs with Nate Herk's [herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) for the tight cutting and captioning steps.

The second was measured from six viral Shorts (cuts, zoom jumps, loudness, caption placement). It renders a plan file into a 1080x1920 clip with its own caption, motion, annotation, sound and loudness tools, and includes a self-test that builds and measures a throwaway clip.

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
cp -R clip-studio/skills/energetic-stream-edit ~/.claude/skills/
python3 -I ~/.claude/skills/energetic-stream-edit/scripts/selftest.py     # optional: checks the second skill on your machine
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

For the energetic style:
> Make an energetic stream-style short from this clip, with coloured captions, zoom jumps and sound effects. Show me the plan before rendering.

The second skill cannot hear audio, so play each clip once before posting.

## What was tested
Every script in `scripts/` was run against real episodes during development, and the Crayo steps against a real account. `energetic-stream-edit` was tested on synthetic footage and its own sound kit: unit checks, a self-test that renders and measures a clip with every feature on, and a fresh-copy run. What was **not** verified: other operating systems, other Crayo plans, and the audio of any export (the assistant cannot listen, so a human should play each clip once).

## Rights
Clipping is only as clean as your permission to clip. Use sources you are allowed to use, credit them, flag any third-party footage, and never use another person's face or branding as your channel's identity. See `references/footage-and-rights.md`.

## Licence
MIT for the original material in this repository (see `LICENSE`). `NOTICE.md` lists the tools and projects it works with, and the sound recordings in `energetic-stream-edit`, which are CC0 public domain.
