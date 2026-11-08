#!/bin/bash
# Crayo's renderer garbles the first 2-3 frames of a project that starts on an uploaded clip. Hold the first clean frame
# (at 0.25 s) over that gap; the audio is untouched, so nothing drifts out of sync.
#   bash fix_start.sh IN.mp4 OUT.mp4
set -euo pipefail
in="$1"; out="$2"
ffmpeg -y -v error -i "$in" -filter_complex "[0:v]trim=start=0.25,setpts=PTS-STARTPTS,tpad=start_duration=0.25:start_mode=clone[v]" \
  -map "[v]" -map 0:a -r 30 -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -c:a copy -movflags +faststart "$out"
echo "wrote $out"
