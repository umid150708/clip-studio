#!/usr/bin/env python3
"""Compose a thumbnail from a REAL frame of the footage (no AI-generated likeness).

  python3 -I make_thumb.py --video segments/01_example.mp4 --at 17 \
      --text "WATCHED THE FIGHT|IN THE AIR" --out thumbs/01 --focus 0.5

Writes <out>_9x16.jpg (1080x1920, Shorts/Reels/TikTok cover) and <out>_16x9.jpg (1280x720).
--text uses | for a line break; the LAST line is drawn in the accent colour.
--focus is the horizontal position (0-1) of the face in the source frame so the crop keeps it.
"""
import argparse, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

FONTS = ["/System/Library/Fonts/Supplemental/Impact.ttf", "/System/Library/Fonts/Supplemental/Arial Black.ttf"]


def font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def grab(video, at):
    tmp = tempfile.mktemp(suffix=".png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(at), "-i", video, "-frames:v", "1", tmp], check=True)
    img = Image.open(tmp).convert("RGB")
    os.remove(tmp)
    return img


def cover(img, w, h, focus):
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    x = min(max(round(img.width * focus - w / 2), 0), img.width - w)
    return img.crop((x, 0, x + w, h))


def grade(img):
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.25)
    return ImageEnhance.Brightness(img).enhance(1.05)


def shade(img, strength=215):
    """Dark gradient over the lower 55% so the text always reads."""
    w, h = img.size
    g = Image.new("L", (1, h), 0)
    for y in range(h):
        t = max(0.0, (y - h * 0.45) / (h * 0.55))
        g.putpixel((0, y), int(strength * t ** 1.4))
    g = g.resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, g)


def draw_text(img, lines, accent, box_w, bottom_pad, max_size):
    d = ImageDraw.Draw(img)
    size = 40
    while size < max_size and max(d.textlength(l, font=font(size + 4)) for l in lines) <= box_w:
        size += 4
    f = font(size)
    line_h = size * 1.08
    y = img.height - bottom_pad - line_h * len(lines)
    for i, line in enumerate(lines):
        x = (img.width - d.textlength(line, font=f)) / 2
        colour = accent if i == len(lines) - 1 else (255, 255, 255)
        d.text((x, y), line, font=f, fill=colour, stroke_width=max(6, size // 12), stroke_fill=(0, 0, 0))
        y += line_h


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--video"); src.add_argument("--image")
    p.add_argument("--at", type=float, default=1.0, help="seconds into --video")
    p.add_argument("--text", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--focus", type=float, default=0.5)
    p.add_argument("--accent", default="#FFD400")
    a = p.parse_args()

    frame = grab(a.video, a.at) if a.video else Image.open(a.image).convert("RGB")
    accent = tuple(int(a.accent.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    lines = [s.strip().upper() for s in a.text.split("|")]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    # max_size keeps the type under ~35% of the frame height so the face stays clear
    for tag, (w, h, pad, max_size) in {"9x16": (1080, 1920, 300, 190), "16x9": (1280, 720, 36, 104)}.items():
        img = shade(grade(cover(frame, w, h, a.focus)))
        draw_text(img, lines, accent, int(w * 0.9), pad, max_size)
        img.save(f"{a.out}_{tag}.jpg", quality=92)
        print(f"wrote {a.out}_{tag}.jpg")


if __name__ == "__main__":
    main()
