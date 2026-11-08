"""Checks for motion.py.   python3 -I test_motion.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import motion as M

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1

FPS = 30
# --- plain push-in: 3%/s, starts at 1.0, never above the cap
z = M.camera_zoom(300, FPS, rate=0.03)
check(z[0] == 1.0, "starts at 1.0")
check(abs(z[150] - 1.15) < 0.01, f"3%/s over 5 s = 1.15 (got {z[150]:.3f})")
check(np.all(np.diff(z) >= 0), "push-in never zooms out")
check(M.camera_zoom(600, FPS, rate=0.05, max_zoom=1.6).max() <= 1.6, "capped")

# --- a punch is a +8% step over ~0.07 s, then the drift carries on
zp = M.camera_zoom(300, FPS, punches=[3.0], rate=0.0, punch_gain=0.08, ease=0.07)
check(abs(zp[int(2.9 * FPS)] - 1.0) < 1e-9 and abs(zp[int(3.2 * FPS)] - 1.08) < 1e-6, "punch +8% with no drift")
jump = (zp[int(3.1 * FPS)] - zp[int(2.95 * FPS)]) / zp[int(2.95 * FPS)]
check(jump > 0.07, "the jump happens within about 5 frames")

# --- pulse mode: in, out, in ... (bounded) vs ratchet (keeps going in)
zpl = M.camera_zoom(300, FPS, punches=[3.0, 5.0, 7.0], rate=0.0, punch_gain=0.10)
check(abs(zpl[int(4.0 * FPS)] - 1.10) < 1e-6 and abs(zpl[int(6.0 * FPS)] - 1.0) < 1e-6 and abs(zpl[int(8.0 * FPS)] - 1.10) < 1e-6, "pulse: in, out, in")
zrt = M.camera_zoom(300, FPS, punches=[3.0, 5.0], rate=0.0, punch_gain=0.10, mode="ratchet")
check(abs(zrt[int(6.0 * FPS)] - 1.21) < 1e-6, "ratchet: 1.1 x 1.1")
zh = M.camera_zoom(300, FPS, punches=[3.0], rate=0.0, punch_gain=0.10)     # default ease = one frame at 30 fps
check(abs(zh[int(3.0 * FPS) + 1] - 1.10) < 1e-6 and zh[int(3.0 * FPS) - 1] == 1.0, "default punch is a one-frame jump")
zbig = M.camera_zoom(900, FPS, punches=list(np.arange(1, 29, 2.0)), rate=0.01)
check(zbig.max() < 1.45, f"pulse never runs away over 28 s (max {zbig.max():.2f})")

# --- a cut resets the zoom and the accumulated punches
cuts = M.expand_cuts([4.0])
zc = M.camera_zoom(300, FPS, cuts=cuts, punches=[1.0, 2.0], rate=0.03, punch_gain=0.08, mode="ratchet")
before, after = zc[int(3.95 * FPS)], zc[int(4.05 * FPS)]
check(before > 1.2 and abs(after - 1.22 * (1 + 0.03 * 0.05)) < 0.02, f"cut resets to the cut framing (before {before:.2f}, after {after:.2f})")
cuts2 = M.expand_cuts([4.0, 6.0])
check(cuts2[0][1] == 1.22 and cuts2[1][1] == 1.0, "plain cuts alternate close / wide")

# --- bursts: n cuts inside span seconds
b = M.expand_cuts(bursts=[dict(t=10.0, n=4, span=0.5)])
check(len(b) == 4 and abs(b[-1][0] - 10.375) < 1e-9 and b[0][0] == 10.0, "burst gives 4 cuts inside 0.5 s")
check(len({round(x[1], 2) for x in b}) >= 3, "burst cuts differ in framing")

# --- auto punches: emphasis first, then fill so no stretch is longer than 1.45*gap
emph = [(2.0, 9.0), (2.4, 5.0), (8.0, 7.0)]
words = [dict(w="x", s=i * 0.4, e=i * 0.4 + 0.3) for i in range(40)]
P = M.auto_punches(emph, 14.0, words=words, gap=2.7, min_gap=1.5)
check(2.0 in P and 2.4 not in P, "loudest wins, near neighbour dropped")
marks = [0.0] + P + [14.0]
check(max(np.diff(marks)) <= 2.7 * 1.45 + 1e-6, f"no stretch longer than 1.45*gap (max {max(np.diff(marks)):.2f})")
check(all(P[i + 1] - P[i] >= 1.2 for i in range(len(P) - 1)), "punches not bunched")
check(len(P) >= 4, "about one punch per 2.7 s over 14 s")
check(all(p >= 1.0 for p in P), "nothing in the first second (hook stays calm)")
Pn = M.auto_punches([], 14.0, cuts=[(7.0, 1.0)], gap=2.7)
check(all(abs(p - 7.0) > 0.3 for p in Pn), "no punch right on a cut")

# --- shake
dx, dy = M.shake(300, FPS, [3.0], amp=0.01)
check(abs(dx[:90]).max() == 0 and abs(dx[91:100]).max() > 0.002 and abs(dx[200:]).max() < 1e-3, "shake only after the punch and decays")
check(M.shake(10, FPS, [1.0], amp=0)[0].max() == 0, "amp 0 = off")

# --- flashes
fl = [dict(t=1.0, dur=0.4, peak=0.5, color="green")]
check(M.flash_alpha(0.9, fl) == [] and abs(M.flash_alpha(1.0, fl)[0][1] - 0.5) < 1e-9, "flash hits at full strength")
check(M.flash_alpha(1.2, fl)[0][1] < 0.3 and M.flash_alpha(1.5, fl) == [], "flash decays and ends")
f = np.full((20, 20, 3), 100, np.uint8); M.apply_flashes(f, 1.0, fl)
check(f[0, 0, 1] > 150 and f[0, 0, 0] < 100, "green flash raises green, lowers red")
f2 = np.full((20, 20, 3), 100, np.uint8); M.apply_flashes(f2, 5.0, fl)
check((f2 == 100).all(), "no change outside the flash")
w = np.full((4, 4, 3), 120, np.uint8); M.warm_grade(w, 1.0)
check(w[0, 0, 0] > 120 > w[0, 0, 2], "warm grade: more red, less blue")

# --- build_motion end to end
m = M.build_motion(14.0, FPS, dict(rate=0.025, cuts=[7.0], flashes=[dict(t=7.0, color="white")]), emph=emph, words=words)
check(len(m["zoom"]) == 420 and m["zoom"].min() >= 1.0 and m["zoom"].max() <= 1.6, "zoom array sane")
check(len(m["punches"]) >= 3 and m["cuts"][0][0] == 7.0, "punches and cuts carried through")
m2 = M.build_motion(14.0, FPS, dict(auto_punch=False))
check(m2["punches"] == [], "auto_punch off")
m3 = M.build_motion(14.0, FPS, dict(punches=[5.0, 2.0]))
check(m3["punches"] == [2.0, 5.0], "explicit punches sorted")
print(f"motion: {ok} checks passed")
