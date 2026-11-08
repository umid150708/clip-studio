"""Where the speaker leans on a word: loud onsets relative to the surrounding speech. Used to place zoom jumps (motion.auto_punches)."""
import subprocess

import numpy as np


def audio(path, sr, ch):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"])
    a = np.frombuffer(raw, np.float32)
    return a.reshape(-1, ch) if ch > 1 else a


def emphasis(base, words):
    """[(time_s, score_dB)] of loud onsets in the audio of `base`, snapped to the nearest word start when words [{'w','s','e'}] are given."""
    a = audio(base, 16000, 1)
    hop = 160
    n = len(a) // hop
    if n < 60:
        return []
    rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-6
    db = 20 * np.log10(rms)
    sm = np.convolve(db, np.ones(8) / 8, mode="same")
    med = np.array([np.median(sm[max(0, i - 150): i + 150]) for i in range(n)])
    score = sm - med
    out = []
    for i in range(20, n - 20):
        if score[i] > 4.0 and score[i] == score[i - 20: i + 20].max():
            t = i * hop / 16000 - 0.12
            if words:
                ws = min(words, key=lambda w: abs(w["s"] - t))
                if abs(ws["s"] - t) < 0.3:
                    t = ws["s"]
            out.append((max(t, 0.0), float(score[i])))
    return out
