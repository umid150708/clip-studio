"""Checks for mixer.py.  The kit used here is made of test tones in a temp folder: fixtures for the placement logic only, never shipped.
   python3 -I test_mixer.py"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import mixer as X

ok = 0
def check(cond, msg):
    global ok
    assert cond, "FAIL: " + msg
    ok += 1

SR = X.SR
def wav(path, x):
    X.write_wav(path, x.astype(np.float32))

def fixture_kit(td, kinds=("impact", "pop", "click", "whoosh", "riser"), n_per=2, license="CC0"):
    os.makedirs(os.path.join(td, "files"), exist_ok=True)
    kit = {"kinds": {}}
    t = np.arange(int(0.6 * SR)) / SR
    for kind in kinds:
        for i in range(n_per):
            lead = 0.08 + 0.01 * i                                     # silence before the sound: placement must align the AUDIBLE start
            body = np.sin(2 * np.pi * (60 + 40 * i) * t) * np.exp(-t * 8)
            if kind == "riser":
                tt = np.arange(int(1.0 * SR)) / SR; body = np.sin(2 * np.pi * (200 + 900 * tt) * tt) * tt; lead = 0.02
            x = np.concatenate([np.zeros(int(lead * SR)), body]) * (0.5 + 0.2 * i)
            f = f"files/{kind}_{i}.wav"; wav(os.path.join(td, f), x)
            kit["kinds"].setdefault(kind, []).append(dict(file=f, license=license, url=f"https://example.invalid/{kind}/{i}", author="fixture"))
    json.dump(kit, open(os.path.join(td, "kit.json"), "w"))
    return td

with tempfile.TemporaryDirectory() as td:
    kd = fixture_kit(os.path.join(td, "kit"))
    kit = X.Kit(kd)
    # --- kit rules
    peaks = [np.abs(x).max() for k in kit.clips.values() for _, x in k]
    check(all(abs(20 * np.log10(p) + 3) < 0.05 for p in peaks), "every clip normalised to -3 dBFS peak")
    check(kit.missing(["impact", "boing"]) == ["boing"], "missing kinds reported")
    bad = os.path.join(td, "bad"); os.makedirs(os.path.join(bad, "files")); wav(os.path.join(bad, "files/a.wav"), np.ones(4800) * 0.3)
    json.dump({"kinds": {"impact": [{"file": "files/a.wav", "url": "https://example.invalid"}]}}, open(os.path.join(bad, "kit.json"), "w"))
    try:
        X.Kit(bad); check(False, "an entry with no licence must be refused")
    except ValueError as e:
        check("license" in str(e), "an entry with no licence is refused")
    try:
        X.Kit(os.path.join(td, "nowhere")); check(False, "no kit must raise")
    except X.MissingSounds as e:
        check("nothing is synthesised" in str(e), "no kit -> clear refusal, no synthetic fallback")

    # --- placement: the audible start lands on the cue
    cues = [dict(t=2.0, kind="impact"), dict(t=3.5, kind="pop")]
    track, placed, dips = X.build_track(cues, kit, 6.0)
    def first_above(x, a, b, thr=0.01):
        i = np.where(np.abs(x[int(a * SR): int(b * SR)]) > thr)[0]; return (i[0] / SR + a) if len(i) else None
    t_imp = first_above(track, 1.5, 2.9, 0.02)
    check(abs(t_imp - 2.0) < 0.01, f"impact onset on the cue (got {t_imp:.3f})")
    t_pop = first_above(track, 3.0, 5.0, 0.01)
    check(abs(t_pop - 3.5) < 0.01, f"pop onset on the cue (got {t_pop:.3f})")
    check(len(track) == 6 * SR, "track is exactly the clip length")
    check([p["kind"] for p in placed] == ["impact", "pop"] and all("file" in p for p in placed), "placements reported")

    # --- clips are used as recorded: no pitch or speed change
    t1, p1, _ = X.build_track([dict(t=2.0, kind="impact")], kit, 4.0, seed=1)
    gain = 10 ** (p1[0]["gain_db"] / 20)
    used = []
    for e2, x2 in kit.clips["impact"]:
        st2 = int(round(2.0 * SR)) - X.onset(x2)
        if np.allclose(t1[st2: st2 + len(x2)], x2 * gain, atol=0.01):
            used.append(e2["file"])
    check(len(used) == 1, "placed samples are the recording itself, only scaled")

    # --- anchor "peak": the loudest point lands on the cue (whooshes swell into the flash)
    kd3 = os.path.join(td, "kit3"); os.makedirs(os.path.join(kd3, "files"))
    tt = np.arange(int(1.0 * SR)) / SR
    wav(os.path.join(kd3, "files/w.wav"), (np.sin(2 * np.pi * 300 * tt) * np.sin(np.pi * tt / 1.0) ** 2).astype(np.float32))   # swells, peaks at 0.5 s
    json.dump({"kinds": {"whoosh": [dict(file="files/w.wav", license="CC0", url="https://example.invalid", anchor="peak")]}}, open(os.path.join(kd3, "kit.json"), "w"))
    tw, _, _ = X.build_track([dict(t=2.0, kind="whoosh")], X.Kit(kd3), 4.0)
    pk = int(np.argmax(np.abs(tw))) / SR
    check(abs(pk - 2.0) < 0.01, f"whoosh peak lands on the cue (got {pk:.3f})")

    # --- never the same clip twice running
    t2, p2, _ = X.build_track([dict(t=1 + i * 0.5, kind="pop") for i in range(8)], kit, 6.0)
    check(all(p2[i]["file"] != p2[i + 1]["file"] for i in range(len(p2) - 1)), "no clip repeats back to back")

    # --- fake-out: riser ends 0.3 s before the hit, the original audio drops out, then the hit
    tr, pl, dp = X.build_track([dict(t=4.0, kind="fakeout", gap=0.3)], kit, 6.0)
    check([p["kind"] for p in pl] == ["riser", "impact"] and abs(pl[0]["t"] - 3.7) < 1e-9 and abs(pl[1]["t"] - 4.0) < 1e-9, "fakeout = riser then impact")
    check(abs(dp[0][0] - 3.7) < 1e-9 and abs(dp[0][1] - 4.0) < 1e-9, "dip spans the gap")
    gap_peak = np.abs(tr[int(3.72 * SR): int(3.98 * SR)]).max(); riser_peak = np.abs(tr[int(3.0 * SR): int(3.7 * SR)]).max()
    check(riser_peak > 0.05 and gap_peak < 0.01, f"near-silence between the riser and the hit (gap {gap_peak:.4f}, riser {riser_peak:.3f})")
    orig = np.full((6 * SR, 2), 0.3, np.float32)
    m = X.mix(orig, tr, dp)
    check(np.abs(m[int(3.75 * SR): int(3.95 * SR)]).max() < 0.02, "original audio dipped ~40 dB in the gap")
    check(abs(m[int(1.0 * SR)].mean() - 0.3) < 1e-4 and abs(m[int(5.5 * SR)].mean() - 0.3) < 1e-4, "original untouched elsewhere")
    check(np.abs(m[int(4.0 * SR): int(4.2 * SR)]).max() > 0.3, "hit is loud right after the dip")

    # --- ducking under a loud effect, and mono input works
    loud = np.zeros(2 * SR, np.float32); loud[SR: SR + 4800] = 0.9
    md = X.mix(np.full(2 * SR, 0.3, np.float32), loud, [])
    check(md.ndim == 1 and len(md) == 2 * SR, "mono in, mono out")
    check(abs(md[0] - 0.3) < 1e-6, "no ducking away from effects")

    # --- cue derivation
    info = dict(title=dict(t0=0.0), annotations=[dict(type="circle", t0=3.0), dict(type="inset", t0=5.0)],
                flashes=[dict(t=6.0, color="white"), dict(t=7.0, color="green")], end_card_t=9.0, cuts=[2.0, 2.05, 4.0], accents=[1.0])
    c = X.derive_cues(info)
    kinds = sorted((round(x["t"], 2), x["kind"]) for x in c)
    check(kinds == [(0.0, "impact"), (3.0, "pop"), (5.0, "whoosh"), (6.0, "whoosh"), (7.0, "impact"), (9.0, "impact")], f"auto cues {kinds}")
    c3 = X.derive_cues(dict(annotations=[dict(type="circle", t0=1.0), dict(type="arrow", t0=2.0), dict(type="inset", t0=3.0), dict(type="emoji", t0=4.0)]),
                       dict(title=False, flashes=False, end_card=False, annotation_kinds=["pop", "click"]))
    check([x["kind"] for x in sorted(c3, key=lambda x: x["t"])] == ["pop", "click", "whoosh", "pop"], "annotation cues alternate pop / click, windows stay whoosh")
    c2 = X.derive_cues(info, dict(cuts=True, caption_clicks=True, title=False))
    check(sum(x["kind"] == "click" for x in c2) == 4 and not any(x["t"] == 0.0 for x in c2), "cuts and caption accents add clicks; title can be switched off")
    check(len(X.tidy([dict(t=2.0, kind="click"), dict(t=2.05, kind="click"), dict(t=2.05, kind="pop"), dict(t=2.3, kind="click")])) == 3, "tidy drops a same-kind cue closer than 0.1 s")

    # --- missing sounds are named, never faked
    kd2 = fixture_kit(os.path.join(td, "kit2"), kinds=("pop",))
    try:
        X.build_track([dict(t=1.0, kind="impact"), dict(t=2.0, kind="whoosh"), dict(t=3.0, kind="pop")], X.Kit(kd2), 4.0); check(False, "must refuse")
    except X.MissingSounds as e:
        check("impact" in str(e) and "whoosh" in str(e) and "pop" not in str(e).split("for:")[1].split("(")[0], "refusal names exactly the missing kinds")

    # --- end to end with a real file
    src = os.path.join(td, "src.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=30:duration=6", "-f", "lavfi", "-i", "sine=f=300:duration=6", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", src], check=True)
    out = os.path.join(td, "mix.wav")
    rep = X.make_mix(src, 1.0, 4.0, dict(kit=kd, auto=dict(title=True), cues=[dict(t=2.0, kind="fakeout")]), dict(title=dict(t0=0.0), end_card_t=3.2), out)
    a = X.decode(out, 2)
    check(a.shape == (4 * SR, 2), f"mix is 4 s stereo (got {a.shape})")
    check(len(rep["placements"]) == 4 and rep["dips"] == [(1.7, 2.0)], f"report lists placements and the dip: {rep['dips']}")
    check(np.abs(a[int(1.75 * SR): int(1.95 * SR)]).max() < 0.03, "the dip is audible in the final mix")
    out2 = os.path.join(td, "mix_none.wav")
    X.make_mix(src, 1.0, 4.0, dict(kit=kd, auto=dict(title=False, annotations=False, flashes=False, end_card=False)), {}, out2)
    a2 = X.decode(out2, 2)
    o2 = np.frombuffer(subprocess.check_output(["ffmpeg", "-v", "error", "-ss", "1.0", "-t", "4.0", "-i", src, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]), np.float32).reshape(-1, 2)
    check(np.abs(a2 - o2).max() < 1e-4, "no cues -> the original audio comes through untouched")
print(f"mixer: {ok} checks passed")
