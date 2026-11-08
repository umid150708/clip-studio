"""Checks for render.py geometry, focus and word handling.   python3 -I test_render.py"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import render as R

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1

# camera window: 16:9 source, zoom 1 -> full-height 9:16 strip
Mx, (x0, y0, w, h) = R.camera_matrix(1920, 1080, 1.0, 0.5, 0.5)
check(abs(h - 1080) < 1e-6 and abs(w - 607.5) < 0.1 and abs(x0 - (960 - 303.75)) < 0.1, "zoom 1 = 607x1080 strip centred")
check(abs(Mx[0, 0] - 1080 / 607.5) < 1e-4, "scale maps the strip onto 1080 wide")
# zoom 2 halves the window
_, (x0, y0, w2, h2) = R.camera_matrix(1920, 1080, 2.0, 0.5, 0.5)
check(abs(w2 - w / 2) < 1e-6 and abs(h2 - 540) < 1e-6, "zoom 2 halves the window")
# the window never leaves the source
_, (x0, y0, w3, h3) = R.camera_matrix(1920, 1080, 1.5, 0.0, 0.0)
check(x0 == 0 and y0 == 0, "clamped at the top-left corner")
_, (x0, y0, w3, h3) = R.camera_matrix(1920, 1080, 1.5, 1.0, 1.0)
check(abs(x0 + w3 - 1920) < 1e-6 and abs(y0 + h3 - 1080) < 1e-6, "clamped at the bottom-right corner")
# already-vertical source: zoom 1 is the whole frame
_, (x0, y0, w4, h4) = R.camera_matrix(720, 1280, 1.0, 0.5, 0.5)
check(abs(w4 - 720) < 1e-6 and abs(h4 - 1280) < 1e-6, "9:16 source used whole")
# a window centred on a point maps that point to the output centre
Mx, (x0, y0, w5, h5) = R.camera_matrix(1920, 1080, 1.0, 0.3, 0.5)
px = Mx @ np.array([0.3 * 1920, 540, 1.0])
check(abs(px[0] - 540) < 1 and abs(px[1] - 960) < 1, "focus point lands mid-frame")

# focus keyframes
k = [dict(t=0, x=0.3), dict(t=2, x=0.7)]
check(R.focus_at(k, -1)[0] == 0.3 and R.focus_at(k, 5)[0] == 0.7 and abs(R.focus_at(k, 1)[0] - 0.5) < 1e-9, "focus eases between keys")
check(R.focus_at(None, 1) == (0.5, 0.5), "default focus is the centre")

# words: json3 + shift + windowing
d = {"events": [{"tStartMs": 10000, "segs": [{"utf8": "hello"}, {"utf8": " big", "tOffsetMs": 400}, {"utf8": " world", "tOffsetMs": 900}]},
                {"tStartMs": 12000, "segs": [{"utf8": "[Music]"}]}, {"tStartMs": 13000, "segs": [{"utf8": "[ __ ]"}]}]}
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "w.json3"); json.dump(d, open(p, "w"))
    wds = R.load_words(p, shift=-9.0)
    check([x["w"] for x in wds] == ["hello", "big", "world", "***"], "words, music tag dropped, bleep kept as ***")
    check(abs(wds[0]["s"] - 1.0) < 1e-9 and abs(wds[1]["s"] - 1.4) < 1e-9, "shift applied")
    win = R.window_of(wds, 1.3, 2.0)
    check([x["w"] for x in win] == ["big", "world"] and abs(win[0]["s"] - 0.1) < 1e-9, "window relative to the clip start")
    q = os.path.join(td, "w.json"); json.dump([dict(w="a", s=1.0, e=1.2)], open(q, "w"))
    check(R.load_words(q, 0.5)[0]["s"] == 1.5, "plain list accepted")

# loudness chain: a quiet source (about -30 LUFS, bursts every 0.7 s) mastered to -12 LUFS must end under -1 dBTP after the AAC encode
import subprocess, tempfile, measure as MS
with tempfile.TemporaryDirectory() as td:
    quiet = os.path.join(td, "quiet.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:duration=6", "-af",
                    "volume='0.02+0.05*lt(mod(t,0.7),0.05)':eval=frame", "-ar", "44100", quiet], check=True)
    af = R.loudness_args(quiet, 0, 6, -12)
    check("linear=false" in af and "level=disabled" in af and "aresample=192000" in af, "chain: dynamic loudnorm, oversampled limiter, level off")
    out = os.path.join(td, "out.m4a")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", quiet, "-vn", "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", out], check=True)
    r = MS.loudness(out)
    check(r["true_peak_dB"] <= R.CEILING_DBTP, f"quiet source: true peak {r['true_peak_dB']} dBTP is under the {R.CEILING_DBTP} ceiling")
    check(abs(r["LUFS"] + 12) < 1.5, f"quiet source: loudness {r['LUFS']} LUFS near the -12 target")
print(f"render: {ok} checks passed")