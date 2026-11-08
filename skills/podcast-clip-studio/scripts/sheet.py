"""Timestamp-labelled contact sheet.  python3 -I sheet.py VIDEO OUT.png [step_s=2] [cols=6] [start=0] [end=None] [tile_w=256]"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

video, out = sys.argv[1], sys.argv[2]
step = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 6
start = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video]))
end = float(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "None" else dur
tw = int(sys.argv[7]) if len(sys.argv) > 7 else 256

tmp = tempfile.mkdtemp()
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-to", str(end), "-i", video,
                "-vf", f"fps=1/{step},scale={tw}:-2", f"{tmp}/f_%04d.png"], check=True)
frames = sorted(os.listdir(tmp))
imgs = [Image.open(f"{tmp}/{f}").convert("RGB") for f in frames]
w, h = imgs[0].size
rows = (len(imgs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 15)
except Exception:
    font = ImageFont.load_default()
d = ImageDraw.Draw(sheet)
for i, im in enumerate(imgs):
    x, y = (i % cols) * w, (i // cols) * h
    sheet.paste(im, (x, y))
    t = start + i * step
    label = f"{int(t // 60)}:{t % 60:04.1f}"
    d.rectangle((x, y, x + 62, y + 20), fill=(0, 0, 0))
    d.text((x + 3, y + 2), label, fill=(255, 255, 0), font=font)
sheet.save(out)
print(out, sheet.size, f"{len(imgs)} frames")
for f in frames:
    os.remove(f"{tmp}/{f}")
os.rmdir(tmp)
