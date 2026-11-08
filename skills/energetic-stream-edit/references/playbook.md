# Playbook: how the energetic viral Shorts are edited

Measured on six public Shorts in October-November 2026. The method: every hard cut found from frame differences, every zoom found by matching image features between frames a fraction of a second apart, loudness with EBU R128, sound events from the spectrum, and a read of contact sheets and caption close-ups. The creators and titles are left out on purpose; the labels A-F stand in for them.

**What is measured and what is not.** Cuts, zoom, caption placement and loudness are numbers. Sound types (boom, click, riser) are guesses from the shape of the spectrum: nobody listened to them. Fonts are named by look only. How the editors worked is inferred, not known.

## The six clips

| | Length | Type | Cuts per 10 s | Zoom jumps per 10 s | Loudness | True peak |
|---|---|---|---|---|---|---|
| A | 14 s | one take, word-by-word captions, a green colour flash | 2.2 | 2.2 | -12.8 LUFS | 0.0 dBTP |
| B | 34 s | one real event told by captions and B-roll, annotations | 1.8 | 7.3 | -10.3 LUFS | +0.4 dBTP |
| C | 25 s | one real event told by captions, a chat insert, circles | 2.8 | 0 | -12.5 LUFS | +0.8 dBTP |
| D | 17 s | voiceover over short clips, action text in asterisks | 2.3 | 8.1 | -12.9 LUFS | +1.4 dBTP |
| E | 37 s | fast multi-angle meme edit, reaction cutaways | 11.3 | 1.4 | -13.6 LUFS | +0.1 dBTP |
| F | 62 s | ranking template with a fixed frame and interstitial cards | 2.1 | 0 | -14.1 LUFS | 0.0 dBTP |

Every one is loud, between -10 and -14 LUFS, with peaks at or just over 0 dBFS. Most have one hard cut every 3-5 seconds, with the exception of clip E.

## Zoom and motion

- **Jumps, both ways.** Clips with a jump pattern show zooms in (median +4 to +18%) and out (median -4 to -12%), roughly every 1 to 2 seconds. Zooming only in runs out of room quickly.
- **Steady drift is rare.** Over one-second windows with no cut and no jump, five of six clips drift about 0% per second; one drifts about 2% per second. An earlier reading of "2-4% per second everywhere" was measurement noise: per-step zoom jitter is about ±0.2% per 1/15 s, so drift must be read over windows a second or longer.
- **Bursts.** At a laugh peak, one clip cuts three or four times inside half a second (shots as short as 0.03 s).
- **Hard cuts between framings.** Clip E alternates a wide shot, a close-up and an audience reaction, with a cut every 0.9 s on average.

## Captions

- One or two words at a time in most clips, ALL CAPS, a heavy rounded sans with a thick black outline. A word is about a quarter of the frame width. Where the yellow captions could be measured (clips B and E), their centre sat at 49-50% of the height; the other two clips with yellow captions measured lower (D near 33%) or higher (C near 69%), so place captions by eye, not by a single rule.
- Captions are narration, not a transcript: third person, short, in the viewer's voice ("the girl notices the livestream").
- Colour by feeling: a yellow base, cyan for emphasis, pink or orange for action text in asterisks, green for a positive or funny word, red for danger.
- Bad words are masked (F*ck style) in every clip that carries speech.
- Clip D places action text in asterisks, small, in the upper middle, and a glow on the face at moments of intensity.

## Overlays and inserts

- **Red circles and arrows** on the thing being talked about: the face, the hand, the chat. They appear on the word, not before it.
- **Emoji** as small icons next to a named thing (a glove next to a fight, an ambulance next to an ambulance).
- **Windows**: a real screen recording or screenshot inserted with a short red label ("CHAT WARNING", a name), usually for 2 to 3 seconds. A window that shows something the viewer cannot otherwise see is what makes the clip work.
- **B-roll** of the thing named, for 1.5 to 3 seconds, cut in the moment it is named.

## Flashes and transitions

- A **white flash** (about 0.1 s) at a scene change.
- A **colour flash** (green or yellow, about 0.4 s, fading) on the punchline word.
- A **warm yellow-orange grade** over the whole clip in one case.

## Sound

Real recorded sound, not synthesised, and always the original audio kept.

- **Impact** on a title card, a reveal, a colour flash or an end line.
- **Small click or pop** on a caption pop or an annotation.
- **Fake-out**: a rising sweep, about 0.3 seconds of near silence, then the hit (clip A, at about 1.5-2.4 s).
- **Whoosh** with a flash transition.
- **Silence as an effect**: 0.2-0.3 seconds before a reveal, or at every card in the ranking template.
- **Regular beat** of low hits about every 1.15 seconds in the voiceover clip, lined up with clip changes.

Mastering: -10 to -14 LUFS, true peak at or just over 0 dBFS. The renderer targets -12 LUFS with a -1 dBTP ceiling, which sits in the middle of the range and gives headroom for the platform's own encode.

## End and title

- The end is a button line ("CHECK LINK IN BIO" style), on a black or flat card, not a fade.
- Titles are short and human: 3-9 words, one or two emoji, a claim or a feeling, no colon, no episode name.
- Two or three hashtags, in the title or the description.

## Five formats (pick one per clip)

1. **One real moment, word captions** (clip A): one continuous take, a punch on emphasis, a colour flash on the punchline, a fake-out before the hit.
2. **A real event told by captions and B-roll** (B, C): cut on each named thing, a circle on what matters, a window for the proof.
3. **Fast multi-angle meme edit** (E): wide, close, reaction, repeat. Bursts at the peak. A call-to-action card at the end.
4. **Voiceover collage** (D): voiceover over one-to-two-second clips, action text, a steady beat of hits.
5. **Ranking template** (F): fixed frame with a banner and numbered list, a short tag per clip, an interstitial card with a deep impact between clips, then a click when the next clip starts.

## Checklist with the measured targets

| Check | Target | Source |
|---|---|---|
| Loudness | -10 to -14 LUFS | all six |
| True peak | 0 to +1.4 dBTP | all six |
| Zoom jump gap | 0.6 to 2 s | B, D, A |
| Jump size in / out | 4-18% / 4-12% | A, B, D, E |
| Cuts per 10 s | 2-3 (11 for the multi-angle edit) | five of six |
| Hook | text on frame 0 | four of six |
| Caption centre | 49-50% of height where measured | B, E (C and D measured elsewhere) |
| End line | a button, not a fade | five of six |

## What the study cannot show

- Why a clip goes viral. Six clips cannot separate the edit from the moment, the channel or the audience.
- What the sounds really are. Their types were inferred from spectra.
- The editors' software or fonts.
- Whether the loudness or the speed of cutting caused the views.
