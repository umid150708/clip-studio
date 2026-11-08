"""Sound for Energetic-style shorts: REAL recorded sound effects placed on cues, the original audio kept, silence dips for the fake-out.

The kit (`assets/sfx_kit/`) holds only real recordings that came with a licence and a source URL. Nothing here synthesises a sound:
if a kind the plan needs is missing from the kit, the mix stops and says which one (the user's rule: find and use the real thing).
Clips are never pitch- or speed-shifted; they are placed so their first audible sample lands on the cue time (a riser: so its END
does; a kit entry can say "anchor": "peak" instead, used for whooshes), at a per-kind level, and the loudness master (render.py) does the rest.

plan["sound"] (all optional):
  {"kit": "assets/sfx_kit",
   "auto": {"title": true, "annotations": true, "flashes": true, "end_card": true, "cuts": false, "caption_clicks": false, "annotation_kinds": ["pop", "click"]},   # cues taken from the plan itself
   "cues": [{"t": 2.4, "kind": "impact"}, {"t": 6.0, "kind": "fakeout", "gap": 0.3}],        # extra cues; fakeout = riser, ~0.3 s near-silence, then a hit
   "gain_db": {"impact": -3, "pop": -9},  "duck_db": -3}

Kinds: impact (title card, reveal, colour flash, end line), pop (annotation appears), click (cut / caption accent), whoosh (white flash, window slides in), riser (used by fakeout).
Where each is used comes from the six studied clips (references/playbook.md): impact on cards and reveals, small clicks on caption pops and cuts,
a rising sweep then 0.3 s of near-silence then the hit, whoosh with a flash transition. Sound types there were inferred from spectrograms.
"""
import json
import os
import random
import subprocess
import sys

import numpy as np

SR = 48000
KINDS = ("impact", "pop", "click", "whoosh", "riser")
GAIN_DB = dict(impact=-3.0, pop=-9.0, click=-13.0, whoosh=-6.0, riser=-7.0)   # added to a clip normalised to -3 dBFS peak
ONSET_DB = -30.0
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KIT = os.path.normpath(os.path.join(HERE, "..", "assets", "sfx_kit"))


class MissingSounds(Exception):
    pass


def decode(path, ch=1):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"])
    a = np.frombuffer(raw, np.float32).copy()
    return a.reshape(-1, ch) if ch > 1 else a


def write_wav(path, x):
    """Float WAV through ffmpeg (so a pre-master mix above full scale is kept for the loudness stage)."""
    ch = 1 if x.ndim == 1 else x.shape[1]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", str(ch), "-i", "-", "-c:a", "pcm_f32le", path],
                   input=np.ascontiguousarray(x, np.float32).tobytes(), check=True)


def onset(x, thr_db=ONSET_DB):
    """Index of the first sample within thr_db of the clip's peak."""
    a = np.abs(x); i = np.where(a >= a.max() * 10 ** (thr_db / 20))[0]
    return int(i[0]) if len(i) else 0


def last_active(x, thr_db=ONSET_DB):
    a = np.abs(x); i = np.where(a >= a.max() * 10 ** (thr_db / 20))[0]
    return int(i[-1]) if len(i) else len(x) - 1


# ---------------------------------------------------------------- the kit
class Kit:
    """assets/sfx_kit/kit.json: {"kinds": {"impact": [{"file": "files/x.wav", "license": "CC0", "url": "...", "author": "...", "title": "..."}]}}
    Every entry must carry a licence and a source URL."""
    def __init__(self, root=DEFAULT_KIT):
        self.root, self.clips = root, {}
        path = os.path.join(root, "kit.json")
        if not os.path.exists(path):
            raise MissingSounds(f"no sound kit at {root} (kit.json not found). The kit holds real, licensed recordings only; nothing is synthesised.")
        for kind, entries in json.load(open(path)).get("kinds", {}).items():
            for e in entries:
                for need in ("file", "license", "url"):
                    if not e.get(need):
                        raise ValueError(f"kit entry in '{kind}' lacks '{need}': {e}")
                x = decode(os.path.join(root, e["file"]))
                if len(x) == 0 or not np.abs(x).max():
                    raise ValueError(f"kit file {e['file']} is empty or silent")
                self.clips.setdefault(kind, []).append((e, x / np.abs(x).max() * 10 ** (-3 / 20)))

    def missing(self, kinds):
        return [k for k in kinds if not self.clips.get(k)]

    def pick(self, kind, rng, last):
        pool = self.clips[kind]; k = rng.randrange(len(pool))
        while len(pool) > 1 and k == last.get(kind):
            k = rng.randrange(len(pool))
        last[kind] = k
        return pool[k]


# ---------------------------------------------------------------- cues
def derive_cues(info, auto=None):
    """Cues taken from the render plan itself. info: title {t0}, annotations [{type, t0}], flashes [{t, color}], cuts [t], end_card_t, accents [t]."""
    auto = {"title": True, "annotations": True, "flashes": True, "end_card": True, "cuts": False, "caption_clicks": False, **(auto or {})}
    c = []
    if auto["title"] and info.get("title"):
        c.append(dict(t=float(info["title"].get("t0", 0.0)), kind="impact"))
    if auto["annotations"]:
        kinds, n = auto.get("annotation_kinds") or ["pop"], 0     # e.g. ["pop", "click"] alternates so one sound is not heard over and over
        for a in info.get("annotations", []):
            if a["type"] == "inset":
                c.append(dict(t=a["t0"], kind="whoosh"))
            else:
                c.append(dict(t=a["t0"], kind=kinds[n % len(kinds)])); n += 1
    if auto["flashes"]:
        c += [dict(t=f["t"], kind="whoosh" if f.get("color", "white") == "white" else "impact") for f in info.get("flashes", [])]
    if auto["end_card"] and info.get("end_card_t") is not None:
        c.append(dict(t=float(info["end_card_t"]), kind="impact"))
    if auto["cuts"]:
        c += [dict(t=t, kind="click") for t in info.get("cuts", [])]
    if auto["caption_clicks"]:
        c += [dict(t=t, kind="click") for t in info.get("accents", [])]
    return c


def tidy(cues, min_gap=0.10):
    """Sort and drop a cue of the same kind closer than min_gap to the previous one (a burst of cuts keeps its clicks 0.1 s apart at most)."""
    out, last = [], {}
    for c in sorted(cues, key=lambda c: c["t"]):
        if c["kind"] in last and c["t"] - last[c["kind"]] < min_gap:
            continue
        last[c["kind"]] = c["t"]; out.append(c)
    return out


def expand(cues):
    """fakeout -> riser ending `gap` before the hit, a dip in the original audio for that gap, then the hit."""
    plain, dips = [], []
    for c in cues:
        if c["kind"] == "fakeout":
            gap = float(c.get("gap", 0.3))
            plain.append(dict(t=c["t"] - gap, kind="riser", align="end", gain_db=c.get("riser_db")))
            dips.append((c["t"] - gap, c["t"], float(c.get("dip_db", -40))))
            plain.append(dict(t=c["t"], kind="impact", gain_db=c.get("gain_db")))
        else:
            plain.append(dict(c))
    return plain, dips


# ---------------------------------------------------------------- the track
def build_track(cues, kit, duration, gains=None, seed=7):
    """-> (mono SFX track, placements [{kind, file, t, gain_db}], dips). Raises MissingSounds listing every kind the cues need and the kit lacks."""
    plain, dips = expand(tidy(cues))
    miss = kit.missing(sorted({c["kind"] for c in plain}))
    if miss:
        raise MissingSounds("the kit has no real recording for: " + ", ".join(miss) + f" (kit: {kit.root}). Add licensed files to kit.json; nothing is synthesised.")
    g = {**GAIN_DB, **(gains or {})}
    rng, last = random.Random(seed), {}
    track = np.zeros(int(duration * SR) + SR, np.float32); placed = []
    for c in plain:
        entry, x = kit.pick(c["kind"], rng, last)
        db = c["gain_db"] if c.get("gain_db") is not None else g[c["kind"]]
        db += rng.uniform(-1.0, 0.0)
        anchor = c.get("align") or entry.get("anchor") or ("end" if c["kind"] == "riser" else "onset")
        idx = {"end": last_active, "peak": lambda y: int(np.argmax(np.abs(y))), "onset": onset}[anchor](x)
        start = int(round(c["t"] * SR)) - idx
        y = x * 10 ** (db / 20)
        a, b = max(0, start), min(len(track), start + len(x))
        if b > a:
            track[a:b] += y[a - start: b - start]
        placed.append(dict(kind=c["kind"], file=entry["file"], t=round(c["t"], 3), gain_db=round(db, 1)))
    return track[: int(duration * SR)], placed, dips


def dip_gain(n, dips):
    g = np.ones(n, np.float32); ramp = int(0.01 * SR)
    for t0, t1, db in dips:
        a, b = int(t0 * SR), int(t1 * SR)
        if b <= a:
            continue
        lo = 10 ** (db / 20)
        env = np.full(b - a, lo, np.float32)
        r = min(ramp, (b - a) // 2)
        if r:
            env[:r] = np.linspace(1, lo, r); env[-r:] = np.linspace(lo, 1, r)
        g[a:b] = np.minimum(g[a:b], env[: max(0, min(n, b) - a)])
    return g


def mix(orig, sfx, dips=(), duck_db=-3.0):
    """Original audio (mono or stereo) + SFX. The original dips for the fake-out and ducks a little under loud SFX."""
    n = min(len(orig), len(sfx)); o = orig[:n].astype(np.float32); s = sfx[:n]
    w = int(0.05 * SR)
    env = np.convolve(np.abs(s), np.ones(w, np.float32) / w, mode="same")
    k = 10 ** (duck_db / 20)
    g = (1 - (1 - k) * np.clip(env / 0.05, 0, 1)) * dip_gain(n, dips)
    out = o * (g[:, None] if o.ndim == 2 else g)
    return out + (s[:, None] if o.ndim == 2 else s)


def make_mix(src, start, dur, cfg, info, out_wav):
    """Original clip audio + sound cues -> out_wav (float, pre-master). Returns a report dict."""
    kit = Kit(os.path.abspath(cfg.get("kit", DEFAULT_KIT)))
    cues = derive_cues(info, cfg.get("auto")) + list(cfg.get("cues", []))
    sfx, placed, dips = build_track(cues, kit, dur, cfg.get("gain_db"), cfg.get("seed", 7))
    orig = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", f"{start}", "-t", f"{dur}", "-i", src, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"])
    orig = np.frombuffer(orig, np.float32).reshape(-1, 2)
    n = int(round(dur * SR))
    if len(orig) < n:
        orig = np.vstack([orig, np.zeros((n - len(orig), 2), np.float32)])
    mixed = mix(orig[:n], np.pad(sfx, (0, max(0, n - len(sfx))))[:n], dips, cfg.get("duck_db", -3.0))
    write_wav(out_wav, mixed)
    return dict(kit=kit.root, placements=placed, dips=[(round(a, 2), round(b, 2)) for a, b, _ in dips])


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "report":
        root = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_KIT
        try:
            k = Kit(root)
        except MissingSounds as e:
            sys.exit(str(e))
        for kind in KINDS:
            es = k.clips.get(kind, [])
            print(f"{kind:7} {len(es)} clip(s)" + ("" if es else "   <- MISSING") + "".join(f"\n   {e['file']}  {e['license']}  {e['url']}" for e, _ in es))
    else:
        sys.exit("usage: python3 -I mixer.py report [KIT_DIR]")
