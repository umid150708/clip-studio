"""Checks for captions.py.   python3 -I test_captions.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import captions as C

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1

# censor
check(C.censor("fuck") == "f*ck", "fuck -> f*ck")
check(C.censor("FUCKING") == "F*CKING", "keeps case")
check(C.censor("shit.") == "sh*t.", "shit")
check(C.censor("ass") == "a**" and C.censor("class") == "class", "ass only as a whole word")
check(C.censor("hello") == "hello", "clean word untouched")

# roles
check(C.role_of("Ambulance!") == "danger" and C.role_of("W") == "positive" and C.role_of("wait") == "accent" and C.role_of("table") is None, "roles")

# markup
segs = C.parse_markup("the girl {red|notice} *looks at her* livestream")
check([s["text"] for s in segs] == ["THE", "GIRL", "NOTICE", "*LOOKS AT HER*", "LIVESTREAM"], "markup text")
check(segs[2]["color"] == "red" and segs[3]["kind"] == "action" and segs[3]["color"] == "pink", "markup colours")

# auto events from words
words = [dict(w=w, s=i * 0.3, e=i * 0.3 + 0.25) for i, w in enumerate("oh no wait that is fucking crazy".split())]
words.append(dict(w="great!", s=2.6, e=2.9))
ev = C.build_events_from_words(words, mode="word")
check(len(ev) == len(words), "one event per word")
check(all(e["t1"] > e["t0"] for e in ev), "positive durations")
check(all(ev[i]["t1"] <= ev[i + 1]["t0"] + 0.45 for i in range(len(ev) - 1)), "events do not pile up")
txt = [e["segs"][0]["text"] for e in ev]
check("F*CKING" in txt, "profanity censored in captions")
check(ev[1]["segs"][0]["color"] == C.PALETTES["yellow-cyan"]["accent"], "NO is an accent word (cyan)")
check(ev[-1]["segs"][0]["color"] == C.PALETTES["yellow-cyan"]["positive"], "GREAT! is positive (green)")
pe = C.build_events_from_words(words, mode="phrase", per=3)
check(all(len(e["segs"]) <= 3 for e in pe) and pe[0]["mode"] == "phrase", "phrase groups of at most 3")

# rendering
R = C.CaptionRenderer(1080, 1920, size=100, y=0.47)
f = np.zeros((1920, 1080, 3), np.uint8) + 60
R.draw(f, ev, 0.31)       # 'NO'
ys, xs = np.where((f != 60).any(axis=2))
check(len(ys) > 2000, "something was drawn")
cy = (ys.min() + ys.max()) / 2 / 1920
check(abs(cy - 0.47) < 0.03, f"caption centre at ~47% height (got {cy:.3f})")
check(abs((xs.min() + xs.max()) / 2 / 1080 - 0.5) < 0.02, "caption centred horizontally")
# nothing drawn when no event is active
g = np.zeros((1920, 1080, 3), np.uint8) + 60; R.draw(g, ev, 10.0)
check((g == 60).all(), "no caption outside any event")
# the pop-in: the caption is larger right at the start than 0.2 s later
a = np.zeros((1920, 1080, 3), np.uint8) + 60; R.draw(a, ev, 0.3 + 0.005)
b = np.zeros((1920, 1080, 3), np.uint8) + 60; R.draw(b, ev, 0.3 + 0.2)
wa = np.where((a != 60).any(axis=2))[1]; wb = np.where((b != 60).any(axis=2))[1]
check((wa.max() - wa.min()) > (wb.max() - wb.min()) * 1.05, "pop-in: bigger at the start")
# long text wraps and still fits the frame
long = C.build_events_from_script([dict(t0=0, t1=2, text="this is a very long caption that must wrap onto two lines nicely")])
h = np.zeros((1920, 1080, 3), np.uint8) + 60; R.draw(h, long, 1.0)
xs2 = np.where((h != 60).any(axis=2))[1]
check(xs2.min() >= 0 and xs2.max() <= 1079 and (xs2.max() - xs2.min()) < 1080 * 0.95, "long caption stays inside the frame")
print(f"captions: {ok} checks passed")
