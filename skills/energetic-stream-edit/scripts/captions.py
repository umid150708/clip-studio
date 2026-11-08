"""Viral-style captions: ALL CAPS, heavy rounded sans, thick black outline, colour per feeling, *action text*.

Measured on six viral Shorts (see study/VIRAL_EDIT_PLAYBOOK.md):
  - one word at a time (or 2-4 words), yellow base, cyan for emphasis, pink for *action text*, red danger, green positive
  - chest height (about 46-50% down the frame), small: a word is about a quarter of the frame width
  - a quick pop-in (scale 1.2 -> 1.0 in ~0.09 s)

Two ways to get captions:
  build_events_from_words(words, ...)   auto, from a word-timed transcript
  build_events_from_script(script)      narration you write: [{"t0":1.0,"t1":2.4,"text":"the girl {red|notice} *looks at her*"}]
Markup in script text:  {cyan|WORD OR WORDS}  = colour that span,   *action text*  = action style (pink, smaller, asterisks kept)
"""
import os
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = {
    "upright": ("/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf", None),
    "italic": ("/System/Library/Fonts/Avenir Next.ttc", 9),       # Heavy Italic
    "impact": ("/System/Library/Fonts/Supplemental/Impact.ttf", None),
}
COLORS = {
    "yellow": (255, 230, 0), "cyan": (0, 229, 255), "pink": (255, 92, 170), "red": (255, 59, 48),
    "green": (61, 255, 106), "white": (255, 255, 255), "orange": (255, 159, 28),
}
PALETTES = {  # which colour plays which role
    "yellow-cyan": dict(base="yellow", accent="cyan", action="pink", danger="red", positive="green"),
    "white-accent": dict(base="white", accent="yellow", action="pink", danger="red", positive="green"),
}
DANGER = {"DEAD", "DIE", "DYING", "KILL", "BLOOD", "STROKE", "ATTACK", "AMBULANCE", "911", "HELP", "SCARED", "SCARY", "FIGHT", "HURT", "DANGER", "CRY"}
POSITIVE = {"W", "WIN", "LOVE", "RESPECT", "KIND", "KINDEST", "THANK", "THANKS", "GOOD", "BLESS", "GOAT", "PROUD", "HAPPY", "BEST", "GREAT"}
EMPHASIS = {"NO", "WAIT", "WHAT", "WOW", "OH", "YES", "NOT", "NEVER", "REALLY", "SERIOUS", "CRAZY", "INSANE", "OMG", "BRO", "LOL", "NOW", "ONLY", "EVERYONE", "NOBODY", "IMPOSSIBLE"}

_CENSOR = [(r"fuck", "f*ck"), (r"shit", "sh*t"), (r"bitch", "b*tch"), (r"cunt", "c*nt"), (r"dick", "d*ck"), (r"asshole", "a**hole"), (r"\bass\b", "a**")]


def censor(word):
    """F*ck / sh*t / a** style (the rule for every clip)."""
    w = word
    for pat, rep in _CENSOR:
        def sub(m, rep=rep):
            s = m.group(0)
            return "".join(r.upper() if c.isupper() else r for c, r in zip(s, rep)) if len(s) == len(rep) else rep
        w = re.sub(pat, sub, w, flags=re.I)
    return w


def role_of(token):
    t = re.sub(r"[^A-Z0-9']", "", token.upper())
    if t in DANGER: return "danger"
    if t in POSITIVE: return "positive"
    if t in EMPHASIS: return "accent"
    return None


# ---------------------------------------------------------------- building events
def _tidy(w, keep_marks="!?"):
    """Caption text for one transcript word: censored, no commas/periods, keeps ! and ?"""
    w = censor(w.replace("[ __ ]", "***").strip())
    return re.sub(r"[,.;:]+$", "", w)


def build_events_from_words(words, mode="word", palette="yellow-cyan", per=3, max_hold=0.7, pause=0.35, upper=True):
    """words: [{'w','s','e'}] in clip time. mode 'word' = one word at a time; 'phrase' = up to `per` words with a highlighted current word."""
    pal = PALETTES[palette]
    words = [dict(w=_tidy(x["w"]), s=x["s"], e=x["e"]) for x in words if _tidy(x["w"])]
    events = []
    # phrase groups (break at pauses and sentence ends); colour alternates per group
    groups, cur = [], []
    for i, x in enumerate(words):
        cur.append(x)
        gap = (words[i + 1]["s"] - x["e"]) if i + 1 < len(words) else 9
        if gap > pause or re.search(r"[!?]$", x["w"]) or len(cur) >= per:
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    for gi, g in enumerate(groups):
        group_color = pal["base"] if gi % 2 == 0 else pal["accent"]
        if mode == "word":
            for j, x in enumerate(g):
                nxt = g[j + 1]["s"] if j + 1 < len(g) else x["e"] + 0.12
                role = role_of(x["w"])
                color = pal[role] if role else group_color
                events.append(dict(t0=x["s"], t1=min(max(nxt, x["s"] + 0.18), x["s"] + max_hold), segs=[dict(text=(x["w"].upper() if upper else x["w"]), color=color, kind="word")], mode="word"))
        else:
            segs = [dict(text=(x["w"].upper() if upper else x["w"]), color=(pal[role_of(x["w"])] if role_of(x["w"]) else "white"), kind="word", s=x["s"], e=x["e"]) for x in g]
            events.append(dict(t0=g[0]["s"], t1=g[-1]["e"] + 0.2, segs=segs, mode="phrase", hi=pal["base"]))
    return events


_TOKEN = re.compile(r"\{(\w+)\|([^}]*)\}|\*([^*]+)\*|(\S+)")


def parse_markup(text, palette="yellow-cyan"):
    pal = PALETTES[palette]
    segs = []
    for m in _TOKEN.finditer(text):
        if m.group(1):
            segs.append(dict(text=censor(m.group(2)).upper(), color=m.group(1), kind="word"))
        elif m.group(3):
            segs.append(dict(text="*" + censor(m.group(3)).upper() + "*", color=pal["action"], kind="action"))
        else:
            tok = censor(m.group(4)); r = role_of(tok)
            segs.append(dict(text=tok.upper(), color=pal[r] if r else pal["base"], kind="word"))
    return segs


def build_events_from_script(script, palette="yellow-cyan"):
    return [dict(t0=s["t0"], t1=s["t1"], segs=parse_markup(s["text"], palette), mode="script") for s in script]


# ---------------------------------------------------------------- rendering
def _rgb(c): return COLORS[c] if isinstance(c, str) else tuple(c)


@lru_cache(maxsize=None)
def _font(style, px):
    path, idx = FONTS[style]
    if not os.path.exists(path):
        raise RuntimeError(f"font not found: {path}. These tools were built on macOS and use its system fonts; point FONTS in captions.py at any heavy rounded sans on this machine.")
    return ImageFont.truetype(path, int(px), index=idx) if idx is not None else ImageFont.truetype(path, int(px))


@lru_cache(maxsize=512)
def _line_image(segs_key, style, size, glow, ss=2):
    """segs_key: tuple of (text, colour name/rgb, kind). Returns RGBA numpy array (outlined text on a transparent canvas)."""
    segs = [dict(text=t, color=c, kind=k) for t, c, k in segs_key]
    S = ss
    px = [size * (0.8 if s["kind"] == "action" else 1.0) * S for s in segs]
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    gap = size * 0.28 * S
    widths = [probe.textlength(s["text"], font=_font(style, p)) for s, p in zip(segs, px)]
    stroke = max(3, int(size * 0.13 * S))
    pad = int(stroke * 2 + size * 0.35 * S)
    W = int(sum(widths) + gap * (len(segs) - 1) + 2 * pad); H = int(size * 1.5 * S + 2 * pad)
    fill = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(fill)
    x = pad
    for s, p, w in zip(segs, px, widths):
        y = pad + (size * S - p) * 0.55
        d.text((x, y), s["text"], font=_font(style, p), fill=_rgb(s["color"]) + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        x += w + gap
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    alpha = fill.split()[3]
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 150)); shadow.paste(sh, (0, int(size * 0.06 * S)), alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.025 * S))
    out = Image.alpha_composite(shadow, fill)
    if glow:   # neon: a blurred copy of the coloured text behind
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(g); x = pad
        for s, p, w in zip(segs, px, widths):
            y = pad + (size * S - p) * 0.55
            gd.text((x, y), s["text"], font=_font(style, p), fill=_rgb(s["color"]) + (200,), stroke_width=stroke // 2, stroke_fill=_rgb(s["color"]) + (200,)); x += w + gap
        g = g.filter(ImageFilter.GaussianBlur(size * 0.14 * S))
        out = Image.alpha_composite(g, out)
    out = out.resize((W // S, H // S), Image.LANCZOS)
    return np.asarray(out)


def _blend(frame, layer, cx, cy, alpha=1.0, scale=1.0):
    if scale != 1.0:
        h, w = layer.shape[:2]
        layer = np.asarray(Image.fromarray(layer).resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR))
    h, w = layer.shape[:2]
    H, W = frame.shape[:2]
    x0 = int(round(cx - w / 2)); y0 = int(round(cy - h / 2))
    sx0, sy0 = max(0, -x0), max(0, -y0); x0c, y0c = max(0, x0), max(0, y0)
    x1, y1 = min(W, x0 + w), min(H, y0 + h)
    if x1 <= x0c or y1 <= y0c: return
    sub = layer[sy0: sy0 + (y1 - y0c), sx0: sx0 + (x1 - x0c)]
    a = sub[:, :, 3:4].astype(np.float32) / 255 * alpha
    region = frame[y0c:y1, x0c:x1].astype(np.float32)
    frame[y0c:y1, x0c:x1] = (region * (1 - a) + sub[:, :, :3] * a).astype(np.uint8)


class CaptionRenderer:
    def __init__(self, width=1080, height=1920, style="upright", size=100, y=0.47, glow=False, pop=0.20, pop_time=0.09):
        self.W, self.H, self.style, self.size, self.y, self.glow, self.pop, self.pop_time = width, height, style, size, y, glow, pop, pop_time

    def _key(self, segs):
        return tuple((s["text"], tuple(s["color"]) if not isinstance(s["color"], str) else s["color"], s["kind"]) for s in segs)

    def draw_segments(self, frame, segs, t0, t, y=None, size=None, style=None, fade_out_at=None):
        size = size or self.size; style = style or self.style; y = self.y if y is None else y
        age = t - t0
        scale = 1.0 + self.pop * max(0.0, 1 - age / self.pop_time) if age >= 0 else 1.0
        alpha = 1.0
        if fade_out_at is not None and t > fade_out_at: alpha = max(0.0, 1 - (t - fade_out_at) / 0.06)
        # wrap to two lines when too wide
        key = self._key(segs)
        img = _line_image(key, style, size, self.glow)
        if img.shape[1] > self.W * 0.9 and len(segs) > 1:
            half = len(segs) // 2
            self.draw_segments(frame, segs[:half], t0, t, y - size * 0.62 / self.H, size, style, fade_out_at)
            self.draw_segments(frame, segs[half:], t0, t, y + size * 0.62 / self.H, size, style, fade_out_at)
            return
        _blend(frame, img, self.W / 2, self.H * y, alpha, scale)

    def draw(self, frame, events, t):
        for ev in events:
            if ev["t0"] <= t < ev["t1"]:
                segs = ev["segs"]
                if ev["mode"] == "phrase":   # highlight the word being spoken
                    cur = max([i for i, s in enumerate(segs) if s.get("s", 0) <= t + 0.02] or [0])
                    segs = [dict(s, color=(ev["hi"] if i == cur else s["color"])) for i, s in enumerate(segs)]
                self.draw_segments(frame, segs, ev["t0"], t, fade_out_at=ev["t1"] - 0.06)
                return ev
        return None

    def draw_title(self, frame, lines, colors, t0, t1, t, y=0.69, size=128, style="italic"):
        if not (t0 <= t < t1): return
        for i, (ln, col) in enumerate(zip(lines, colors)):
            self.draw_segments(frame, [dict(text=ln.upper(), color=col, kind="word")], t0, t, y=y + i * (size * 0.95 / self.H), size=size, style=style, fade_out_at=t1 - 0.08)
