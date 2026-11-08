#!/bin/bash
# Metadata only (no video): top comments, "Most replayed" heatmap and auto-captions for one video id.
#   printf '%s\n' ID1 ID2 | xargs -P 4 -n 1 bash fetch_meta.sh
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p meta subs
id="$1"
yt-dlp --js-runtimes node --skip-download --write-info-json --write-comments \
  --write-auto-subs --sub-langs en --sub-format json3 --no-warnings -q \
  --extractor-args "youtube:max_comments=500,500,0,0;comment_sort=top" \
  -o "meta/%(id)s" "https://www.youtube.com/watch?v=${id}" 2>&1 | tail -1
[ -f "meta/${id}.en.json3" ] && mv "meta/${id}.en.json3" "subs/${id}.en.json3"
echo "done ${id}"
