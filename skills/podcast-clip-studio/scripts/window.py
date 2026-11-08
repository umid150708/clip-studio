"""Print a timed transcript window from a yt-dlp json3 caption file.
Usage: python3 -I window.py <subs_dir> <video_id> <start_sec> <end_sec>
"""
import json, sys


def load(path):
    d = json.load(open(path))
    out = []
    for ev in d.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if text:
            out.append((ev["tStartMs"] / 1000.0, text))
    return out


def fmt(t):
    t = int(t)
    return f"{t // 60}:{t % 60:02d}"


if __name__ == "__main__":
    subs, vid, a, b = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    for t, text in load(f"{subs}/{vid}.en.json3"):
        if a <= t <= b:
            print(f"[{fmt(t)}] {text}")
