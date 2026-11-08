"""Find stretches where the PICTURE (not the audio, not the captions) stays visually still.
A 'visible change' = the frame differs a lot from the last reference frame (a cut, a cutaway, or a clear zoom).
   python3 -I stillness.py VIDEO [threshold=14] [limit_s=3.4]      prints the changes and every still stretch longer than limit_s
"""
import subprocess, sys
import numpy as np
v = sys.argv[1]; T = float(sys.argv[2]) if len(sys.argv) > 2 else 14.0; LIM = float(sys.argv[3]) if len(sys.argv) > 3 else 3.4
w, h = 54, 96
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", v, "-an", "-vf", f"fps=30,scale={w}:{h},format=gray", "-f", "rawvideo", "-"])
f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
ref, events = f[0], [0.0]
for i in range(1, len(f)):
    if np.abs(f[i] - ref).mean() > T:
        events.append(i / 30); ref = f[i]
events.append(len(f) / 30)
print("visible changes at:", [round(e, 1) for e in events[1:-1]])
bad = [(round(a, 1), round(b, 1)) for a, b in zip(events, events[1:]) if b - a > LIM]
print(f"STILL stretches longer than {LIM}s:", bad or "none")
if bad:
    print("note: a scene with its own built-in animation (a typing screen, a screen recording) can be listed here even though it moves; judge those by eye.")
