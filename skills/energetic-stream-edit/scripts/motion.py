"""Motion layer for viral-style Shorts: slow push-in, punch-ins on emphasis, burst cuts, colour / white flashes.

Everything here is a pure function over time (no video I/O), so it can be tested and measured:
  camera_zoom(...)   -> zoom factor per output frame (1.0 = whole 9:16 window, 1.5 = 1.5x closer)
  auto_punches(...)  -> where to put punch-ins (speaker emphasis first, then filler so no stretch runs longer than ~gap)
  expand_cuts(...)   -> framing cuts (+ burst cuts) as (time, starting zoom)
  shake(...)         -> small decaying wobble after each punch (off by default)
  flash_alpha / apply_flashes -> colour flash and white-flash transitions
Numbers come from the six studied clips (study/VIRAL_EDIT_PLAYBOOK.md, re-measured 8 Nov with measure.py): jumps of 4-18% in and out every
~1-2 s, little or no steady drift (about 0-2 %/s), 2-3 hard cuts per 10 s (11 in the multi-camera meme edit).
"""
import numpy as np

COLORS = {"white": (255, 255, 255), "green": (61, 255, 106), "yellow": (255, 230, 0), "cyan": (0, 229, 255),
          "pink": (255, 92, 170), "red": (255, 59, 48), "orange": (255, 159, 28), "black": (0, 0, 0)}
BURST_ZOOMS = [1.0, 1.42, 1.12, 1.55]


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def expand_cuts(cuts=(), bursts=(), cut_alt=1.22):
    """cuts: floats (time) or {'t':..,'zoom':..}; bursts: {'t','n','span'} = n quick cuts inside `span` seconds.
    Plain cuts alternate between a close framing (cut_alt) and the wide one (1.0), like wide / close-up / wide in the multi-camera edit.
    Returns [(time, starting zoom)] sorted by time."""
    out, close = [], True
    for c in cuts or []:
        t = c["t"] if isinstance(c, dict) else c
        z = c.get("zoom") if isinstance(c, dict) else None
        if z is None:
            z, close = (cut_alt if close else 1.0), not close
        out.append((float(t), float(z)))
    for b in bursts or []:
        n = max(2, int(b.get("n", 4))); span = float(b.get("span", 0.5))
        for i in range(n):
            z = BURST_ZOOMS[i % len(BURST_ZOOMS)] if i < n - 1 else 1.1
            out.append((float(b["t"]) + span * i / n, z))
    return sorted(out)


def camera_zoom(n, fps, cuts=(), punches=(), rate=0.01, max_zoom=1.6, punch_gain=0.10, ease=0.033, mode="pulse"):
    """Zoom per frame. Inside each shot: a gentle push-in of `rate` per second from the shot's starting zoom, plus punches.
    mode "pulse" (default, what the studied clips do): punches alternate IN (+punch_gain) and OUT (back to the drifting base), so the
    picture keeps jumping without running away. mode "ratchet": every punch goes further in (capped by max_zoom).
    A punch is a hard jump over `ease` seconds (default one frame at 30 fps). A cut resets the shot."""
    t = np.arange(n) / fps
    starts = [(0.0, 1.0)] + sorted(cuts)
    z = np.ones(n)
    for k, (t0, z0) in enumerate(starts):
        t1 = starts[k + 1][0] if k + 1 < len(starts) else np.inf
        m = (t >= t0) & (t < t1)
        if not m.any():
            continue
        zz = z0 * (1 + rate * (t[m] - t0))
        lvl = np.zeros(int(m.sum()))
        for j, p in enumerate(sorted(q for q in punches if t0 <= q < t1)):
            up = mode == "ratchet" or j % 2 == 0
            lvl += (1.0 if up else -1.0) * smoothstep((t[m] - p) / ease)
        z[m] = zz * (1 + punch_gain) ** lvl
    return np.minimum(z, max_zoom)


def auto_punches(emph, duration, cuts=(), words=None, gap=2.0, min_gap=1.5, first=1.0, tail=0.5, snap=0.3):
    """Punch times: the loudest speaker emphasis points first (never closer than min_gap), then fill any stretch longer
    than 1.45*gap with extra punches (snapped to a word start) so the picture keeps changing about every `gap` seconds."""
    cut_t = [c[0] if isinstance(c, (tuple, list)) else c for c in cuts]
    near_cut = lambda t: any(abs(t - c) < 0.3 for c in cut_t)
    picked = []
    for t, s in sorted([e for e in emph if first <= e[0] <= duration - tail], key=lambda e: -e[1]):
        if not near_cut(t) and all(abs(t - p) >= min_gap for p in picked):
            picked.append(t)
    picked.sort()
    limit = gap * 1.45
    for _ in range(100):
        marks = sorted([0.0] + picked + [duration] + cut_t)
        gaps = [(b - a, a, b) for a, b in zip(marks, marks[1:])]
        width, a, b = max(gaps)
        if width <= limit:
            break
        t = a + max(gap, width / 2) if width > 2 * gap else a + width / 2
        if words:
            w = min(words, key=lambda x: abs(x["s"] - t))
            if abs(w["s"] - t) <= snap and a + 0.8 < w["s"] < b - 0.8:
                t = w["s"]
        if t < first or near_cut(t) or t > duration - tail:
            break
        picked.append(t); picked.sort()
    return [round(p, 3) for p in picked]


def shake(n, fps, punches, amp=0.0, tau=0.12, freq=14.0):
    """Decaying wobble after each punch, as a fraction of the crop window. amp=0 turns it off."""
    dx, dy = np.zeros(n), np.zeros(n)
    if amp <= 0:
        return dx, dy
    t = np.arange(n) / fps
    for p in punches:
        m = t >= p; tt = t[m] - p; env = np.exp(-tt / tau)
        dx[m] += amp * env * np.sin(2 * np.pi * freq * tt)
        dy[m] += 0.6 * amp * env * np.cos(2 * np.pi * freq * 1.3 * tt)
    return dx, dy


def flash_alpha(t, flashes):
    """[(colour rgb, alpha)] active at time t. A flash hits at full strength on its time and decays linearly over `dur`."""
    out = []
    for f in flashes or []:
        d = float(f.get("dur", 0.35))
        if f["t"] <= t < f["t"] + d:
            col = f.get("color", "white")
            out.append((COLORS[col] if isinstance(col, str) else tuple(col), float(f.get("peak", 0.45)) * (1 - (t - f["t"]) / d)))
    return out


def apply_flashes(frame, t, flashes):
    """Tint the frame in place (uint8 RGB)."""
    for col, a in flash_alpha(t, flashes):
        frame[:] = (frame.astype(np.float32) * (1 - a) + np.array(col, np.float32) * a).astype(np.uint8)


def warm_grade(frame, amount=0.0):
    """Warm yellow-orange grade (amount 0..1) like the 'kindest streamer' clip."""
    if amount <= 0:
        return
    f = frame.astype(np.float32)
    f[..., 0] *= 1 + 0.10 * amount; f[..., 1] *= 1 + 0.03 * amount; f[..., 2] *= 1 - 0.14 * amount
    frame[:] = np.clip(f, 0, 255).astype(np.uint8)


def build_motion(duration, fps, cfg=None, emph=(), words=None, title_end=0.0):
    """Turn a motion config (see render.py plan) into per-frame arrays + the event lists that were used."""
    cfg = dict(cfg or {})
    n = int(round(duration * fps))
    cuts = expand_cuts(cfg.get("cuts"), cfg.get("bursts"), cfg.get("cut_alt", 1.22))
    if "punches" in cfg:
        punches = sorted(float(p) for p in cfg["punches"])
    elif cfg.get("auto_punch", True):
        punches = auto_punches(emph, duration, cuts, words, gap=cfg.get("gap", 2.0), min_gap=cfg.get("min_gap", 1.5), first=max(1.0, title_end))
    else:
        punches = []
    zoom = camera_zoom(n, fps, cuts, punches, cfg.get("rate", 0.01), cfg.get("max_zoom", 1.6), cfg.get("punch_gain", 0.10), cfg.get("ease", 0.033), cfg.get("punch_mode", "pulse"))
    dx, dy = shake(n, fps, punches, cfg.get("shake", 0.0))
    flashes = list(cfg.get("flashes", [])) + [dict(t=w if not isinstance(w, dict) else w["t"], color="white", peak=0.9, dur=0.12) for w in cfg.get("white_flash", [])]
    return dict(n=n, zoom=zoom, dx=dx, dy=dy, cuts=cuts, punches=punches, flashes=flashes, grade=cfg.get("grade", 0.0))
