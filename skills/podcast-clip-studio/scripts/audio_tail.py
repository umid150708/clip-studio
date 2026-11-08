"""Is the last word cut off?  Prints the loudness of the last N seconds of a clip's audio in 0.1 s steps.
A healthy ending trails off (a final word, then a drop to near silence). A bar that is still tall in the very last
step means the clip was cut mid-sound.

   python3 -I audio_tail.py clip.mp4 [seconds=1.6]
"""
import subprocess, sys
import numpy as np

path = sys.argv[1]
n = float(sys.argv[2]) if len(sys.argv) > 2 else 1.6
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"])
a = np.frombuffer(raw, np.float32)
total = len(a) / 16000
print(f"audio {total:.2f}s")
for t in np.arange(max(total - n, 0), total - 0.05, 0.1):
    seg = a[int(t * 16000): int((t + 0.1) * 16000)]
    if len(seg):
        print(f"{t:6.2f}s {'#' * int(min(np.sqrt((seg ** 2).mean()) * 400, 60))}")
