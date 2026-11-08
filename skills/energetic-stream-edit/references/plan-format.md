# Plan format

A plan is one JSON file. Times are in seconds. Caption, title, flash and annotation times are relative to the **start of the clip**, not of the source. Unknown keys are ignored, so check spelling.

## Skeleton

```json
{
  "source": "/path/to/source.mp4",
  "start": 23.5, "end": 38.0,
  "words": "/path/to/captions.en.json3", "words_shift": -705.0,
  "captions": {"mode": "word", "size": 84, "y": 0.47, "style": "upright", "palette": "yellow-cyan", "per": 3},
  "title": {"lines": ["WILL HE WIN?", "FIND OUT"], "colors": ["white", "cyan"], "t0": 0.0, "t1": 2.0},
  "end_card": {"text": "THE RIVAL IS STILL SCARY", "dur": 1.3, "color": "green"},
  "focus": [{"t": 0, "x": 0.5, "y": 0.45}],
  "motion": {"rate": 0.01, "max_zoom": 1.6, "auto_punch": true, "flashes": [], "white_flash": []},
  "annotations": [],
  "sound": {"auto": {"title": true, "annotations": true, "flashes": true, "end_card": true}, "cues": []}
}
```

## Source and clip window

| Key | Default | Meaning |
|---|---|---|
| `source` | required | the video file |
| `start`, `end` | 0, full length | the clip window in the source |
| `focus` | centre | where the 9:16 window sits, as fractions `x`, `y` of the source, eased between keys |

## Words and captions

`words` is a json3 auto-caption file or a list of `{"w","s","e"}`. `words_shift` moves its times (seconds) so they match the clip's source timeline.

| Key | Default | Meaning |
|---|---|---|
| `captions.mode` | `word` if words are given, else `none` | `word` (one word at a time), `phrase` (2-3 words with the spoken one highlighted), `script`, `none` |
| `captions.size` | 84 | font size in pixels at 1080 wide |
| `captions.y` | 0.47 | vertical centre, fraction of the frame height (the references sit at 45-50%) |
| `captions.style` | `upright` | `upright`, `italic` or `impact` |
| `captions.palette` | `yellow-cyan` | `yellow-cyan` (yellow base, cyan emphasis) or `white-accent` |
| `captions.per` | 3 | words per phrase in `phrase` mode |
| `captions.glow` | false | neon glow behind the text |

Words are censored automatically (`F*ck`, `sh*t`, `a**`). Word colours follow the role of the word: cyan for emphasis words (NO, WAIT, WHAT and similar), green for positive words, red for danger words, the base colour otherwise.

**Script mode** writes the captions yourself, one entry per caption:

```json
"captions": {"mode": "script"},
"script": [
  {"t0": 1.0, "t1": 2.4, "text": "the girl {red|notices} *looks at her*"},
  {"t0": 2.6, "t1": 4.0, "text": "then {cyan|everything} moves"}
]
```

Markup: `{colour|WORDS}` sets a colour for that span, `*action text*` is pink and smaller, with the asterisks kept. Colour names: yellow, cyan, pink, red, green, white, orange.

## Title and end card

| Key | Default | Meaning |
|---|---|---|
| `title.lines` | required | one or two lines, shown at about 69% of the frame height |
| `title.colors` | white, cyan | colour of each line |
| `title.t0`, `title.t1` | 0, 2.0 | when it shows |
| `title.hide_captions` | false | hide captions while the title is up |
| `end_card.text` | none | the last line, shown over the last `dur` seconds, replacing captions |
| `end_card.dur` | 1.3 | seconds |
| `end_card.color` | green | colour |

## Motion

The picture moves in **jumps**: a zoom in or out of about 10% that happens in one frame, every one to two seconds, placed on the speaker's emphasis. A steady push-in is optional and small.

| Key | Default | Meaning |
|---|---|---|
| `motion.rate` | 0.01 | steady push-in per second (0 turns it off) |
| `motion.max_zoom` | 1.6 | cap on the zoom |
| `motion.punch_gain` | 0.10 | size of each jump |
| `motion.punch_mode` | `pulse` | `pulse` zooms in, then out, then in (what the references do); `ratchet` keeps going in |
| `motion.auto_punch` | true | place jumps on the speaker's loudest moments, filling any gap longer than about 2.9 s |
| `motion.punches` | none | explicit jump times (overrides auto) |
| `motion.gap`, `motion.min_gap` | 2.0, 1.5 | target spacing and minimum spacing of automatic jumps |
| `motion.cuts` | none | hard cut times; framings alternate close and wide |
| `motion.cut_alt` | 1.22 | the close framing's zoom |
| `motion.bursts` | none | `[{"t": 5.0, "n": 4, "span": 0.5}]`: four quick cuts inside half a second (a laugh peak) |
| `motion.flashes` | none | `[{"t": 6.0, "color": "green", "dur": 0.4, "peak": 0.45}]`: a colour flash that fades |
| `motion.white_flash` | none | list of times for a white flash (0.12 s) |
| `motion.grade` | 0 | warm grade, 0 to 1 |
| `motion.shake` | 0 | a small wobble after each jump (0 is off) |

## Annotations

Each item is one of four types. Circles, arrows and emoji are drawn on the picture and follow the zoom (`space: "source"`). Windows are drawn on the frame (`space: "screen"`).

```json
"annotations": [
  {"type": "circle", "at_word": "scary", "dur": 1.7, "x": 0.505, "y": 0.365, "rx": 0.042, "ry": 0.07},
  {"type": "arrow", "t0": 6.0, "dur": 1.6, "x0": 0.80, "y0": 0.52, "x1": 0.575, "y1": 0.40},
  {"type": "emoji", "at_word": "fighting", "char": "🥊", "x": 0.17, "y": 0.26, "size": 0.17, "space": "screen"},
  {"type": "inset", "t0": 12.2, "dur": 2.4, "src": "/path/to/real-screenshot-or-clip.mp4", "ss": 9.0, "label": "THE FIGHT", "x": 0.5, "y": 0.19, "w": 0.62}
]
```

- `at_word` starts the item on that spoken word (`lead` shifts it, `occurrence` picks a repeat). Without it, use `t0`.
- Circles take `r` or `rx`/`ry`, as fractions of the picture width. Arrows take `x0,y0` (tail) and `x1,y1` (head); `bend` curves the shaft.
- An **inset** shows a real image or video file (`src`). It is the only way to show a chat, a phone or a page. Use real files the user has permission to use; never build one.

## Sound

```json
"sound": {
  "kit": "assets/sfx_kit",
  "auto": {"title": true, "annotations": true, "flashes": true, "end_card": true,
           "cuts": false, "caption_clicks": false, "annotation_kinds": ["pop", "click"]},
  "cues": [{"t": 8.6, "kind": "fakeout"}, {"t": 2.4, "kind": "click"}],
  "gain_db": {"impact": -3, "pop": -9},
  "duck_db": -3
}
```

- `auto` derives cues from the plan: title (impact), annotations (pop or click, alternating; windows get a whoosh), white flashes (whoosh), colour flashes (impact), end card (impact). `cuts: true` adds a click on each cut; `caption_clicks: true` adds one on each emphasised word.
- `cues` adds your own. Kinds: `impact`, `pop`, `click`, `whoosh`, `riser`, and `fakeout` (riser, 0.3 s of near silence in the original, then impact). `gap` changes the silence length of a fake-out.
- Gains are added to each clip's normalised level. The original audio dips only inside a fake-out and ducks 3 dB under loud effects.
- The JSON the render prints includes `sound.placements` (every cue, its time, kit file and gain) and `sound.dips`, so the user can check the timing.

## Render options

```bash
python3 -I scripts/render.py plan.json out.mp4 --lufs -12        # master to -12 LUFS, true peak limited at -1 dBTP
python3 -I scripts/render.py plan.json out.mp4 --peek 1.0,3.0    # PNG stills at those times, nothing encoded
```

The loudness stage is two-pass. It keeps the true peak under −1 dBTP (dynamic gain, then a limiter on a 4× oversampled grid, then a 48 kHz output), and after the encode the render measures the file and stops with an error if the true peak is above −1 dBTP. A quiet source needs a lot of gain, and that is the case the check exists for. Without `--lufs` the audio stays at the level it came in, and no ceiling is applied.
