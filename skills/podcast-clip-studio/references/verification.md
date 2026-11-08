# Verify before you say "ready"

Do all of these. Report what passed, and what you could not check (you cannot hear audio).

| Check | How |
|---|---|
| The file plays end to end | `ffmpeg -v error -i clip.mp4 -f null - 2>&1 | wc -l` should print 0 |
| Format | `ffprobe` shows h264 + aac, 1080x1920, ~30 fps, 20-60 s |
| First second | `python3 -I scripts/sheet.py clip.mp4 out.png 0.1 10 0 1.0 110`. Crayo can garble frames 0-3; `scripts/fix_start.sh` fixes it |
| The hook is the first line | read the first captions: the clip opens on the hook, with nothing before it |
| Last word not cut | measure audio energy over the last 1.5 s (a short script with ffmpeg `-f f32le` and numpy) and look at the last frames |
| The picture keeps changing | `python3 -I scripts/stillness.py clip.mp4 14 3.4`. Animated scenes may be flagged; judge by eye |
| Cutaways are the right footage | contact sheet at 1 frame per second; confirm each shows what the words say |
| No cutaway in the first 2 s | read the plan's start times |
| Captions | read every line against the transcript; fix in the editor |
| Bad words | scan every caption line; censor in the F*ck style |
| Text that must be read is above the captions | look at a frame from the real export, not the plan |
| Loudness | `ffmpeg -i clip.mp4 -af ebur128=peak=true -f null -`: aim near -16 LUFS, true peak under -1.5 dB |
| No stray audio | if a special sound track was added (typing, for example), compare the export to the voice track alone and check the extra energy sits only where intended |
| Credits | `crayo.py account` before and after; the difference is what you spent |

## What to hand over
- The final file(s), named so the user can tell them apart. Move older versions into an "old versions" folder instead of deleting them.
- A notes file with the post title, the hook, the source episode, every third-party cutaway and its source, and any known defect, stated plainly.
- The Crayo project id, so the user can open it in the advanced editor.
