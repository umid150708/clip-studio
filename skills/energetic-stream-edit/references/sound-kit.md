# Sound kit

`assets/sfx_kit/` holds 21 short clips cut from real recordings. Nothing in it is synthesised, pitched or sped up. Each clip has its licence and source URL in `kit.json`, and `mixer.py` refuses to load a clip without both.

## Source

All the recordings come from the Internet Archive's **SSE Library** (the USC Optical Sound Effects Library, digitised from tapes; uploaded to the archive by Jason Scott). The archive's metadata for each item states **CC0 1.0 Universal** (public domain dedication, `https://creativecommons.org/publicdomain/zero/1.0/`). The file-level list with checksums is in `assets/sfx_kit/download_plan.json`, and the per-clip provenance is in `kit.json`.

Clips were chosen by measurement (`kit_analyze.py`: length, attack, peak, decay, and whether a riser really gets louder and brighter), then checked against the expectations for their kind (`build_kit.py`). Nobody has listened to the clips. Listen before you rely on them.

## What is in the kit

| Kind | Clips | Source recording |
|---|---|---|
| impact | 5 | four explosions (dull, heavy sharp with reverb, two heavy) and a fist crack |
| pop | 1 | a cartoon cork pop |
| click | 6 | single clicks cut from one "metal clicks, several takes" recording |
| whoosh | 6 | two firework swooshes, three processed swishes, one door swish |
| riser | 3 | a spaceship takeoff in two lengths, and a short magneto swell |

Left out after measurement: a "punch and body fall" (its loudest point comes 0.8 s in, too slow for an impact), a long "rising machine" recording (it rises about 8 dB over 54 seconds, so no 1-2 second cut rises), and a "gathering storm" rumble (it gets quieter). They stay in the archive's raw files, not in the kit.

## Rules for the kit

- **Only real recordings.** A sound that is not a recording of a real thing is not allowed in the kit, and the mixer refuses a kind it does not have.
- **Every entry needs `file`, `license` and `url`.** `mixer.py` raises an error for an entry without them.
- **Cuts only.** A kit clip is a start, an end, a short fade-in against clicks, and a fade-out. No pitch change, no speed change, no layering.
- **Use it for the energetic profile only.** Campaign clips with a no-sound-effects brief do not use it.

## Rebuilding the kit from source

The raw archive files (11.3 MB) are not in this repository. To rebuild, run `python3 -I scripts/fetch_kit.py --yes` first (it reads `assets/sfx_kit/download_plan.json`, checks each file's md5, and writes `assets/sfx_kit/raw/`), then `python3 -I scripts/build_kit.py`. Using the kit as shipped needs nothing extra.

## Adding a sound

1. Find a recording with a licence that allows commercial use and remixing without credit or with credit you can state. Record its page URL and licence text.
2. Ask the user before downloading (name the source, the size and the reason).
3. Add the file to `download_plan.json` (name, size, md5 if the archive gives one), fetch it with `python3 -I scripts/fetch_kit.py --yes`, and check the checksum.
4. Add a cut to `cuts.json` and run `python3 -I scripts/build_kit.py`. A clip that fails its check is dropped and reported.
5. `python3 -I scripts/mixer.py report` shows the result. Listen to it before you use it.

## Mixer behaviour

- A clip lands on its cue by the anchor in `kit.json`: `onset` (the first audible sample, the default), `peak` (the loudest point, for whooshes that swell into a flash) or `end` (the last audible sample, for risers that must finish on the cue).
- Each clip is normalised to -3 dBFS peak, then the cue's gain is added (impact -3 dB, pop -9, click -13, whoosh -6, riser -7), with ±1 dB of random variation so repeats do not sound identical.
- The same clip is never used twice in a row.
- A fake-out dips the original audio by about 40 dB during the gap, with 10 ms ramps, so the silence is clean.
