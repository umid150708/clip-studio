# Finding the moments people replay

## Signals, strongest first
1. **Timestamps in comments.** Viewers write "12:34 this part" to point friends at a moment. `find_moments.py` pulls every `m:ss` or `h:mm:ss` from the top ~500 comments, clusters timestamps within 25 s of each other, and weights each by the comment's likes.
2. **"Most replayed" heatmap.** `yt-dlp` writes it to the `.info.json` as `heatmap` (100 segments, 0 to 1). A segment near 1.0 is where viewers scrub back. It is absent on some videos, and the very start of a video is always high, so the script ignores the first 20 s.
3. **Laughter and joy in the comments.** The share of comments with laugh emoji or words (😂🤣💀😭, lol, lmao, "dying") near a moment, smoothed toward the video's overall rate. Use it to choose between two otherwise equal moments.
4. **Guest fame.** `--bonus VIDEO_ID=1.5:Guest name` adds weight for a bigger name.

## What the score cannot know
- **Ads.** Sponsor reads attract replays and comment timestamps ("skip to 43:29"). The script flags any window whose captions contain sponsor words and drops it. Add show-specific sponsors with `--ad WORD`. Captions can misspell a brand ("Betr" as "better"), so read the top few by hand.
- **Brand safety.** The funniest moments are often crude, about drugs, or about someone's health or ethnicity. For a paid campaign, drop them even if the laugh score is high.
- **Who is speaking.** Auto-captions have no speaker labels. Watch the frames before you label a clip "X says Y".
- **Context.** A 1.0 replay peak can be the end of a story you cannot clip without its setup.

## Fetching the data
```bash
bash scripts/fetch_meta.sh VIDEO_ID        # writes meta/ID.info.json (comments, heatmap) and subs/ID.en.json3
```
The fetch reads public comments and captions only; no video file is downloaded. If captions return HTTP 429, run `bash scripts/retry_subs.sh VIDEO_ID` in the background; it retries every 4 minutes.

Useful `yt-dlp` pieces: `--write-comments --extractor-args "youtube:max_comments=500,500,0,0;comment_sort=top"`, `--write-auto-subs --sub-langs en --sub-format json3`, and the updated `--js-runtimes node`.

## Reading a window
```bash
python3 -I scripts/window.py subs VIDEO_ID 1230 1290      # timed transcript between 20:30 and 21:30
```
Pick the **hook line** (the first sentence of the clip), the **landing line** (where it ends), and the in and out times. A clip works when it has a reason to keep watching in its first 2-3 seconds and pays that reason off before it ends.

## A ranked table to show the user
| # | Clip | Source (id) | In-out | Hook line | Evidence | Flags |
|---|---|---|---|---|---|---|
Keep it to 5-8 rows. Mark each row's flags honestly: sponsor read, brand risk, speaker unknown, third-party footage, old episode.
