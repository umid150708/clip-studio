"""Cut a finished base short into kept segments (captions are burned in, so they follow) and remap the word timings.
   python3 -I cut_base.py BASE.mp4 WORDS.json OUT.mp4 --seg 12.40-32.15 --seg 44.60-74.95
"""
import argparse, json, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("words"); ap.add_argument("out")
ap.add_argument("--seg", action="append", required=True, help="start-end seconds to keep, in order")
ap.add_argument("--vhold", type=float, default=0.0,
                help="first segment only: take the picture from start+VHOLD and hold that first frame for VHOLD s, "
                     "so a glitch or wrong-speaker frame at the very start is hidden while the audio still begins on the word")
a = ap.parse_args()
segs = [tuple(float(x) for x in s.split("-")) for s in a.seg]

parts, labels = [], []
for i, (s, e) in enumerate(segs):
    fade = 0.03
    vh = a.vhold if i == 0 else 0.0
    vtrim = f"trim={s + vh}:{e},setpts=PTS-STARTPTS" + (f",tpad=start_duration={vh}:start_mode=clone" if vh else "")
    parts.append(f"[0:v]{vtrim}[v{i}];"
                 f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade},afade=t=out:st={e - s - fade}:d={fade}[a{i}]")
    labels.append(f"[v{i}][a{i}]")
fc = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.base, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-r", "30", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", a.out], check=True)

data = json.load(open(a.words))
off, out = 0.0, []
for s, e in segs:
    for w in data["words"]:
        if s - 0.02 <= w["s"] < e:
            out.append({"w": w["w"], "s": round(w["s"] - s + off, 3), "e": round(min(w["e"], e) - s + off, 3)})
    off += e - s
data["words"] = out
json.dump(data, open(a.out.rsplit(".", 1)[0] + ".words.json", "w"), indent=1)
print(f"{a.out}: {off:.1f}s, {len(out)} words")
