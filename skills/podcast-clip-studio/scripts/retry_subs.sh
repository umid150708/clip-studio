#!/bin/bash
# Retries the caption download for one video id every 4 minutes (YouTube rate-limits caption requests), up to 8 tries.
cd "$(dirname "$0")"
id="$1"
for i in 1 2 3 4 5 6 7 8; do
  yt-dlp --js-runtimes node --skip-download --write-auto-subs --sub-langs en --sub-format json3 --no-warnings -q -o "subs/%(id)s" "https://www.youtube.com/watch?v=$id" >/dev/null 2>&1
  if [ -f "subs/$id.en.json3" ]; then echo "got subs for $id on try $i"; exit 0; fi
  sleep 240
done
echo "gave up on subs for $id"; exit 1
