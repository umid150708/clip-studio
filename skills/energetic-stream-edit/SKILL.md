---
name: energetic-stream-edit
description: Edit a clip into a loud, fast, energetic short in the style of viral stream and reaction Shorts. Use this skill whenever the user wants a high-energy, meme-paced vertical clip from a stream, reaction, podcast or event: colour-coded one-word captions, zoom jumps and punch-ins that keep the picture moving, hard cuts between framings, annotations (red circles, arrows, emoji, or a real screenshot or B-roll window with a label), flash transitions, real sound effects on the cues, a hot loudness master, a short emoji title and hashtags. Trigger on phrases like "energetic edit", "viral style short", "speed viral", "stream clip with sound effects", "colour captions", "make it punchier", "add zoom and sound effects", "make it look like the viral ones", even when the user does not name the style. Do NOT use it for the calm campaign look (no sound effects, head-tracked reframe, 3-second cutaways for a paid clipping brief); that belongs to podcast-clip-studio.
---

# Energetic stream edit

This skill makes **one short at a time** in a fast, colour-coded, sound-driven style. It was measured from six viral Shorts (see `references/playbook.md`), and the tools are a plan file plus a renderer that does the picture, the captions, the motion, the annotations, the sound and the loudness.

Two limits shape everything below. **The assistant cannot hear audio**, so every sound choice is made from measurements and the user has to listen. And **the source is somebody else's footage**, so the rights rules in `podcast-clip-studio/references/footage-and-rights.md` apply.

## Rules (read first)

1. **Ask before you fetch, export or upload.** Downloading a source, a sound pack, or any export or upload needs a yes from the user first. Name the source, the size and the purpose. Local renders are free and fine to run for previews.
2. **Never draw a stand-in for something real.** A "chat window", a phone screen, a sign, a sound effect or a fight clip must be a real file the user supplies or a real recording from the kit. If the user asks for a chat screenshot and has none, ask for one. Do not build a fake interface, and do not synthesise a sound. The renderer refuses to fake a missing sound; if it says a kind is missing, tell the user and ask.
3. **Say what you could not check.** Measurements cover loudness, timing, zoom and framing. They do not cover taste. End with "play it once before you post it".
4. **Do not overclaim virality.** Six reference clips describe a style. They cannot show why a clip goes viral. Say so when the user asks for guarantees.
5. **Use only the files the user names.** Do not scan the user's folders, and do not read a file the user did not give you as the source.
6. **Keep the calm profile separate.** No sound effects in a campaign clip, and no viral-style colour captions in one, unless the user's brief says so.

## Workflow

### 1. Get the source and the moment
- Ask the user for the source file path (or a URL, with permission) and the start and end times. **Do not search the user's folders for a matching video.** A file that happens to match may not be the one the user means, and scanning folders they did not name is outside this skill's job. If no path is given, ask for it and stop.
- Read the transcript at the start and end before deciding, so the hook is the first line and the clip ends on a line that lands. **Quote the hook from the transcript or the spoken words.** If no transcript is given, ask for one and mark the hook as a placeholder; never write a hook as if the streamer had said it.
- A usable length is 14 to 37 seconds, the range the references use. Shorter needs a stronger hook.
- If the user wants word-timed captions, get a word-timed transcript (YouTube auto-captions in json3 work, and `words_shift` moves them to clip time).

### 2. Write the plan
Copy `references/plan-format.md` for every key. A plan is one JSON file: source, start, end, captions, title, end card, focus, motion, annotations and sound. Start with the smallest plan that works (captions and motion), then add annotations, then sound. Adding one layer at a time makes a failure easy to find.

### 3. Preview, then render
```bash
python3 -I scripts/render.py plan.json preview.mp4 --peek 1.0,3.0,6.5      # stills only, no encode: look at them first
python3 -I scripts/render.py plan.json out.mp4 --lufs -12                  # the real render
```
Look at the stills at the moments that matter: the hook, each annotation, each flash, the end card. Captions must sit in the middle of the frame and be readable at phone size. A caption that is cut off, or sitting on a face, is a plan change, not a render bug.

### 4. Measure
```bash
python3 -I scripts/measure.py out.mp4
```
It reports cuts per 10 seconds, zoom jumps in and out, the steady push-in, loudness, true peak and caption height, measured the same way as the six references. Compare with the ranges in `references/playbook.md`. Two things matter most: loudness between −10 and −14 LUFS, and true peak at or below −1 dBTP. The renderer checks the true peak after the encode and stops with an error above −1 dBTP, so a render that finished is under that ceiling. Also check a zoom jump every one to two seconds. If the numbers are off, change the plan and re-render; do not guess.

### 5. Title and hashtags
Write a short title with one or two emoji, and two or three hashtags, such as `#edit` plus one word about the topic. Put the title in the reply, not in the video.

### 6. Hand over
Report the file path, the measured numbers, what you could not check, and the `sound.placements` list the render prints, so the user knows which kit clip plays where. Offer one follow-up: a change list, or a second clip from the same source.

## Sound

The sound kit lives in `assets/sfx_kit/` (21 real CC0 clips with their sources in `kit.json`). `python3 -I scripts/mixer.py report` lists what it holds. Only one pop sound exists; annotation cues alternate between the pop and six clicks so it does not repeat. A plan that needs a kind the kit lacks stops with a message. Tell the user, and offer to fetch more sounds with `scripts/fetch_kit.py` after they say yes.

Every sound is placed on a cue: the title, each annotation, each white flash, colour flash and the end line. The fake-out (`{"kind": "fakeout"}`) is a riser, 0.3 seconds of near silence in the original audio, then a hit. Keep the fake-out to one per clip, on the line the clip is built around.

## Scripts

| Script | Use |
|---|---|
| `scripts/render.py` | plan.json to the 1080x1920 clip (`--peek` for stills, `--lufs` for the loudness master) |
| `scripts/measure.py` | the numbers that compare against the references |
| `scripts/captions.py`, `motion.py`, `annotations.py`, `mixer.py` | the layers; read the docstrings before changing a default |
| `scripts/kit_analyze.py`, `build_kit.py`, `fetch_kit.py` | measure a recording, cut kit clips, download approved sources |
| `scripts/selftest.py` | builds a throwaway clip with every feature on and measures it; run once after install |
| `scripts/test_*.py` | unit checks (`python3 -I scripts/test_captions.py`, and so on) |

## Requirements

- Python 3 with `numpy`, `opencv-python` and `Pillow`; `ffmpeg` and `ffprobe` on the PATH.
- The captions and emoji use macOS system fonts (Arial Rounded, Avenir Next, Apple Color Emoji). On another system, `captions.py` and `annotations.py` raise a message naming the font; point `FONTS` or `EMOJI_FONT` at an equivalent heavy rounded sans and an emoji font, or skip emoji annotations.
- Only tested on macOS (Apple silicon). Run `python3 -I scripts/selftest.py` after install to check your machine.

## Reference files

- `references/plan-format.md`: every plan key, its default and an example.
- `references/playbook.md`: the study, the measured numbers and the recipe. Read it before choosing settings.
- `references/sound-kit.md`: where each sound comes from, its licence, and how to add one.
