#!/usr/bin/env python3
"""Polish a Crayo base short. Standing rules for every clip (see references/edit-rules.md):
  1. 1-3 B-roll cutaways (2-4 s) of what is being discussed, captions kept on screen over them.
  2. The picture never sits still for more than 3.5 s: punch-in / zoom-out on the speaker's emphasis
     (found from the audio), speaker cuts and B-roll all count as changes. Each zoom has a quiet SFX.

  python3 -I polish.py --base bases/01.mp4 --words bases/01.words.json --plan plans/01.json --out finals/01.mp4

plan.json:
  {"broll": [{"src": "broll/aj_ko.mp4", "at_word": "chin", "occurrence": 1, "lead": 0.0, "dur": 2.6,
              "ss": 0.0, "cx": 0.5, "z0": 1.04, "z1": 1.16, "sfx": "whoosh", "impact_at": 1.4}],
   "zoom_depth": 0.10, "max_gap": 3.1}
  "at" (seconds in the base) can be used instead of at_word.  cx = horizontal centre of the 9:16 crop in the source.
"""
import argparse, json, math, os, subprocess, sys, tempfile, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
SFX_DIR = os.path.join(HERE, "sfx")
FONT = "/System/Library/Fonts/Avenir Next.ttc"  # index 8 = Heavy
SR = 44100


# ---------- media helpers ----------
def run(cmd):
    subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]))


def frames(path, vf, w, h, pix="rgb24", ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(ss)] if ss else []) + (["-t", str(t)] if t else [])
    cmd += ["-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = w * h * (3 if pix == "rgb24" else 1)
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape((h, w, 3) if pix == "rgb24" else (h, w))
    finally:  # a cutaway decoder is usually abandoned early: stop it quietly
        p.kill(); p.stdout.close(); p.wait()


def audio(path, sr, ch):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"])
    a = np.frombuffer(raw, np.float32)
    return a.reshape(-1, ch) if ch > 1 else a


# ---------- sound effects (synthesised with ffmpeg, cached in sfx/) ----------
SFX_CMDS = {
    "pop": ["-f", "lavfi", "-i", "sine=f=1300:d=0.07", "-f", "lavfi", "-i", "sine=f=150:d=0.12", "-filter_complex",
            "[0]afade=t=out:st=0:d=0.07[a];[1]afade=t=out:st=0:d=0.12[b];[a][b]amix=inputs=2:normalize=0"],
    "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.9", "-af",
               "highpass=f=250,lowpass=f=7000,afade=t=in:st=0:d=0.28,afade=t=out:st=0.28:d=0.22"],
    "swish": ["-f", "lavfi", "-i", "anoisesrc=d=0.3:c=pink:a=0.8", "-af",
              "highpass=f=600,lowpass=f=5000,afade=t=in:st=0:d=0.05,afade=t=out:st=0.05:d=0.25"],
    "impact": ["-f", "lavfi", "-i", "sine=f=58:d=0.6", "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=brown:a=0.9", "-filter_complex",
               "[0]afade=t=out:st=0.02:d=0.58[a];[1]lowpass=f=600,afade=t=out:st=0:d=0.45[b];[a][b]amix=inputs=2:normalize=0,volume=1.5"],
}


def sfx(name):
    os.makedirs(SFX_DIR, exist_ok=True)
    p = os.path.join(SFX_DIR, f"{name}.wav")
    if not os.path.exists(p):
        run(["ffmpeg", "-y", "-v", "error"] + SFX_CMDS[name] + ["-ar", str(SR), "-ac", "1", p])
    return audio(p, SR, 1)


# ---------- analysis ----------
def detect_cuts_and_title(base):
    """Shot cuts (frame-diff on a tiny grey copy) and when the title box in the top-left disappears."""
    prev, cuts, title_end, i = None, [], 0.0, 0
    for g in frames(base, f"fps={FPS},scale=108:192", 108, 192, pix="gray"):
        if prev is not None and np.abs(g.astype(np.int16) - prev).mean() > 14:
            t = i / FPS
            if t > 0.6 and (not cuts or t - cuts[-1] > 0.5):  # ignore the opening settle and duplicate detections
                cuts.append(t)
        prev = g.astype(np.int16)
        if (g[4:30, 0:55] > 235).mean() > 0.3:  # white title box present
            title_end = i / FPS
        i += 1
    return cuts, title_end + 0.25


def emphasis(base, words):
    """Times where the speaker leans on a word: loud onsets relative to the surrounding speech."""
    a = audio(base, 16000, 1)
    hop = 160
    n = len(a) // hop
    rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-6
    db = 20 * np.log10(rms)
    k = np.ones(8) / 8
    sm = np.convolve(db, k, mode="same")
    med = np.array([np.median(sm[max(0, i - 150): i + 150]) for i in range(n)])
    score = sm - med
    out = []
    for i in range(20, n - 20):
        if score[i] > 4.0 and score[i] == score[i - 20: i + 20].max():
            t = i * hop / 16000 - 0.12
            if words:  # snap to the nearest word start
                ws = min(words, key=lambda w: abs(w["s"] - t))
                if abs(ws["s"] - t) < 0.3:
                    t = ws["s"]
            out.append((max(t, 0.0), float(score[i])))
    return out


# ---------- planning ----------
def find_word(words, token, occurrence=1):
    hits = [w for w in words if w["w"].lower().strip(".,?!\"'") == token.lower()]
    if len(hits) < occurrence:
        sys.exit(f"word {token!r} (occurrence {occurrence}) not found in transcript")
    return hits[occurrence - 1]["s"]


def plan_zooms(D, cuts, windows, emph, words, title_end, depth, max_gap):
    """Zoom events so that no two visible changes are more than max_gap apart."""
    natural = sorted(set([c for c in cuts] + [w[0] for w in windows] + [w[1] for w in windows]))
    zoom, last = [], 0.0
    def blocked(t):
        return any(a - 0.25 <= t <= b + 0.1 for a, b in windows)
    while last < D - 0.5:
        nxt = min([c for c in natural if c > last + 0.05] + [D])
        if nxt - last <= max_gap:
            last = nxt
            continue
        lo, hi = max(last + 1.3, title_end), last + max_gap - 0.1
        cands = [(t, s) for t, s in emph if lo <= t <= hi and not blocked(t)]
        if cands:
            t, s = max(cands, key=lambda c: c[1])
        else:
            t, s = min(hi, max(lo, last + 2.4)), 5.0
            if words:
                ws = min(words, key=lambda w: abs(w["s"] - t))
                if lo <= ws["s"] <= hi:
                    t = ws["s"]
            if blocked(t):
                t = last + 1.4
        zoom.append((round(t, 3), s))
        last = t
    return zoom


def zoom_curve(D, cuts, zoom, depth):
    n = int(D * FPS) + 2
    z = np.ones(n)
    cur, target, kind = 1.0, 1.0, "out"
    ev = {int(round(t * FPS)): s for t, s in zoom}
    cutf = {int(round(c * FPS)) for c in cuts}
    since = 0
    events = []
    for i in range(n):
        if i in cutf:
            cur, target, kind, since = 1.0, 1.0, "out", 0
        if i in ev:
            if kind == "out":
                d = depth + 0.05 * min(max((ev[i] - 4) / 8, 0), 1)
                target, kind = 1.0 + d, "in"
            else:
                target, kind = 1.0, "out"
            since = 0
            events.append((i / FPS, kind))
        drift = 0.012 * min(since / FPS, 3.0)  # a slow push so the frame is never frozen
        tgt = target + (drift if kind == "in" else 0.0)
        rate = 1 - math.exp(-(14 if kind == "in" else 7) / FPS)
        cur += (tgt - cur) * rate
        z[i] = cur
        since += 1
    return z, events


# ---------- drawing ----------
def chunks(words, per=2):
    out, i = [], 0
    while i < len(words):
        grp = words[i: i + per]
        out.append((grp[0]["s"], " ".join(w["w"] for w in grp), grp[-1]["e"]))
        i += per
    res = []
    for k, (s, txt, e) in enumerate(out):
        end = out[k + 1][0] if k + 1 < len(out) else e + 0.15
        res.append((s, end, txt))
    return res


_text_cache = {}


def caption_layer(text, colour):
    key = (text, colour)
    if key not in _text_cache:
        font = ImageFont.truetype(FONT, 84, index=8)
        probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        box = probe.textbbox((0, 0), text, font=font, stroke_width=5)
        im = Image.new("RGBA", (box[2] - box[0] + 24, box[3] - box[1] + 24), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((12 - box[0], 12 - box[1]), text, font=font, fill=colour + (255,), stroke_width=5, stroke_fill=(0, 0, 0, 255))
        _text_cache[key] = np.asarray(im)
    return _text_cache[key]


def title_layer(lines):
    """White rounded box with bold black text, like Crayo's own title card (used when a cut drops Crayo's)."""
    font = ImageFont.truetype(FONT, 66, index=8)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    widths = [probe.textlength(l, font=font) for l in lines]
    lh = 84
    w, h = int(max(widths)) + 70, lh * len(lines) + 36
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=26, fill=(255, 255, 255, 255))
    for i, l in enumerate(lines):
        d.text(((w - widths[i]) / 2, 14 + i * lh), l, font=font, fill=(0, 0, 0, 255))
    return np.asarray(im)


def blend(frame, layer, cx, cy):
    h, w = layer.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    x0, y0 = max(0, min(W - w, x0)), max(0, min(H - h, y0))
    a = layer[:, :, 3:4].astype(np.float32) / 255
    region = frame[y0: y0 + h, x0: x0 + w].astype(np.float32)
    frame[y0: y0 + h, x0: x0 + w] = (region * (1 - a) + layer[:, :, :3] * a).astype(np.uint8)


def zoom_frame(f, z, cy=0.42):
    if z <= 1.002:
        return f
    cw, ch = W / z, H / z
    x0 = (W - cw) / 2
    y0 = min(max(H * cy - ch / 2, 0), H - ch)
    M = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
    return cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR)


def caption_colour(base, t):
    for fr in frames(base, f"fps={FPS},crop={W}:{int(H * .3)}:0:{int(H * .42)}", W, int(H * .3), ss=max(t - 0.12, 0), t=0.1):
        r, g, b = fr[..., 0].astype(int), fr[..., 1].astype(int), fr[..., 2].astype(int)
        yellow = ((r > 215) & (g > 150) & (g < 215) & (b < 80)).sum()
        return (255, 184, 0) if yellow > 250 else (255, 255, 255)
    return (255, 255, 255)


def cutaway_filter(b):
    """ffmpeg filter that turns the B-roll source into a 1080x1920 cutaway.
    layout "crop" (default): tight 9:16 crop, panning from cx to cx1 (0 = left edge of the source, 1 = right edge).
    layout "blur": the whole 16:9 frame in a band over a blurred copy (keeps wide two-fighter shots in view).
    trim_bottom: fraction to cut off the bottom first (baked-in caption strips on old footage)."""
    tb, tt = b.get("trim_bottom", 0), b.get("trim_top", 0)
    pre = f"crop=iw:ih*{1 - tb - tt}:0:ih*{tt}," if (tb or tt) else ""
    if b.get("layout") == "blur":
        return (f"fps={FPS},{pre}split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=40:6,eq=brightness=-0.08[bg];[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    c0, c1 = b.get("cx", .5), b.get("cx1", b.get("cx", .5))
    return f"fps={FPS},{pre}crop=w=ih*9/16:h=ih:x='(iw-ow)*({c0}+({c1}-{c0})*min(t/{b['dur']},1))':y=0,scale={W}:{H}"


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True); ap.add_argument("--words", required=True)
    ap.add_argument("--plan", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--peek", action="store_true", help="only render a contact sheet of each cutaway crop (OUT.png), no full render")
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    words = json.load(open(a.words))["words"]
    D = duration(a.base)
    depth, max_gap = plan.get("zoom_depth", 0.10), plan.get("max_gap", 3.1)

    cuts, title_end = detect_cuts_and_title(a.base)
    emph = emphasis(a.base, words)
    inserts = []
    for b in plan.get("broll", []):
        t0 = (b["at"] if "at" in b else find_word(words, b["at_word"], b.get("occurrence", 1))) + b.get("lead", 0.0)
        inserts.append(dict(b, t0=t0, t1=t0 + b["dur"]))
    windows = [(b["t0"], b["t1"]) for b in inserts]
    zoom = plan_zooms(D, cuts, windows, emph, words, title_end, depth, max_gap)
    z, zevents = zoom_curve(D, cuts, zoom, depth)

    edges = sorted({0.0, D, *cuts, *[w for win in windows for w in win], *[t for t, _ in zoom]})
    gaps = np.diff(edges)
    print(f"duration {D:.1f}s | cuts {len(cuts)} | emphasis peaks {len(emph)} | zoom events {len(zoom)} | B-roll {len(inserts)}")
    print(f"max time between visible changes: {gaps.max():.2f}s (limit 3.5)")
    if gaps.max() > 3.5:
        print("WARNING: gap over 3.5s", [round(e, 1) for e, g in zip(edges, gaps) if g > 3.5])

    if a.peek:  # preview of each cutaway as it will be cropped: 6 frames per insert
        rows = []
        for b in inserts:
            vf = cutaway_filter(b)
            fr = list(frames(b["src"], vf, W, H, ss=b.get("ss"), t=b["dur"]))
            idx = [min(int(k * (len(fr) - 1) / 5), len(fr) - 1) for k in range(6)]
            rows.append(np.concatenate([cv2.resize(fr[i], (180, 320)) for i in idx], axis=1))
        cv2.imwrite(a.out, cv2.cvtColor(np.concatenate(rows, axis=0), cv2.COLOR_RGB2BGR))
        print("peek ->", a.out, [f"{b['t0']:.1f}s {os.path.basename(b['src'])}" for b in inserts])
        return

    # --- audio: base + SFX
    mix = audio(a.base, SR, 2).copy()
    speech = mix[np.abs(mix).max(1) > 0.02]
    voice = float(np.sqrt((speech ** 2).mean())) if len(speech) else 0.1
    def put(name, t, level):
        s = sfx(name); s = s / (np.sqrt((s ** 2).mean()) + 1e-9) * voice * level
        i = int(max(t, 0) * SR)
        seg = s[: max(0, len(mix) - i)]
        mix[i: i + len(seg)] += seg[:, None]
    for t, kind in zevents:
        put("pop", t - 0.02, 0.38) if kind == "in" else put("swish", t, 0.2)
        if kind == "in":
            put("whoosh", t - 0.18, 0.2)
    for b in inserts:
        put(b.get("sfx", "whoosh"), b["t0"] - 0.2, 0.3)
        if "impact_at" in b:
            put("impact", b["t0"] + b["impact_at"], 0.65)
        put("swish", b["t1"] - 0.05, 0.2)
    mix = np.tanh(mix)  # soft limiter with unity gain for normal speech levels (peaks compress slightly)
    tmpdir = tempfile.mkdtemp()
    wav = os.path.join(tmpdir, "mix.wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())

    # --- video
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    cap = chunks(words)
    title = plan.get("title")
    tlayer = title_layer(title["lines"]) if title else None
    for b in inserts:
        b["colour"] = caption_colour(a.base, b["t0"])
        b["it"] = frames(b["src"], cutaway_filter(b), W, H, ss=b.get("ss"), t=b["dur"] + 0.2)
        b["last"] = None
    for i, fr in enumerate(frames(a.base, f"fps={FPS}", W, H)):
        t = i / FPS
        ins = next((b for b in inserts if b["t0"] <= t < b["t1"]), None)
        if ins:
            nf = next(ins["it"], None)
            if nf is not None:
                ins["last"] = nf
            src = ins["last"] if ins["last"] is not None else fr
            p = (t - ins["t0"]) / ins["dur"]
            out = zoom_frame(src, ins.get("z0", 1.04) + (ins.get("z1", 1.16) - ins.get("z0", 1.04)) * p, ins.get("cy", 0.5)).copy()
            for s, e, txt in cap:
                if s <= t < e:
                    blend(out, caption_layer(txt, ins["colour"]), W / 2, H * 0.60)
                    break
        else:
            out = zoom_frame(fr, z[min(i, len(z) - 1)])
            if tlayer is not None and t < title["t1"]:
                out = out.copy()
                blend(out, tlayer, W / 2, 175)
        enc.stdin.write(np.ascontiguousarray(out).tobytes())
    enc.stdin.close(); enc.wait()
    json.dump({"duration": D, "cuts": cuts, "zoom_events": zevents, "broll": [[b["t0"], b["t1"]] for b in inserts],
               "max_gap": float(gaps.max())}, open(a.out + ".plan.json", "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
