#!/usr/bin/env python3
"""Measure sound-kit candidates (I cannot hear them, so I measure): length, peak, onset sharpness, decay, low-frequency share,
separate hits inside the file, and for risers whether loudness and brightness actually climb.

  python3 -I kit_analyze.py FILE [FILE ...] [--json out.json]
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mixer as X

SR = X.SR
HOP = int(0.010 * SR)          # 10 ms
WIN = int(0.020 * SR)


def envelope_db(x):
    n = (len(x) - WIN) // HOP + 1
    if n <= 0:
        return np.array([-120.0])
    r = np.array([np.sqrt(np.mean(x[i * HOP: i * HOP + WIN] ** 2)) for i in range(n)])
    return 20 * np.log10(r + 1e-9)


def hits(env_db, min_gap_s=0.12, rise_db=10.0, floor_db=-45.0):
    """Frame indices where the level jumps >= rise_db within 40 ms and is a local maximum within min_gap_s: separate hits / clicks."""
    out, last = [], -10**9
    gap = int(min_gap_s / 0.010)
    for i in range(4, len(env_db) - 1):
        if env_db[i] < floor_db:
            continue
        if env_db[i] - env_db[i - 4: i].min() >= rise_db and env_db[i] == env_db[max(0, i - gap): i + gap + 1].max() and i - last >= gap:
            out.append(i); last = i
    return out


def analyze(path):
    x = X.decode(path)
    d = len(x) / SR
    pk = float(np.abs(x).max()) or 1e-9
    env = envelope_db(x)
    top = env.max()
    onset_i = int(np.argmax(env > top - 30))
    peak_i = int(np.argmax(env))
    after = env[peak_i:]
    dec = np.where(after < top - 30)[0]
    spec = np.abs(np.fft.rfft(x[: min(len(x), SR * 20)] * np.hanning(min(len(x), SR * 20)))) ** 2
    fq = np.fft.rfftfreq(min(len(x), SR * 20), 1 / SR)
    low = float(spec[fq < 200].sum() / (spec.sum() + 1e-12))
    thirds = np.array_split(x, 3)
    def centroid(seg):
        if len(seg) < 1024:
            return 0.0
        s = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; f = np.fft.rfftfreq(len(seg), 1 / SR)
        return float((s * f).sum() / (s.sum() + 1e-12))
    rms3 = [20 * np.log10(np.sqrt(np.mean(t ** 2)) + 1e-9) for t in thirds]
    cen3 = [centroid(t) for t in thirds]
    h = hits(env)
    return dict(file=os.path.basename(path), seconds=round(d, 2), peak_dbfs=round(20 * np.log10(pk), 1),
                onset_s=round(onset_i * 0.01, 2), time_to_peak_s=round((peak_i - onset_i) * 0.01, 2),
                decay_to_minus30db_s=round(dec[0] * 0.01, 2) if len(dec) else None,
                low_share_below_200hz=round(low, 2), n_hits=len(h), hit_times=[round(i * 0.01, 2) for i in h][:40],
                thirds_rms_db=[round(float(v), 1) for v in rms3], thirds_centroid_hz=[round(c) for c in cen3],
                rises=bool(rms3[2] > rms3[0] + 3 or cen3[2] > cen3[0] * 1.25))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--json")
    a = ap.parse_args()
    rows = [analyze(f) for f in a.files]
    for r in rows:
        print(f"{r['file'][:62]:62} {r['seconds']:6.2f}s pk{r['peak_dbfs']:6.1f} onset{r['onset_s']:5.2f} rise{r['time_to_peak_s']:5.2f} decay30={r['decay_to_minus30db_s']} "
              f"low={r['low_share_below_200hz']:.2f} hits={r['n_hits']} rms3={r['thirds_rms_db']} cen3={r['thirds_centroid_hz']} rises={r['rises']}")
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
