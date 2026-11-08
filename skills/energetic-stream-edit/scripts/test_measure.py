"""Checks for measure.py.   python3 -I test_measure.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np
import measure as M

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1

# a textured test image, zoomed about its centre by a known factor
rng = np.random.default_rng(3)
img = np.full((480, 270), 90, np.uint8)
for _ in range(220):
    c = (int(rng.integers(0, 270)), int(rng.integers(0, 480))); r = int(rng.integers(4, 18))
    cv2.circle(img, c, r, int(rng.integers(0, 255)), -1)
    cv2.rectangle(img, (c[0] - r, c[1] - r), (c[0] + r, c[1] + r), int(rng.integers(0, 255)), 1)
def zoomed(z):
    T = np.array([[z, 0, 135 * (1 - z)], [0, z, 240 * (1 - z)]], np.float32)
    return cv2.warpAffine(img, T, (270, 480), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
orb = cv2.ORB_create(800)
for z in (1.0, 1.01, 1.05, 1.10):
    got = M.pair_scale(img, zoomed(z), orb)
    check(abs(got - z) < 0.012, f"measured zoom {got:.3f} for a true {z}")
check(np.isnan(M.pair_scale(img, np.full((480, 270), 7, np.uint8), orb)), "blank frame -> nan, not a fake number")

# summarising a series: one jump in (+8%) at 2.0 s, one jump out (-6%) at 3.0 s, a cut at 4.0 s
s = np.full(90, 1.0)
s[30] = 1.08; s[45] = 0.94; s[60:62] = np.nan
r = M.summarize_zoom(s, cuts=[4.0])
check(r["jumps"] == 2 and r["n_in"] == 1 and r["n_out"] == 1, f"one jump in, one out (got {r['n_in']} in, {r['n_out']} out)")
check(abs(r["in_median_pct"] - 8.0) < 0.5 and abs(r["out_median_pct"] - 6.0) < 0.5, "sizes 8% in, 6% out")
check(abs(r["jump_times"][0] - 2.0) < 0.1 and abs(r["jump_gap_median_s"] - 1.0) < 0.1, "times and spacing")
check(r["longest_stretch_no_jump_or_cut_s"] <= 3.1, "longest still stretch")
s2 = np.full(60, 1.0); s2[20] = 1.05; s2[21] = 1.04
check(M.summarize_zoom(s2, [])["jumps"] == 1, "neighbouring steps merge into one jump")
s3 = np.full(60, 1.0); s3[30] = 1.4
check(M.summarize_zoom(s3, [2.05])["jumps"] == 0, "cut steps are ignored")
s4 = np.full(60, 1.0) + rng.normal(0, 0.002, 60)
check(M.summarize_zoom(s4, [])["jumps"] == 0, "per-step noise is not a jump")

# steady push-in over 1 s windows: frames zoomed 3%/s, plus a window that is skipped because of an event
frs = np.stack([zoomed(1 + 0.03 * i / 15) for i in range(75)])
dw = M.drift_windows(frs, [])
check(len(dw) >= 15 and abs(float(np.median(dw)) - 3.0) < 0.5, f"drift 3%/s recovered (median {np.median(dw):.2f})")
check(len(M.drift_windows(frs, [2.5])) < len(dw), "windows holding an event are skipped")
still = np.stack([img for _ in range(60)])
check(abs(float(np.median(M.drift_windows(still, [])))) < 0.2, "a still shot reads ~0 drift")

# loudness parsing reads the Summary block, not the -70 per-frame lines
sample = ("[Parsed_ebur128_0 @ 0x1] t: 0.1 M: -120.7 S: -120.7 I: -70.0 LUFS LRA: 0.0 LU FTPK: -nan dBFS TPK: -nan dBFS\n"
          "[Parsed_ebur128_0 @ 0x1] Summary:\n\n  Integrated loudness:\n    I:         -12.4 LUFS\n    Threshold: -22.6 LUFS\n\n"
          "  Loudness range:\n    LRA:         3.2 LU\n    Threshold: -32.6 LUFS\n\n  True peak:\n    Peak:        0.4 dBFS\n")
p = M.parse_loudness(sample)
check(p["LUFS"] == -12.4 and p["LRA"] == 3.2 and p["true_peak_dB"] == 0.4, f"summary parsed: {p}")
print(f"measure: {ok} checks passed")
