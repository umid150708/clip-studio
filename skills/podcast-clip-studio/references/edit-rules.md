# Edit rules (the campaign profile)

These are the defaults. The user's brief overrides them. Each one came from a real correction.

## Hook and length
- The first spoken line is the hook. Nothing before it. No intro, no outro, no watermark of another editor.
- 20-60 seconds, 9:16, chest-up talking head.
- A title card (one line naming the moment) sits at the top for the first ~3 s.

## Head-tracking camera
- The speaker's head stays locked in the centre of the frame while the background and body move around it. No deadband, almost no lag (a damping constant near 0.05 s only removes detector jitter).
- The crop needs some zoom (at least ~1.2x) so it can also move vertically. Keep headroom: the head sits about 47% down the crop.
- **One person at a time.** When several people laugh, hold the same person for at least 1.5 s before switching, and only switch if another face has been clearly bigger for ~0.45 s or the tracked person left the frame. At a real cut in the picture, start fresh on the biggest face.
- Check by counting camera hops inside a shot: it should be about zero outside real cuts.

## The picture keeps changing
- Never more than ~3.5 s without a visible change: a speaker cut, a cutaway, or a zoom punch on emphasis (found from louder-than-surrounding words in the audio).
- Jump cuts inside one shot alternate a slight punch-in (about 7%) so they read as intentional.

## Cutaways
- 5-7 per clip, about 3 s each, spread through it. Relevant to the exact words. Never in the first 2 s. Captions stay on top. The speaker's audio keeps running.
- Show **action**: the fight, the knockout, the moment itself. Not ceremony (referee raising an arm, the crowd).
- 1080p or better, from the official source. Look at the frames first with `scripts/sheet.py`. Trim burned-in caption strips from old footage (`trim_top`, `trim_bottom` in the plan).
- When a cutaway illustrates something specific (a chat, a message, a document), recreate that specific thing from a real reference, not a generic stand-in. Label a recreation as one ("RE-ENACTMENT").

## Captions
- Burned in, 2-4 words at a time, high contrast, word by word. Crayo's "Black Caps" style (id 122) was used for this.
- Text the viewer must read goes above the caption zone (roughly 81-89% of the frame height).
- Profanity is censored in the style F*ck, sh*t, a**.
- Read every caption line against the audio. Fix errors in the caption text box.

## Audio
- Voice only: no music, no sound effects (campaign profile). Light compression, about -16 LUFS.
- If a specific effect is asked for (for example real iPhone keyboard clicks under a typing scene), use a real recording of that effect, put it on its own track so the user can mute it, and note where the sound came from and its licence.

## Pace for the loudest moments
- Cut between phrases, never inside one. Remove pauses over ~0.3 s and filler words, leaving about 0.17 s of breath.
- Do not start a segment on the second half of a word.
