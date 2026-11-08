#!/bin/bash
# Download ONLY a time window of a YouTube video (not the whole episode), up to 1080p, as mp4.
# Ask the user first: say the source, the window and the expected size (roughly 15-25 MB per 90 s at 1080p).
#
#   bash fetch_window.sh VIDEO_ID START-END NAME          e.g.  bash fetch_window.sh dQw4w9WgXcQ 12:30-14:10 01_hook_story
#   DRY=1 bash fetch_window.sh ...                        prints what it would fetch and checks the video exists, downloads nothing
#
# Needs: yt-dlp (keep it current: old builds get HTTP 403), node on PATH (YouTube's JS checks), ffmpeg.
# Pad the window by 10-20 s on each side of the clip so the editor has room to land on sentence boundaries.
# Crayo AutoClip needs a source of at least 60 s.
set -euo pipefail
id="$1"; win="$2"; name="$3"
mkdir -p segments
out="segments/${name}.mp4"
[ -f "$out" ] && { echo "skip: $out exists"; exit 0; }
args=(--js-runtimes node --no-warnings -q
      -f "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]"
      --merge-output-format mp4 --download-sections "*${win}" --force-keyframes-at-cuts
      -o "segments/${name}.%(ext)s")
if [ "${DRY:-0}" = "1" ]; then
  yt-dlp "${args[@]}" --simulate --print "would fetch: %(title)s | %(channel)s | %(duration_string)s" "https://www.youtube.com/watch?v=${id}"
  exit 0
fi
yt-dlp "${args[@]}" --progress "https://www.youtube.com/watch?v=${id}"
ls -lh "$out"
