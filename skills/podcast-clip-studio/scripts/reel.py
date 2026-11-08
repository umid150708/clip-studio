#!/usr/bin/env python3
"""reel.py: build a short from a 1080p 16:9 source window. Standing rules (see references/edit-rules.md):
  - the 9:16 camera FOLLOWS the speaker's head (face boxes from facetrack, damped like a camera operator)
  - 5-7 action cutaways of ~3 s, quality footage, captions stay on screen over them
  - the picture changes at least every ~3 s (speaker cuts, cutaways, zoom punches on emphasis)
  - NO sound effects. Audio: original voice, light compression, -16 LUFS.

  python3 -I reel.py --plan plans/clip01.json --out finals/clip01.mp4 [--peek]

plan.json:
  {"source": "segments/01.mp4", "faces": "faces/01.json",
   "words": "subs/ID.en.json3", "words_shift": -10.0,          # YouTube caption time -> source-file time
   "segments": [[17.5, 38.15], [50.7, 82.1]],                   # kept parts, in source-file seconds
   "title": {"lines": ["Guest Reacts to the", "Fight Result"], "t1": 3.2},
   "broll": [{"src": "broll/x.mp4", "at_word": "chin", "occurrence": 1, "lead": 0, "dur": 3.0, "ss": 6.7,
              "cx": 0.5, "cx1": 0.5, "trim_top": 0, "trim_bottom": 0, "z0": 1.0, "z1": 1.08}]}
"""
import argparse, json, math, os, re, subprocess, sys, tempfile
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polish
from polish import frames, audio, duration, emphasis, plan_zooms, zoom_curve, zoom_frame, blend, title_layer, cutaway_filter, find_word

W, H, FPS = 1080, 1920, 30
SW, SH = 1920, 1080
FONT = polish.FONT
YELLOW = (255, 214, 0)
HEADLOCK_MIN_ZOOM = 1.2   # below this the crop is full frame height and could not follow the head vertically


# ---------- words from YouTube auto-captions (word-level) ----------
def load_words(path, shift):
    d = json.load(open(path))
    out = []
    for ev in d.get("events", []):
        base = ev.get("tStartMs", 0)
        for s in ev.get("segs") or []:
            w = s.get("utf8", "").strip()
            if not w or w == "\n":
                continue
            out.append({"w": w, "s": (base + s.get("tOffsetMs", 0)) / 1000 + shift})
    words = []
    for a, b in zip(out, out[1:] + [None]):
        w = a["w"].replace(">>", "").strip()
        if w in ("", "[Music]", "[Applause]", "[Laughter]"):
            continue
        if "[ __ ]" in w:
            w = "***"
        end = min(b["s"], a["s"] + 0.6) if b else a["s"] + 0.5
        words.append({"w": w, "s": a["s"], "e": end})
    return words


def remap_words(words, segs):
    out, off = [], 0.0
    for a, b in segs:
        for w in words:
            if a - 0.03 <= w["s"] < b:
                out.append({"w": w["w"], "s": w["s"] - a + off, "e": min(w["e"], b) - a + off})
        off += b - a
    return out


# ---------- tight jump cuts: remove pauses and filler words ----------
FILLERS = {"um", "uh", "uhh", "umm", "erm", "hmm", "uh,", "um,"}


def silences(src, a, b, noise="-34dB", d=0.30):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", src,
                        "-af", f"silencedetect=noise={noise}:d={d}", "-vn", "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    if len(starts) > len(ends):
        ends.append(b - a)
    return list(zip(starts, ends))


def tighten(src, segs, words, noise="-34dB", lead=0.07, tail=0.10, min_pause=0.30):
    """Cut every pause longer than min_pause down to ~0.17 s and drop filler words (um, uh). Returns new segments."""
    out = []
    for a, b in segs:
        cur = a
        for s, e in silences(src, a, b, noise, min_pause):
            cs, ce = a + s, a + e
            if ce - cs < min_pause:
                continue
            if s < 0.05:                       # leading silence: just start later
                cur = max(cur, ce - lead)
            elif e >= (b - a) - 0.05:          # trailing silence: stop early
                out.append((cur, cs + tail)); cur = None
                break
            else:
                out.append((cur, cs + tail)); cur = ce - lead
        if cur is not None and b - cur > 0.2:
            out.append((cur, b))
    # filler words: cut from the filler's start to just before the next word
    cuts = []
    for w, nw in zip(words, words[1:]):
        if w["w"].lower().strip(".,?!") in FILLERS and 0.08 < nw["s"] - w["s"] < 0.8:
            cuts.append((w["s"] - 0.03, nw["s"] - 0.05))
    fine = []
    for a, b in out:
        pieces = [(a, b)]
        for cs, ce in cuts:
            nxt = []
            for p, q in pieces:
                if cs > p and ce < q:
                    nxt += [(p, cs), (ce, q)]
                else:
                    nxt.append((p, q))
            pieces = nxt
        fine += pieces
    return [(round(p, 3), round(q, 3)) for p, q in fine if q - p > 0.2]


# ---------- cut source ----------
def build_cut(src, segs, out):
    parts, lab = [], []
    for i, (a, b) in enumerate(segs):
        f = 0.03
        parts.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={f},afade=t=out:st={b - a - f}:d={f}[a{i}]")
        lab.append(f"[v{i}][a{i}]")
    fc = ";".join(parts) + ";" + "".join(lab) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-r", str(FPS),
                    "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", out], check=True)


def detect_cuts(path, joins):
    prev, cuts, i = None, [], 0
    for g in frames(path, f"fps={FPS},scale=192:108", 192, 108, pix="gray"):
        g = g.astype(np.int16)
        if prev is not None and np.abs(g - prev).mean() > 12:
            t = i / FPS
            if t > 0.3 and (not cuts or t - cuts[-1] > 0.4):
                cuts.append(t)
        prev = g
        i += 1
    return sorted(set(cuts) | set(j for j in joins if j > 0))


# ---------- head-following camera ----------
def face_track(faces_json, segs, D, cuts=(), hold=1.5, dominance=1.3, confirm=0.45):
    """Per output frame: (cx, cy, fw) of ONE tracked person (normalised source coords).
    Sticky selection (rule: when everyone laughs, stay on one person for at least 1-1.5 s):
      - inside a shot the camera follows the same person (nearest face to where they were a moment ago);
      - it only moves to somebody else after `hold` seconds, and only if that person has been clearly
        bigger/closer (dominance x area) for `confirm` seconds, or if the tracked person is gone;
      - at a real cut in the picture it starts fresh on the biggest face."""
    samples = json.load(open(faces_json))
    ts = np.array([s["t"] for s in samples])
    n = int(D * FPS) + 2
    per_frame = [[] for _ in range(n)]
    off = 0.0
    for a, b in segs:
        for i in range(int((b - a) * FPS)):
            k = min(max(int(np.searchsorted(ts, a + i / FPS)), 0), len(ts) - 1)
            idx = int(off * FPS) + i
            if idx < n:
                per_frame[idx] = samples[k]["faces"]
        off += b - a
    bounds = sorted(set([0] + [int(round(c * FPS)) for c in cuts if 0 < c < D] + [n]))
    out = np.full((n, 3), np.nan)
    stats = {"switches": 0}
    area = lambda f: f["w"] * f["h"]
    ctr = lambda f: (f["x"] + f["w"] / 2, f["y"] + f["h"] / 2)
    for a, b in zip(bounds, bounds[1:]):
        cur, last_switch, chal_since = None, -10 ** 9, None
        for i in range(a, b):
            faces = per_frame[i]
            if not faces:
                if cur is not None:
                    out[i] = (*ctr(cur), cur["w"])
                continue
            if cur is None:
                cur = max(faces, key=area); last_switch = i
                out[i] = (*ctr(cur), cur["w"]); continue
            cx0, cy0 = ctr(cur)
            near = min(faces, key=lambda f: abs(ctr(f)[0] - cx0) + abs(ctr(f)[1] - cy0))
            if abs(ctr(near)[0] - cx0) + abs(ctr(near)[1] - cy0) > 0.16:   # the tracked person left the frame
                cur = max(faces, key=area); last_switch = i; chal_since = None; stats["switches"] += 1
            else:
                cur = near
                big = max(faces, key=area)
                if big is not near and area(big) > dominance * area(near):
                    chal_since = chal_since if chal_since is not None else i
                    if i - chal_since >= confirm * FPS and i - last_switch >= hold * FPS:
                        cur = big; last_switch = i; chal_since = None; stats["switches"] += 1
                else:
                    chal_since = None
            out[i] = (*ctr(cur), cur["w"])
    for c in range(3):
        col = out[:, c]
        good = ~np.isnan(col)
        if good.any():
            out[:, c] = np.interp(np.arange(n), np.where(good)[0], col[good])
    face_track.last_stats = stats
    return out


def face_track_old(faces_json, segs, D):
    """The previous behaviour (largest face on every sample), kept only to measure the difference."""
    samples = json.load(open(faces_json))
    ts = np.array([s["t"] for s in samples])
    raw = []
    for s in samples:
        if s["faces"]:
            f = max(s["faces"], key=lambda f: f["w"] * f["h"])
            raw.append((f["x"] + f["w"] / 2, f["y"] + f["h"] / 2, f["w"]))
        else:
            raw.append((np.nan, np.nan, np.nan))
    raw = np.array(raw)
    n = int(D * FPS) + 2
    out = np.full((n, 3), np.nan)
    off = 0.0
    for a, b in segs:
        for i in range(int((b - a) * FPS)):
            k = min(max(int(np.searchsorted(ts, a + i / FPS)), 0), len(ts) - 1)
            idx = int(off * FPS) + i
            if idx < n:
                out[idx] = raw[k]
        off += b - a
    for c in range(3):
        col = out[:, c]
        good = ~np.isnan(col)
        if good.any():
            out[:, c] = np.interp(np.arange(n), np.where(good)[0], col[good])
    return out


def camera_path(track, cuts, D):
    """Damped follow inside each shot, hard jump at cuts. Returns per-frame (cx, cy, base_zoom)."""
    n = len(track)
    bounds = [0] + [int(round(c * FPS)) for c in cuts if 0 < c < D] + [n]
    bounds = sorted(set(bounds))
    cam = np.zeros((n, 3))
    # HEAD-TRACKING EFFECT: the head stays locked in the centre of the frame while the background slides around it.
    # So: no deadband and almost no lag (tau 0.05 s only removes detector jitter), and enough zoom (>=1.2) that the
    # crop can also move vertically instead of being stuck at full frame height.
    tau, dt = 0.05, 1.0 / FPS
    alpha = 1 - math.exp(-dt / tau)
    for a, b in zip(bounds, bounds[1:]):
        seg = track[a:b].copy()
        if len(seg) == 0:
            continue
        k = 5  # median filter against detection jitter
        pad = np.pad(seg, ((k // 2, k // 2), (0, 0)), mode="edge")
        med = np.array([np.median(pad[i:i + k], axis=0) for i in range(len(seg))])
        fw = float(np.median(med[:, 2]))
        zbase = min(max(0.13 / max(fw, 1e-3), HEADLOCK_MIN_ZOOM), 2.0)  # wide shots get punched in so the speaker is a sensible size
        x, y = med[0, 0], med[0, 1]
        for i in range(len(seg)):
            x += (med[i, 0] - x) * alpha
            y += (med[i, 1] - y) * alpha
            cam[a + i] = (x, y, zbase)
    return cam


def crop_frame(src, cx, cy, zoom):
    hc = SH / zoom
    wc = hc * 9 / 16
    x0 = min(max(cx * SW - wc / 2, 0), SW - wc)          # head dead centre horizontally
    y0 = min(max(cy * SH - 0.47 * hc, 0), SH - hc)       # and held at the same height, 47% from the top (headroom)
    s = W / wc
    M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
    return cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_CUBIC)


# ---------- captions ----------
_font = ImageFont.truetype(FONT, 80, index=8)
_cache = {}


def caption_img(words, cur):
    key = (tuple(w.upper() for w in words), cur)
    if key in _cache:
        return _cache[key]
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    ws = [w.upper() for w in words]
    sp = probe.textlength(" ", font=_font)
    widths = [probe.textlength(w, font=_font) for w in ws]
    total = int(sum(widths) + sp * (len(ws) - 1)) + 40
    im = Image.new("RGBA", (total, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 20
    for i, w in enumerate(ws):
        d.text((x, 20), w, font=_font, fill=(YELLOW if i == cur else (255, 255, 255)) + (255,), stroke_width=7, stroke_fill=(0, 0, 0, 255))
        x += widths[i] + sp
    if im.width > 1000:  # long chunk: scale it down to stay inside the frame
        k = 1000 / im.width
        im = im.resize((1000, max(1, int(im.height * k))), Image.LANCZOS)
    _cache[key] = np.asarray(im)
    return _cache[key]


def chunk_words(words, per=3):
    chunks, i = [], 0
    while i < len(words):
        grp = words[i:i + per]
        # break early on long pauses
        for j in range(1, len(grp)):
            if grp[j]["s"] - grp[j - 1]["e"] > 0.45:
                grp = grp[:j]
                break
        chunks.append(grp)
        i += len(grp)
    return chunks


def tracked_cutaway(b, out, dur):
    """Cutaway whose 9:16 crop follows a bright-orange subject (the Dutch skating suit), so she never leaves the frame."""
    tt, tb = b.get("trim_top", 0), b.get("trim_bottom", 0)
    y0 = int(SH * tt); hc = int(SH * (1 - tt - tb)); wc = int(hc * 9 / 16)
    cxs, prev = [], 0.5
    frs = []
    for fr in frames(b["src"], f"fps={FPS}", SW, SH, ss=b.get("ss"), t=dur):
        small = cv2.resize(fr[y0:y0 + hc], (480, int(480 * hc / SW)))
        hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, (5, 150, 150), (22, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            c = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(c) > 120:
                m = cv2.moments(c); prev = m["m10"] / m["m00"] / 480
        cxs.append(prev); frs.append(fr)
    cxs = np.array(cxs)
    pad = np.pad(cxs, 4, mode="edge")
    cxs = np.array([np.median(pad[i:i + 9]) for i in range(len(cxs))])
    x = cxs[0]
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-an", "-c:v", "libx264", "-crf", "18", "-bf", "0", "-g", "30", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fr, tx in zip(frs, cxs):
        x += (tx - x) * 0.35
        x0 = min(max(x * SW - wc / 2, 0), SW - wc)
        s = W / wc
        M = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
        enc.stdin.write(cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC).tobytes())
    enc.stdin.close(); enc.wait()


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--peek", action="store_true", help="only write a contact sheet of the cutaway crops (OUT.png)")
    ap.add_argument("--plain", action="store_true",
                    help="render ONLY the head-tracked picture (no captions, title or cutaways, no audio) plus OUT.narration.m4a and OUT.json; "
                         "Crayo then adds captions, title and cutaways")
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    segs = [tuple(s) for s in plan["segments"]]
    tag = os.path.splitext(os.path.basename(a.out))[0]
    raw_words = load_words(plan["words"], plan.get("words_shift", 0.0))
    if plan.get("tighten", True):
        segs = tighten(plan["source"], segs, raw_words, plan.get("silence_db", "-34dB"))
    cut = f"edits/{tag}_cut.mp4"
    build_cut(plan["source"], segs, cut)
    D = duration(cut)
    words = remap_words(raw_words, segs)
    joins = list(np.cumsum([b - a_ for a_, b in segs])[:-1])
    cuts = detect_cuts(cut, joins)

    inserts = []
    for b in plan.get("broll", []):
        t0 = (b["at"] if "at" in b else find_word(words, b["at_word"], b.get("occurrence", 1))) + b.get("lead", 0.0)
        t0 = max(t0, 2.1)  # campaign rule: the hook owns the first 2 seconds, no cutaway over it
        inserts.append(dict(b, t0=t0, t1=min(t0 + b["dur"], D)))
    inserts.sort(key=lambda b: b["t0"])
    for k in range(len(inserts) - 1):  # a cutaway never runs into the next one, and never leaves a sliver of speaker between two
        prev, nxt = inserts[k], inserts[k + 1]
        prev["t1"] = min(prev["t1"], nxt["t0"])
        if 0 < nxt["t0"] - prev["t1"] < 1.0:
            nxt["t0"] = prev["t1"]
            nxt["t1"] = min(nxt["t0"] + nxt["dur"], D)
    inserts = [b for b in inserts if b["t1"] - b["t0"] >= 1.0]
    windows = [(b["t0"], b["t1"]) for b in inserts]

    if a.peek:
        rows = []
        for b in inserts:
            fr = list(frames(b["src"], cutaway_filter(b), W, H, ss=b.get("ss"), t=b["dur"]))
            idx = [min(int(k * (len(fr) - 1) / 5), len(fr) - 1) for k in range(6)]
            rows.append(np.concatenate([cv2.resize(fr[i], (180, 320)) for i in idx], axis=1))
        cv2.imwrite(a.out, cv2.cvtColor(np.concatenate(rows, axis=0), cv2.COLOR_RGB2BGR))
        print("peek ->", a.out, [f"{b['t0']:.1f}s {os.path.basename(b['src'])}" for b in inserts])
        return

    emph = emphasis(cut, words)
    depth = plan.get("zoom_depth", 0.10)
    zoom = plan_zooms(D, cuts, windows, emph, words, 0.0, depth, plan.get("max_gap", 3.0))
    zc, zevents = zoom_curve(D, cuts, zoom, depth)
    cam = camera_path(face_track(plan["faces"], segs, D, cuts), cuts, D)
    # jump cuts inside one shot alternate a slight punch-in so they read as intentional edits
    jn = np.array(joins) if len(joins) else np.array([])
    jump_mult = np.array([1.0 + 0.07 * (int((jn <= i / FPS).sum()) % 2) for i in range(len(cam))])

    edges = sorted({0.0, D, *cuts, *[w for win in windows for w in win], *[t for t, _ in zoom]})
    gaps = np.diff(edges)
    print(f"{tag}: {D:.1f}s | shot cuts {len(cuts)} | zoom punches {len(zoom)} | cutaways {len(inserts)} "
          f"({sum(b['dur'] for b in inserts):.1f}s) | longest gap between visible changes {gaps.max():.2f}s")
    if gaps.max() > 3.5:
        print("WARNING gap > 3.5s around", [round(e, 1) for e, g in zip(edges, gaps) if g > 3.5])

    chunks = chunk_words(words)
    title = plan.get("title")
    tlayer = title_layer(title["lines"]) if title else None
    if not a.plain:
        for b in inserts:
            b["it"] = frames(b["src"], cutaway_filter(b), W, H, ss=b.get("ss"), t=b["dur"] + 0.3)
            b["last"] = None

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    AF = "acompressor=threshold=0.12:ratio=3:attack=5:release=90:makeup=1,loudnorm=I=-16:TP=-1.5:LRA=9"
    if a.plain:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", cut, "-vn", "-af", AF, "-c:a", "libmp3lame", "-b:a", "192k", a.out + ".narration.mp3"], check=True)
        enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
        inserts_active = []
    else:
        enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-i", cut, "-map", "0:v", "-map", "1:a", "-af", AF,
                                "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                                "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
        inserts_active = inserts
    ci = 0
    for i, fr in enumerate(frames(cut, f"fps={FPS}", SW, SH)):
        t = i / FPS
        ins = next((b for b in inserts_active if b["t0"] <= t < b["t1"]), None)
        if a.plain:
            cx, cy, zb = cam[min(i, len(cam) - 1)]
            enc.stdin.write(np.ascontiguousarray(crop_frame(fr, cx, cy, zb * zc[min(i, len(zc) - 1)] * jump_mult[min(i, len(jump_mult) - 1)])).tobytes())
            continue
        if ins:
            nf = next(ins["it"], None)
            if nf is not None:
                ins["last"] = nf
            base = ins["last"] if ins["last"] is not None else crop_frame(fr, *cam[min(i, len(cam) - 1)][:2], cam[min(i, len(cam) - 1)][2])
            p = (t - ins["t0"]) / ins["dur"]
            out = zoom_frame(base, ins.get("z0", 1.0) + (ins.get("z1", 1.08) - ins.get("z0", 1.0)) * p, ins.get("cy", 0.5)).copy()
        else:
            cx, cy, zb = cam[min(i, len(cam) - 1)]
            zp = zc[min(i, len(zc) - 1)]
            out = crop_frame(fr, cx, cy, zb * zp * jump_mult[min(i, len(jump_mult) - 1)])
            if tlayer is not None and t < title["t1"]:
                blend(out, tlayer, W / 2, 175)
        # captions (always on top, also over cutaways)
        while ci < len(chunks) and chunks[ci][-1]["e"] + 0.15 < t:
            ci += 1
        if ci < len(chunks) and chunks[ci][0]["s"] - 0.05 <= t:
            grp = chunks[ci]
            cur = max([k for k, w in enumerate(grp) if w["s"] <= t + 0.02] or [0])
            blend(out, caption_img([w["w"] for w in grp], cur), W / 2, H * 0.655)
        enc.stdin.write(np.ascontiguousarray(out).tobytes())
    enc.stdin.close(); enc.wait()
    files = []
    if a.plain:  # each cutaway as its own 9:16 clip, exactly as long as its slot, for Crayo to place on the timeline
        os.makedirs("cutaways", exist_ok=True)
        for k, b in enumerate(inserts, 1):
            p = f"cutaways/{tag}_{k}.mp4"
            if b.get("track") == "orange":
                tracked_cutaway(b, p, b["t1"] - b["t0"] + 0.4)
            else:
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(b.get("ss", 0)), "-t", f"{b['t1'] - b['t0'] + 0.4:.3f}", "-i", b["src"],
                                "-vf", cutaway_filter(b), "-an", "-c:v", "libx264", "-crf", "18", "-bf", "0", "-g", "30", "-pix_fmt", "yuv420p", p], check=True)
            files.append(p)
    json.dump({"duration": D, "cuts": cuts, "zoom": zoom, "title": plan.get("title"),
               "cutaways": [[b["t0"], b["t1"], os.path.basename(b["src"])] for b in inserts], "cutaway_files": files,
               "max_gap": float(gaps.max())}, open(a.out + ".json", "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
