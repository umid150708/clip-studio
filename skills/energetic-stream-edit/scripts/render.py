#!/usr/bin/env python3
"""Energetic-style renderer: one source clip -> 1080x1920 Short with coloured captions, push-in/punch motion, flashes, end line.

  python3 -I render.py plan.json OUT.mp4 [--lufs -12] [--peek 0.5,3.2,7]   (--peek writes stills next to OUT and skips the encode)

This is the ENERGETIC STREAM profile (hot loudness, motion layer, colour captions, sound effects). The calmer campaign profile (no SFX, -16 LUFS, head-tracking) belongs to the podcast-clip-studio skill.
The original audio is kept. No sound effects are added here (they come from a real-recording kit, built separately).

plan.json (times in seconds; caption/title/flash times are relative to the START of the clip):
  {"source": "segments/x.mp4", "start": 23.55, "end": 38.0,
   "words": "subs/x.en.json3", "words_shift": -705.0,          # word-timed transcript (YouTube json3), or a [{"w","s","e"}] json list
   "captions": {"mode": "word"|"phrase"|"script"|"none", "size": 84, "y": 0.47, "style": "upright", "glow": false, "palette": "yellow-cyan", "per": 3},
   "script": [{"t0": 1.0, "t1": 2.4, "text": "the girl {red|notice} *looks at her*"}],     # for mode "script"
   "title": {"lines": ["THE MOMENT", "HITS DIFFERENT"], "colors": ["white", "cyan"], "t0": 0, "t1": 2.0},
   "end_card": {"text": "CHECK LINK IN BIO", "dur": 1.3, "color": "green"},
   "focus": [{"t": 0, "x": 0.5, "y": 0.5}],                    # where the 9:16 window sits in the source (0..1), linear between keys
   "sound": {"auto": {"title": true, "annotations": true, "flashes": true, "end_card": true}, "cues": [{"t": 6.0, "kind": "fakeout"}]},   # real recorded effects from assets/sfx_kit/, see mixer.py
   "annotations": [{"type": "circle", "at_word": "scary", "x": 0.5, "y": 0.31, "r": 0.06}, ...],   # circles, arrows, emoji, labelled real-file insets: see annotations.py
   "motion": {"rate": 0.03, "max_zoom": 1.6, "punch_gain": 0.08, "auto_punch": true, "punches": [..], "cuts": [..], "bursts": [{"t": 5, "n": 4, "span": 0.5}],
              "flashes": [{"t": 6.0, "color": "green", "dur": 0.4, "peak": 0.45}], "white_flash": [7.0], "shake": 0.0, "grade": 0.0}}
"""
import argparse, json, math, os, re, subprocess, sys, tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import annotations as AN
import captions as C
import emphasis as EM
import mixer as MX
import motion as M

OUT_W, OUT_H, FPS = 1080, 1920, 30


# ---------------------------------------------------------------- inputs
def probe(path):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", path]))
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def load_words(path, shift=0.0):
    """YouTube json3 auto-captions (word level) or a ready [{'w','s','e'}] list. Times are shifted by `shift` seconds."""
    d = json.load(open(path))
    if isinstance(d, list):
        return [dict(w=x["w"], s=x["s"] + shift, e=x["e"] + shift) for x in d]
    raw = []
    for ev in d.get("events", []):
        base = ev.get("tStartMs", 0)
        for s in ev.get("segs") or []:
            w = s.get("utf8", "").strip()
            if w and w != "\n":
                raw.append({"w": w, "s": (base + s.get("tOffsetMs", 0)) / 1000 + shift})
    out = []
    for a, b in zip(raw, raw[1:] + [None]):
        w = a["w"].replace(">>", "").strip()
        if w in ("", "[Music]", "[Applause]", "[Laughter]"):
            continue
        if "[ __ ]" in w:
            w = "***"
        out.append({"w": w, "s": a["s"], "e": min(b["s"], a["s"] + 0.6) if b else a["s"] + 0.5})
    return out


def window_of(words, start, end):
    return [dict(w=x["w"], s=x["s"] - start, e=min(x["e"], end) - start) for x in words if start - 0.02 <= x["s"] < end]


def focus_at(keys, t):
    keys = sorted(keys or [{"t": 0, "x": 0.5, "y": 0.5}], key=lambda k: k["t"])
    if t <= keys[0]["t"]:
        return keys[0].get("x", 0.5), keys[0].get("y", 0.5)
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t < b["t"]:
            u = (t - a["t"]) / (b["t"] - a["t"]); u = u * u * (3 - 2 * u)
            return a.get("x", 0.5) + (b.get("x", 0.5) - a.get("x", 0.5)) * u, a.get("y", 0.5) + (b.get("y", 0.5) - a.get("y", 0.5)) * u
    return keys[-1].get("x", 0.5), keys[-1].get("y", 0.5)


# ---------------------------------------------------------------- geometry
def camera_matrix(sw, sh, zoom, fx, fy, dx=0.0, dy=0.0, ow=OUT_W, oh=OUT_H):
    """Affine map from the source to the output for a 9:16 window `zoom` times closer than the widest one that fits.
    (fx, fy) = window centre as a fraction of the source; the window is clamped to stay inside it."""
    bw, bh = (sh * ow / oh, float(sh)) if sw / sh > ow / oh else (float(sw), sw * oh / ow)
    w, h = bw / zoom, bh / zoom
    cx, cy = fx * sw + dx * w, fy * sh + dy * h
    x0 = min(max(cx - w / 2, 0.0), sw - w); y0 = min(max(cy - h / 2, 0.0), sh - h)
    s = ow / w
    return np.array([[s, 0, -x0 * s], [0, s, -y0 * s]], np.float32), (x0, y0, w, h)


# ---------------------------------------------------------------- audio
LOUDNESS_TP = -1.5                 # loudnorm's true-peak target: dynamic mode keeps the peaks under it
LIMIT_LINEAR = 10 ** (-2.0 / 20)   # the limiter at -2 dBFS, on a 4x-oversampled grid
CEILING_DBTP = -1.0                # the promise: the finished file's true peak is at or below this


def loudness_args(src, start, dur, lufs):
    """Two-pass loudness master. Pass 1 measures the source. Pass 2 applies the gain in dynamic mode, which keeps the true peak under
    LOUDNESS_TP, then a limiter on a 4x-oversampled grid catches the inter-sample peaks that the AAC encode adds.
    Linear gain is not used: it applies the whole gain even when the peaks would go over the ceiling, and a sample-peak limiter cannot
    catch those (a quiet 20 dB-gain test measured +4.4 dBTP that way)."""
    f = f"loudnorm=I={lufs}:TP={LOUDNESS_TP}:LRA=11:print_format=json"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start}", "-t", f"{dur}", "-i", src, "-vn", "-af", f, "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex("{"): err.rindex("}") + 1])
    return (f"loudnorm=I={lufs}:TP={LOUDNESS_TP}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=false"
            f",aresample=192000,alimiter=limit={LIMIT_LINEAR:.3f}:attack=1:release=50:level=disabled,aresample=48000")


# ---------------------------------------------------------------- the render
def build(plan_path):
    base = os.path.dirname(os.path.abspath(plan_path))
    plan = json.load(open(plan_path))
    res = lambda p: p if os.path.isabs(p) else next((c for c in (os.path.join(base, p), os.path.join(os.getcwd(), p)) if os.path.exists(c)), p)
    src = res(plan["source"])
    sw, sh, sdur = probe(src)
    start = float(plan.get("start", 0.0)); end = float(plan.get("end", sdur)); D = end - start
    n = int(round(D * FPS))
    words = None
    if plan.get("words"):
        words = window_of(load_words(res(plan["words"]), plan.get("words_shift", 0.0)), start, end)
    cap = plan.get("captions", {}); mode = cap.get("mode", "word" if words else "none")
    title = plan.get("title")
    title_end = float(title["t1"]) if title else 0.0
    # speaker emphasis (loud onsets) -> punch candidates
    emph = []
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start}", "-t", f"{D}", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
        emph = EM.emphasis(wav, words)
    mo = M.build_motion(D, FPS, plan.get("motion"), emph=emph, words=words, title_end=title_end)
    # captions
    if mode == "script":
        events = C.build_events_from_script(plan.get("script", []), cap.get("palette", "yellow-cyan"))
    elif mode in ("word", "phrase") and words:
        events = C.build_events_from_words(words, mode=mode, palette=cap.get("palette", "yellow-cyan"), per=cap.get("per", 3))
    else:
        events = []
    rend = C.CaptionRenderer(OUT_W, OUT_H, style=cap.get("style", "upright"), size=cap.get("size", 84), y=cap.get("y", 0.47), glow=cap.get("glow", False))
    neon = C.CaptionRenderer(OUT_W, OUT_H, style="upright", size=96, y=0.5, glow=True)
    if plan.get("sound", {}).get("kit"):
        plan["sound"]["kit"] = res(plan["sound"]["kit"])
    anns = AN.resolve_times(plan.get("annotations"), words)
    ann = AN.AnnotationRenderer(anns, OUT_W, OUT_H, base_dirs=(base, os.getcwd())) if anns else None
    return dict(plan=plan, src=src, sw=sw, sh=sh, start=start, end=end, D=D, n=n, words=words, events=events, mo=mo, rend=rend, neon=neon, title=title, emph=emph, anns=anns, ann=ann)


def render(plan_path, out, lufs=None, peek=None):
    B = build(plan_path)
    plan, mo, n = B["plan"], B["mo"], B["n"]
    peek_frames = {int(round(t * FPS)): t for t in peek} if peek else {}
    enc, tmp = None, None
    if not peek:
        a_in, a_src, a_ss = ["-ss", f"{B['start']}", "-t", f"{B['D']}", "-i", B["src"]], B["src"], B["start"]
        if plan.get("sound"):            # real recorded effects placed on cues; raises MissingSounds (no fakes) if the kit lacks one the plan needs
            tmp = tempfile.TemporaryDirectory(); wavp = os.path.join(tmp.name, "mix.wav")
            end_cfg0 = plan.get("end_card")
            info = dict(title=B["title"], annotations=B["anns"], flashes=mo["flashes"], cuts=[c[0] for c in mo["cuts"]],
                        end_card_t=(B["D"] - end_cfg0.get("dur", 1.3)) if end_cfg0 else None,
                        accents=[e["t0"] for e in B["events"] if any(C.role_of(sg["text"]) or sg["kind"] == "action" for sg in e["segs"])])
            B["sound_report"] = MX.make_mix(B["src"], B["start"], B["D"], plan["sound"], info, wavp)
            a_in, a_src, a_ss = ["-i", wavp], wavp, 0.0
        a_af = ["-af", loudness_args(a_src, a_ss, B["D"], lufs)] if lufs is not None else []
        enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-"]
                               + a_in + ["-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"] + a_af + ["-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{B['start']}", "-t", f"{B['D']}", "-i", B["src"], "-an", "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    sw, sh = B["sw"], B["sh"]; size = sw * sh * 3
    end_cfg = plan.get("end_card")
    try:
        for i in range(n):
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            t = i / FPS
            if peek and i > max(peek_frames):
                break
            src = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
            fx, fy = focus_at(plan.get("focus"), t)
            Mx, _ = camera_matrix(sw, sh, float(mo["zoom"][i]), fx, fy, float(mo["dx"][i]), float(mo["dy"][i]))
            frame = cv2.warpAffine(src, Mx, (OUT_W, OUT_H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            M.warm_grade(frame, mo["grade"])
            M.apply_flashes(frame, t, mo["flashes"])
            if B["ann"]:
                B["ann"].draw(frame, t, AN.View(OUT_W, OUT_H, sw, sh, Mx))
            if B["title"]:
                tl = B["title"]
                B["rend"].draw_title(frame, tl["lines"], tl.get("colors", ["white", "cyan"]), tl.get("t0", 0.0), tl["t1"], t, y=tl.get("y", 0.69), size=tl.get("size", 128))
            in_title = B["title"] and B["title"].get("t0", 0.0) <= t < B["title"]["t1"] and B["title"].get("hide_captions", False)
            in_end = end_cfg and t >= B["D"] - end_cfg.get("dur", 1.3)      # the end line replaces the captions, as in the studied clips
            if not in_title and not in_end:
                B["rend"].draw(frame, B["events"], t)
            if in_end:
                B["neon"].draw_segments(frame, [dict(text=end_cfg["text"].upper(), color=end_cfg.get("color", "green"), kind="word")], B["D"] - end_cfg.get("dur", 1.3), t, y=end_cfg.get("y", 0.5))
            if peek:
                if i in peek_frames:
                    cv2.imwrite(os.path.splitext(out)[0] + f"_t{peek_frames[i]:.2f}.png", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            else:
                enc.stdin.write(frame.tobytes())
    finally:
        if B["ann"]:
            B["ann"].close()
        dec.kill(); dec.stdout.close(); dec.wait()
        if enc:
            enc.stdin.close(); enc.wait()
        if tmp:
            tmp.cleanup()
    return B


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan"); ap.add_argument("out")
    ap.add_argument("--lufs", type=float, default=None, help="master loudness target, e.g. -12 (viral clips sit at -10 to -14)")
    ap.add_argument("--peek", default=None, help="comma-separated clip times: write PNG stills instead of encoding")
    a = ap.parse_args()
    try:
        B = render(a.plan, a.out, a.lufs, [float(x) for x in a.peek.split(",")] if a.peek else None)
    except MX.MissingSounds as e:
        sys.exit(f"SOUND KIT: {e}")
    print(json.dumps(dict(out=a.out, duration=round(B["D"], 2), punches=B["mo"]["punches"], cuts=[c[0] for c in B["mo"]["cuts"]], captions=len(B["events"]), annotation_cues=AN.cue_times(B["anns"]), sound=B.get("sound_report"),
                          emphasis_found=len(B["emph"])), indent=1))
    if a.lufs is not None and not a.peek:                  # the ceiling is a promise: check the file that was written
        import measure
        tp = measure.loudness(a.out)["true_peak_dB"]
        print(f"true peak {tp} dBTP (ceiling {CEILING_DBTP})", file=sys.stderr)
        if tp > CEILING_DBTP:
            sys.exit(f"TRUE PEAK {tp} dBTP is above the {CEILING_DBTP} dBTP ceiling. The file was written to {a.out}; do not post it.")
