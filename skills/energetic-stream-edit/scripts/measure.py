#!/usr/bin/env python3
"""Measure a Short the same way the six viral references were measured, so my output can be compared with them.

  python3 -I measure.py FILE.mp4 [FILE2.mp4 ...] [--json out.json]

Reports: hard cuts per 10 s; zoom JUMPS (punch-in / punch-out: count, direction, size, spacing); steady push-in (%/s, measured over
1-second windows with no cut or jump); loudness (LUFS, true peak); where the yellow caption text sits. Zoom = scale of the best
similarity transform between ORB matches; the caption band is masked so static text does not pull the estimate toward 1.0.
Note: per-step (1/15 s) scale has noise of roughly +-0.2%, so a steady push-in must be read from 1-second windows, never from per-step medians.
"""
import argparse, json, math, re, subprocess, sys
import cv2
import numpy as np

STEP_FPS = 15
JUMP = 0.03            # a zoom of 3% or more between two samples 1/15 s apart is a jump (punch-in / punch-out)
CAP_BAND = (0.40, 0.56)


def decode(path, vf, w, h, pix="gray"):
    ch = 3 if pix == "rgb24" else 1
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"])
    a = np.frombuffer(raw, np.uint8)
    return a.reshape(-1, h, w, 3) if ch == 3 else a.reshape(-1, h, w)


def cut_times(path):
    """Hard cuts: frame-difference spikes on a tiny grey copy at 30 fps (identical method to the study's analyze.py)."""
    fr = decode(path, "fps=30,scale=72:128,format=gray", 72, 128).astype(np.int16)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    thr = max(14.0, 7 * float(np.median(d)))
    cuts, last = [], -1
    for i, x in enumerate(d):
        if x > thr and (last < 0 or i - last > 5):
            cuts.append((i + 1) / 30); last = i
    return cuts, len(fr) / 30


def pair_scale(a, b, orb, mask=None):
    """Zoom factor between two grey frames (>1 = b is closer than a), or nan if there is not enough to match."""
    ka, da = orb.detectAndCompute(a, mask); kb, db = orb.detectAndCompute(b, mask)
    if da is None or db is None or len(ka) < 15 or len(kb) < 15:
        return float("nan")
    m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db), key=lambda x: x.distance)[:200]
    if len(m) < 15:
        return float("nan")
    pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
    T, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if T is None or inl is None or int(inl.sum()) < 12:
        return float("nan")
    return float(math.hypot(T[0, 0], T[1, 0]))


def load_gray(path, w=270, h=480):
    return decode(path, f"fps={STEP_FPS},scale={w}:{h},format=gray", w, h)


def caption_mask(h, w):
    m = np.full((h, w), 255, np.uint8); m[int(CAP_BAND[0] * h): int(CAP_BAND[1] * h)] = 0
    return m


def step_series(fr):
    """Zoom between each pair of neighbouring samples (1/15 s)."""
    orb = cv2.ORB_create(800); mask = caption_mask(*fr.shape[1:])
    return np.array([pair_scale(fr[i], fr[i + 1], orb, mask) for i in range(len(fr) - 1)])


def summarize_zoom(s, cuts, thr=JUMP):
    """s[i] = zoom between sample i and i+1. Steps that hold a hard cut are ignored. A jump is a step of |zoom-1| >= thr;
    neighbouring steps (within 0.3 s) add up to one jump. In = zoom in (+), out = zoom out (-)."""
    s = np.array(s, float); t = np.arange(len(s)) / STEP_FPS
    cut_step = np.zeros(len(s), bool)
    for c in cuts:
        i = int(c * STEP_FPS); cut_step[max(0, i - 1): i + 1] = True
    ok = ~np.isnan(s) & ~cut_step
    d = np.where(ok, s - 1, 0.0)
    jt, js = [], []
    for i in np.where(ok & (np.abs(d) >= thr))[0]:
        if jt and t[i] - jt[-1] < 0.3:
            js[-1] += d[i]
        else:
            jt.append(float(t[i])); js.append(float(d[i]))
    ins = [x for x in js if x > 0]; outs = [-x for x in js if x < 0]
    dur = len(s) / STEP_FPS
    marks = sorted([0.0] + jt + list(cuts) + [dur])
    med = lambda v: round(float(np.median(v)) * 100, 1) if v else None
    return dict(valid_share=round(float(ok.mean()), 2) if len(s) else 0.0, jumps=len(jt), jumps_per_10s=round(len(jt) / dur * 10, 1) if dur else 0,
                n_in=len(ins), n_out=len(outs), in_median_pct=med(ins), out_median_pct=med(outs),
                jump_gap_median_s=round(float(np.median(np.diff(jt))), 2) if len(jt) > 1 else None, jump_times=[round(x, 2) for x in jt],
                longest_stretch_no_jump_or_cut_s=round(float(max(np.diff(marks))), 2))


def drift_windows(fr, events, k=STEP_FPS, stride=3, margin=0.1):
    """Steady push-in: zoom between frames one second apart (direct match, so per-step noise does not accumulate), counting only
    windows that contain no hard cut and no jump. Returns a list of %/s."""
    orb = cv2.ORB_create(800); mask = caption_mask(*fr.shape[1:]); out = []
    for i in range(0, len(fr) - k, stride):
        t0, t1 = i / STEP_FPS, (i + k) / STEP_FPS
        if any(t0 - margin <= e <= t1 + margin for e in events):
            continue
        sc = pair_scale(fr[i], fr[i + k], orb, mask)
        if not math.isnan(sc):
            out.append((sc - 1) * 100 / ((k) / STEP_FPS))
    return out


def parse_loudness(err):
    """Read the Summary block of ffmpeg's ebur128 output (the per-frame lines above it start at -70)."""
    blk = err[err.rindex("Summary:"):]
    g = lambda pat: float(re.search(pat, blk).group(1))
    return dict(LUFS=g(r"I:\s+(-?[\d.]+) LUFS"), LRA=g(r"LRA:\s+([\d.]+) LU"), true_peak_dB=g(r"Peak:\s+(-?[\d.]+) dBFS"))


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    return parse_loudness(err)


def caption_height(path, w=270, h=480):
    """Median vertical centre (fraction of frame height) of yellow caption pixels, over frames that have enough of them."""
    fr = decode(path, f"fps=5,scale={w}:{h}", w, h, "rgb24").astype(np.int16)
    ys = []
    for f in fr:
        m = (f[..., 0] > 235) & (f[..., 1] > 205) & (f[..., 1] < 250) & (f[..., 2] < 70)
        if m.sum() > 60:
            r = np.where(m)[0]; ys.append(float(np.median(r)) / h)
    return dict(yellow_caption_frames=round(len(ys) / max(1, len(fr)), 2), yellow_caption_centre_y=round(float(np.median(ys)), 3) if ys else None)


def measure(path):
    cuts, dur = cut_times(path)
    fr = load_gray(path)
    st = step_series(fr)
    out = dict(file=path, dur=round(dur, 2), cuts_per_10s=round(len(cuts) / dur * 10, 1), cuts=[round(c, 2) for c in cuts])
    j = summarize_zoom(st, cuts); out.update(j)
    dr = drift_windows(fr, list(cuts) + j["jump_times"])
    out["drift_windows"] = len(dr)
    out["pushin_pct_per_s_median"] = round(float(np.median(dr)), 2) if dr else None
    out["pushin_pct_per_s_p75"] = round(float(np.percentile(dr, 75)), 2) if dr else None
    out.update(loudness(path)); out.update(caption_height(path))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+"); ap.add_argument("--json", default=None)
    a = ap.parse_args()
    rows = [measure(f) for f in a.files]
    keys = ["dur", "cuts_per_10s", "jumps_per_10s", "n_in", "n_out", "in_median_pct", "out_median_pct", "jump_gap_median_s", "pushin_pct_per_s_median",
            "longest_stretch_no_jump_or_cut_s", "LUFS", "true_peak_dB", "yellow_caption_centre_y"]
    short = dict(dur="dur_s", cuts_per_10s="cuts/10s", jumps_per_10s="jumps/10s", n_in="in", n_out="out", in_median_pct="in%med", out_median_pct="out%med", jump_gap_median_s="gap_s",
                 pushin_pct_per_s_median="drift%/s", longest_stretch_no_jump_or_cut_s="still_s", LUFS="LUFS", true_peak_dB="TPdB", yellow_caption_centre_y="cap_y")
    print(f"{'':30}" + "".join(f"{short[k]:>10}" for k in keys))
    for r in rows:
        print(f"{r['file'].split('/')[-1][:29]:30}" + "".join(f"{str(r.get(k)):>10}" for k in keys))
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
