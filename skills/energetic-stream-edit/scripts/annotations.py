"""Annotations for viral-style Shorts: hand-drawn red circles and arrows, emoji icons, and labelled picture-in-picture windows.

Seen in the studied clips ("circle the girl, circle the hand, arrow at the chat", an ambulance icon next to the word,
a screen-recorded stream chat inserted with a "CHAT WARNING" label).

Plan entries (all times are seconds from the start of the clip; coordinates are fractions):
  {"type": "circle", "at_word": "scary", "dur": 1.6, "x": 0.5, "y": 0.31, "r": 0.06}            # r = radius as a fraction of the width; or rx / ry
  {"type": "arrow",  "t0": 3.0, "dur": 1.4, "x0": 0.2, "y0": 0.1, "x1": 0.45, "y1": 0.28, "bend": 0.12}
  {"type": "emoji",  "at_word": "fighting", "char": "🥊", "x": 0.2, "y": 0.3, "size": 0.16}
  {"type": "inset",  "t0": 5.0, "dur": 2.4, "src": "broll/x.mp4", "ss": 3.0, "label": "THE FIGHT", "x": 0.5, "y": 0.2, "w": 0.62}
"space": "source" (default for circle / arrow / emoji) pins the drawing to the picture, so it follows the zoom jumps;
"space": "screen" pins it to the 1080x1920 frame (default for inset). Insets show a REAL file you give (screenshot or screen recording):
nothing here invents a chat or a screen.
"""
import math
import os
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import captions as C

RED = (255, 59, 48)
EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


def ease_out_back(x, s=1.70158):
    x = min(max(x, 0.0), 1.0)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def fade(t, t1, tail=0.10):
    return 1.0 if t < t1 - tail else max(0.0, (t1 - t) / tail)


# ---------------------------------------------------------------- coordinates
class View:
    """Maps annotation coordinates to output pixels. `M` is the 2x3 camera matrix (source px -> output px) of the current frame."""
    def __init__(self, W=1080, H=1920, sw=None, sh=None, M=None):
        self.W, self.H, self.sw, self.sh, self.M = W, H, sw, sh, M

    def point(self, x, y, space="source"):
        if space == "source" and self.M is not None:
            return (float(self.M[0, 0] * x * self.sw + self.M[0, 2]), float(self.M[1, 1] * y * self.sh + self.M[1, 2]))
        return float(x * self.W), float(y * self.H)

    def length(self, v, space="source"):
        return float(v * self.sw * self.M[0, 0]) if (space == "source" and self.M is not None) else float(v * self.W)


# ---------------------------------------------------------------- strokes
def _polys_layer(polys, width, color, ss=2, shadow=True):
    """Draw polylines (absolute output px) as a round-capped stroke with a soft shadow. Returns (RGBA layer, (cx, cy)) or None."""
    arrs = [np.asarray(p, float) for p in polys if len(p)]
    if not arrs:
        return None
    allp = np.concatenate(arrs)
    pad = width * 2 + 8
    x0, y0 = allp.min(0) - pad; x1, y1 = allp.max(0) + pad
    W, H = int(math.ceil(x1 - x0)), int(math.ceil(y1 - y0))
    big = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    loc = [[((x - x0) * ss, (y - y0) * ss) for x, y in p] for p in polys if len(p)]
    if shadow:
        sh = Image.new("RGBA", big.size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh); off = 3 * ss
        for p in loc:
            d.line([(x + off, y + off * 1.3) for x, y in p], fill=(0, 0, 0, 120), width=int(width * ss * 1.15), joint="curve")
        big = Image.alpha_composite(big, sh.filter(ImageFilter.GaussianBlur(2.5 * ss)))
    d = ImageDraw.Draw(big); r = width * ss / 2
    for p in loc:
        if len(p) > 1:
            d.line(p, fill=tuple(color) + (255,), width=int(width * ss), joint="curve")
        for x, y in (p[0], p[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(color) + (255,))
    return np.asarray(big.resize((W, H), Image.LANCZOS)), ((x0 + x1) / 2, (y0 + y1) / 2)


def circle_points(cx, cy, rx, ry, progress, tilt_deg=-8.0, seed=1.0, turns=1.07):
    """A hand-drawn loop: slightly wobbly, spiralling out so the end overshoots the start. progress 0..1 = how much is drawn."""
    if progress <= 0:
        return np.zeros((0, 2))
    n = max(3, int(240 * min(progress, 1.0)))
    k = np.linspace(0, min(progress, 1.0), n)
    th = math.radians(-110) + 2 * math.pi * turns * k
    rr = 1 + 0.05 * np.sin(2 * th + seed) + 0.03 * np.sin(3 * th + 2 * seed) + 0.07 * (k / max(progress, 1e-6)) * min(progress, 1.0)
    x, y = rx * rr * np.cos(th), ry * rr * np.sin(th)
    a = math.radians(tilt_deg); ca, sa = math.cos(a), math.sin(a)
    return np.stack([cx + x * ca - y * sa, cy + x * sa + y * ca], 1)


def arrow_polys(x0, y0, x1, y1, progress, bend=0.12, head=None):
    """Shaft (slightly curved) drawn over the first 78% of progress, then the two head strokes grow."""
    if progress <= 0:
        return []
    v = np.array([x1 - x0, y1 - y0], float); L = float(np.hypot(*v)) or 1.0
    nrm = np.array([-v[1], v[0]]) / L
    ctrl = np.array([x0, y0]) + v / 2 + nrm * bend * L
    ts = np.linspace(0, min(progress / 0.78, 1.0), 40)
    P0, P2 = np.array([x0, y0]), np.array([x1, y1])
    shaft = np.array([(1 - t) ** 2 * P0 + 2 * (1 - t) * t * ctrl + t ** 2 * P2 for t in ts])
    polys = [shaft]
    if progress > 0.78:
        hp = min((progress - 0.78) / 0.22, 1.0)
        tang = P2 - ctrl; tang = tang / (np.hypot(*tang) or 1.0)
        hl = (head or max(46.0, 0.28 * L)) * hp
        for s in (+1, -1):
            a = math.radians(150 * s); ca, sa = math.cos(a), math.sin(a)
            d = np.array([tang[0] * ca - tang[1] * sa, tang[0] * sa + tang[1] * ca])
            polys.append(np.array([P2, P2 + d * hl]))
    return polys


# ---------------------------------------------------------------- emoji
_emoji_cache = {}

def emoji_image(char, px):
    """Apple Color Emoji glyph, cropped, as RGBA at roughly `px` pixels wide."""
    key = (char, int(px))
    if key not in _emoji_cache:
        from PIL import ImageFont
        if not os.path.exists(EMOJI_FONT):
            raise RuntimeError(f"emoji font not found: {EMOJI_FONT} (macOS only); skip emoji annotations on other systems")
        f = ImageFont.truetype(EMOJI_FONT, 160)
        im = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((20, 20), char, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        s = px / im.width
        _emoji_cache[key] = np.asarray(im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS))
    return _emoji_cache[key]


# ---------------------------------------------------------------- insets (real files only)
def _fit(w, h, wpx, hmax):
    s = min(wpx / w, hmax / h)
    return max(2, int(w * s) // 2 * 2), max(2, int(h * s) // 2 * 2)


class Inset:
    """A labelled rounded window showing a real image or video file."""
    def __init__(self, src, wpx, hmax, ss=0.0, fps=30, label=None, label_color=RED, radius=30, border=7, margin=26):
        self.src, self.fps, self.ss, self.radius, self.border, self.margin = src, fps, float(ss), radius, border, margin
        self.video = src.lower().endswith(VIDEO_EXT)
        if self.video:
            j = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src]).decode().strip().split(",")
            self.w, self.h = _fit(int(j[0]), int(j[1]), wpx, hmax)
            self._proc, self._idx, self._last = None, -1, None
        else:
            im = Image.open(src).convert("RGB")
            self.w, self.h = _fit(im.width, im.height, wpx, hmax)
            self._still = np.asarray(im.resize((self.w, self.h), Image.LANCZOS))
        self._build_frame_art()
        self.label_img = self._label(label, label_color) if label else None

    def _build_frame_art(self):
        m, b, r = self.margin, self.border, self.radius
        W, H = self.w + 2 * b + 2 * m, self.h + 2 * b + 2 * m
        outer = Image.new("L", (W * 2, H * 2), 0)
        ImageDraw.Draw(outer).rounded_rectangle([m * 2, m * 2, (W - m) * 2 - 1, (H - m) * 2 - 1], radius=(r + b) * 2, fill=255)
        outer = outer.resize((W, H), Image.LANCZOS)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shadow.putalpha(outer.point(lambda v: int(v * 0.55)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(9)); shadow = Image.alpha_composite(Image.new("RGBA", (W, H)), shadow)
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0)); base.alpha_composite(shadow, (0, 6))
        white = Image.new("RGBA", (W, H), (255, 255, 255, 255)); white.putalpha(outer)
        base.alpha_composite(white)
        inner = Image.new("L", (self.w * 2, self.h * 2), 0)
        ImageDraw.Draw(inner).rounded_rectangle([0, 0, self.w * 2 - 1, self.h * 2 - 1], radius=r * 2, fill=255)
        self._base, self._inner_mask, self._pos = base, inner.resize((self.w, self.h), Image.LANCZOS), (m + b, m + b)

    @staticmethod
    def _label(text, color):
        txt = C._line_image(((text.upper(), "white", "word"),), "upright", 54, False)
        h, w = txt.shape[:2]
        pill = Image.new("RGBA", (w + 40, h + 6), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle([0, 0, pill.width - 1, pill.height - 1], radius=pill.height // 2, fill=tuple(color) + (255,))
        pill.alpha_composite(Image.fromarray(txt), (20, 3))
        return np.asarray(pill)

    def _frame(self, k):
        if not self.video:
            return self._still
        k = max(0, k)
        if self._proc is None or k < self._idx:
            self.close()
            self._proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(self.ss), "-i", self.src, "-an", "-vf", f"fps={self.fps},scale={self.w}:{self.h}",
                                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self._idx = -1
        n = self.w * self.h * 3
        while self._idx < k:
            buf = self._proc.stdout.read(n)
            if len(buf) < n:
                break                         # clip ended: hold the last frame
            self._last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3); self._idx += 1
        return self._last if self._last is not None else np.zeros((self.h, self.w, 3), np.uint8)

    def close(self):
        if self.video and self._proc is not None:
            self._proc.kill(); self._proc.stdout.close(); self._proc.wait(); self._proc = None

    def group(self, age):
        """RGBA array: label above the window, for `age` seconds after the insert appeared."""
        panel = self._base.copy()
        panel.paste(Image.fromarray(self._frame(int(round(age * self.fps)))), self._pos, self._inner_mask)
        panel = np.asarray(panel)
        if self.label_img is None:
            return panel
        lh, lw = self.label_img.shape[:2]
        H = panel.shape[0] + lh // 2 + 4; W = max(panel.shape[1], lw)
        out = np.zeros((H, W, 4), np.uint8)
        y0 = lh // 2 + 4
        out[y0:y0 + panel.shape[0], (W - panel.shape[1]) // 2:(W - panel.shape[1]) // 2 + panel.shape[1]] = panel
        lab = Image.fromarray(out); lab.alpha_composite(Image.fromarray(self.label_img), ((W - lw) // 2, self.margin - 4 + 0))
        return np.asarray(lab)


# ---------------------------------------------------------------- plan handling
def resolve_times(anns, words=None):
    """Fill in t0 / t1: `at_word` starts the annotation on the spoken word (plus `lead`, default -0.05 s); `dur` defaults to 1.8 s."""
    out = []
    for a in anns or []:
        a = dict(a)
        if "at_word" in a:
            tok = re.sub(r"[^a-z0-9']", "", a["at_word"].lower())
            hits = [w for w in (words or []) if re.sub(r"[^a-z0-9']", "", w["w"].lower()) == tok]
            occ = a.get("occurrence", 1)
            if len(hits) < occ:
                raise ValueError(f"annotation word {a['at_word']!r} (occurrence {occ}) not found in the transcript")
            a["t0"] = hits[occ - 1]["s"] + a.get("lead", -0.05)
        a.setdefault("t0", 0.0)
        a.setdefault("t1", a["t0"] + a.get("dur", 1.8))
        out.append(a)
    return out


def cue_times(anns):
    """When each annotation appears: where a pop / impact sound belongs."""
    return sorted(a["t0"] for a in anns)


class AnnotationRenderer:
    def __init__(self, anns, W=1080, H=1920, base_dirs=()):
        self.W, self.H, self.anns, self.insets = W, H, anns, {}
        for i, a in enumerate(anns):
            if a["type"] == "inset":
                src = a["src"] if os.path.isabs(a["src"]) else next((os.path.join(d, a["src"]) for d in base_dirs if os.path.exists(os.path.join(d, a["src"]))), a["src"])
                self.insets[i] = Inset(src, int(a.get("w", 0.62) * W), int(a.get("hmax", 0.30) * H), a.get("ss", 0.0), label=a.get("label"),
                                       label_color=C.COLORS[a["label_color"]] if isinstance(a.get("label_color"), str) else a.get("label_color", RED))

    def close(self):
        for ins in self.insets.values():
            ins.close()

    def draw(self, frame, t, view):
        for i, a in enumerate(self.anns):
            if not (a["t0"] <= t < a["t1"]):
                continue
            age, alpha, kind = t - a["t0"], fade(t, a["t1"]), a["type"]
            col = C.COLORS[a["color"]] if isinstance(a.get("color"), str) else tuple(a.get("color", RED))
            sp = a.get("space", "screen" if kind == "inset" else "source")
            if kind == "circle":
                cx, cy = view.point(a["x"], a["y"], sp)
                rx = view.length(a.get("rx", a.get("r", 0.06)), sp); ry = view.length(a.get("ry", a.get("r", 0.06)), sp)
                pts = circle_points(cx, cy, rx, ry, min(age / a.get("draw", 0.28), 1.0), a.get("tilt", -8.0), a.get("seed", 1.0))
                lay = _polys_layer([pts], a.get("width", 11), col)
                if lay: C._blend(frame, lay[0], lay[1][0], lay[1][1], alpha)
            elif kind == "arrow":
                x0, y0 = view.point(a["x0"], a["y0"], sp); x1, y1 = view.point(a["x1"], a["y1"], sp)
                lay = _polys_layer(arrow_polys(x0, y0, x1, y1, min(age / a.get("draw", 0.25), 1.0), a.get("bend", 0.12)), a.get("width", 14), col)
                if lay: C._blend(frame, lay[0], lay[1][0], lay[1][1], alpha)
            elif kind == "emoji":
                cx, cy = view.point(a["x"], a["y"], sp)
                img = emoji_image(a["char"], a.get("size", 0.16) * self.W)
                s = 0.35 + 0.65 * ease_out_back(age / 0.18)
                C._blend(frame, img, cx, cy, alpha, s)
            elif kind == "inset":
                ins = self.insets[i]
                cx, cy = view.point(a.get("x", 0.5), a.get("y", 0.22), "screen")
                s = 0.8 + 0.2 * ease_out_back(age / 0.18)
                C._blend(frame, ins.group(age), cx, cy, alpha, s)
