"""Checks for annotations.py.   python3 -I test_annotations.py"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import annotations as A

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1

BG = 60
def blank(): return np.full((1920, 1080, 3), BG, np.uint8)
def changed(f): return (f != BG).any(axis=2)
screen = A.View(1080, 1920)

# --- circle: drawn progressively, ring not disc, hand-drawn overshoot
def circ(t, **kw):
    a = dict(type="circle", t0=0.0, t1=2.0, x=0.5, y=0.5, r=0.12, **kw)
    f = blank(); r = A.AnnotationRenderer([a]); r.draw(f, t, screen); return f
f0, f1, f2 = circ(0.02, space="screen"), circ(0.14, space="screen"), circ(1.0, space="screen")
n0, n1, n2 = changed(f0).sum(), changed(f1).sum(), changed(f2).sum()
check(n0 < n1 < n2, f"circle draws on progressively ({n0} < {n1} < {n2})")
check(not changed(f2)[960, 540] and not changed(f2)[900:1020, 480:600].any(), "centre of the ring is empty")
rpx = 0.12 * 1080
ring = [(540 + rpx * np.cos(a), 960 + rpx * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 24, endpoint=False)]
hits = sum(changed(f2)[int(y) - 14:int(y) + 15, int(x) - 14:int(x) + 15].any() for x, y in ring)
check(hits >= 22, f"strokes follow the ellipse ({hits}/24 sample points)")
col = f2[changed(f2)]
check(((col[:, 0] > 200) & (col[:, 1] < 90)).sum() > 3000, "stroke is red")
check(not changed(circ(2.5, space="screen")).any() and not changed(circ(-0.1, space="screen")).any(), "nothing outside the time window")
check(np.abs(circ(1.95, space="screen").astype(int) - BG).sum() < 0.7 * np.abs(f2.astype(int) - BG).sum(), "fades out at the end")

# --- source space follows the camera matrix
M = np.array([[2.0, 0, -1380.0], [0, 2.0, -120.0]], np.float32)     # source (0.5, 0.5) lands at the frame centre
v = A.View(1080, 1920, 1920, 1080, M)
px, py = v.point(0.5, 0.5, "source")
check(abs(px - 540) < 1e-3 and abs(py - 960) < 1e-3, "source point goes through the matrix")
px2, py2 = v.point(0.6, 0.5, "source")
check(abs(px2 - (540 + 2 * 0.1 * 1920)) < 1e-3, "and moves 2x as fast as the picture")
check(abs(v.length(0.1, "source") - 0.1 * 1920 * 2) < 1e-4 and abs(v.length(0.1, "screen") - 108) < 1e-4, "source lengths scale with the zoom")
fa = blank(); A.AnnotationRenderer([dict(type="circle", t0=0, t1=2, x=0.5, y=0.5, r=0.05)]).draw(fa, 1.0, A.View(1080, 1920, 1920, 1080, np.array([[1.0, 0, 0], [0, 1.0, 0]], np.float32)))
fb = blank(); A.AnnotationRenderer([dict(type="circle", t0=0, t1=2, x=0.5, y=0.5, r=0.05)]).draw(fb, 1.0, v)
wa = np.where(changed(fa).any(0))[0]; wb = np.where(changed(fb).any(0))[0]
check((wb.max() - wb.min()) > 1.8 * (wa.max() - wa.min()), "the same circle is ~2x wider when the picture is zoomed 2x")

# --- arrow: shaft first, head last, tip at the target
def arr(t):
    f = blank(); A.AnnotationRenderer([dict(type="arrow", t0=0, t1=2, x0=0.2, y0=0.2, x1=0.6, y1=0.4, space="screen")]).draw(f, t, screen); return f
a1, a2 = changed(arr(0.1)), changed(arr(1.0))
check(a1.sum() < a2.sum(), "arrow draws on")
ys, xs = np.where(a2)
tip = (0.6 * 1080, 0.4 * 1920)
check(abs(xs.max() - tip[0]) < 60 and abs(ys.max() - tip[1]) < 60, f"arrow reaches the target (x {xs.max()}, y {ys.max()})")
check(abs(xs.min() - 0.2 * 1080) < 30, "arrow starts at the tail")
polys0 = A.arrow_polys(100, 100, 400, 100, 0.5); polys1 = A.arrow_polys(100, 100, 400, 100, 1.0)
check(len(polys0) == 1 and len(polys1) == 3, "head strokes appear only at the end")

# nothing drawn yet on the very first frame, and no crash
for kind in (dict(type="arrow", x0=0.2, y0=0.2, x1=0.6, y1=0.4), dict(type="circle", x=0.5, y=0.5, r=0.1)):
    f = blank(); A.AnnotationRenderer([dict(kind, t0=1.0, t1=3.0, space="screen")]).draw(f, 1.0, screen)
    check(not changed(f).any(), f"{kind['type']} at age 0 draws nothing and does not crash")

# --- emoji
f = blank(); A.AnnotationRenderer([dict(type="emoji", t0=0, t1=2, char="🥊", x=0.5, y=0.3, size=0.16, space="screen")]).draw(f, 1.0, screen)
ys, xs = np.where(changed(f))
check(len(ys) > 4000 and abs((xs.min() + xs.max()) / 2 - 540) < 20 and abs((ys.min() + ys.max()) / 2 - 576) < 40, "emoji drawn around its position")
check(abs((xs.max() - xs.min()) - 0.16 * 1080) < 30, f"emoji ~16% of the width (got {xs.max() - xs.min()})")
fs = blank(); A.AnnotationRenderer([dict(type="emoji", t0=0, t1=2, char="🥊", x=0.5, y=0.3, size=0.16, space="screen")]).draw(fs, 0.01, screen)
check(changed(fs).sum() < changed(f).sum() * 0.6, "emoji pops in small")

# --- insets (real files)
with tempfile.TemporaryDirectory() as td:
    img = Image.new("RGB", (400, 250), (20, 60, 200)); img.paste((250, 230, 0), (100, 60, 300, 190)); ip = os.path.join(td, "shot.png"); img.save(ip)
    vp = os.path.join(td, "clip.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=2", "-pix_fmt", "yuv420p", vp], check=True)
    f = blank(); r = A.AnnotationRenderer([dict(type="inset", t0=1.0, t1=3.0, src=ip, label="Chat warning", x=0.5, y=0.25, w=0.6)])
    r.draw(f, 0.5, screen); check(not changed(f).any(), "inset absent before its time")
    r.draw(f, 1.5, screen); ys, xs = np.where(changed(f))
    check(len(ys) > 50000, "inset drawn")
    check(abs((xs.min() + xs.max()) / 2 - 540) < 25, "inset centred horizontally")
    check(ys.max() < 960 and ys.min() > 100, "inset sits in the upper part of the frame")
    blue = ((f[..., 2] > 150) & (f[..., 0] < 60)).sum(); yellow = ((f[..., 0] > 200) & (f[..., 1] > 190) & (f[..., 2] < 60)).sum()
    check(blue > 20000 and yellow > 10000, f"shows the real picture (blue {blue}, yellow {yellow})")
    red = ((f[..., 0] > 220) & (f[..., 1] < 90) & (f[..., 2] < 90)).sum()
    check(red > 1500, f"label pill drawn above the window (red px {red})")
    top_red = np.where(((f[..., 0] > 220) & (f[..., 1] < 90) & (f[..., 2] < 90)).any(1))[0].min()
    top_blue = np.where(((f[..., 2] > 150) & (f[..., 0] < 60)).any(1))[0].min()
    check(top_red < top_blue, "label is above the picture")
    # video: frames change with time
    rv = A.AnnotationRenderer([dict(type="inset", t0=0.0, t1=3.0, src=vp, x=0.5, y=0.25, w=0.5)])
    fa, fb, fc = blank(), blank(), blank()
    rv.draw(fa, 0.1, screen); rv.draw(fb, 1.0, screen)
    check(np.abs(fa.astype(int) - fb.astype(int)).sum() > 100000, "video inset advances")
    rv.draw(fc, 0.1, screen)
    check(np.abs(fa.astype(int) - fc.astype(int)).sum() < 1000, "video inset can jump back")
    f2 = blank(); rv.draw(f2, 2.9, screen)          # past the 2 s file: holds the last frame instead of failing
    check(changed(f2).sum() > 20000, "short clip holds its last frame")
    rv.close(); r.close()

# --- times
words = [dict(w="Fighting", s=1.0, e=1.4), dict(w="Rival?", s=1.5, e=1.9), dict(w="rival", s=4.0, e=4.3)]
res = A.resolve_times([dict(type="circle", at_word="rival"), dict(type="circle", at_word="rival", occurrence=2, dur=1.0, lead=0.1), dict(type="emoji", t0=3.0)], words)
check(abs(res[0]["t0"] - 1.45) < 1e-9 and abs(res[0]["t1"] - 3.25) < 1e-9, "at_word starts just before the word, 1.8 s default")
check(abs(res[1]["t0"] - 4.1) < 1e-9 and abs(res[1]["t1"] - 5.1) < 1e-9, "occurrence, lead and dur")
check(res[2]["t1"] == 4.8, "explicit t0 kept")
try:
    A.resolve_times([dict(type="circle", at_word="zebra")], words); check(False, "unknown word must raise")
except ValueError:
    check(True, "unknown word raises")
check(A.cue_times(res) == sorted(a["t0"] for a in res), "cue times for the sound mixer")
print(f"annotations: {ok} checks passed")
