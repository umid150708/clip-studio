"""Rank clip moments for FUNNY / HAPPY content with FAMOUS guests.

Signals per candidate window:
  - timestamps typed in comments (weight by likes)          -> clusters
  - YouTube 'Most replayed' heatmap                          -> heat
  - laugh/happy share of the comments in the cluster         -> fun
  - sponsor-read keywords in the captions of that window     -> ad flag (excluded)
Usage: python3 -I find_moments.py <meta_dir> <subs_dir> <out_json> [--bonus VIDEO_ID=1.5[:Guest name]] [--ad SPONSOR_WORD] ...
"""
import glob, json, math, os, re, sys

TS = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?![\d:])")
LAUGH = re.compile(r"[😂🤣😆😹💀😭🤪😅]|\b(lol|lmao|lmfao|haha+|hahaha|dead|dying|hilarious|funny|crying|cracked|rofl)\b", re.I)
HAPPY = re.compile(r"[❤🥰😍🥹😊🔥👏🙌💯]|\b(wholesome|love this|so cute|goated|legend|W\b)", re.I)
AD_WORDS = ["use code", "promo code", "terms apply", "download the", "sponsored", "brought to you", "link in the description", "% off", "sign up", "free trial"]   # add show-specific sponsors with --ad WORD
ADS = re.compile("(" + "|".join(re.escape(w) for w in AD_WORDS) + ")", re.I)

FAMOUS = {}   # filled from --bonus VIDEO_ID=1.5[:Guest name]  (a bigger name earns a bigger score)


def to_sec(h, m, s):
    return int(h or 0) * 3600 + int(m) * 60 + int(s)


def captions(subs_dir, vid):
    p = os.path.join(subs_dir, f"{vid}.en.json3")
    if not os.path.exists(p):
        return None
    out = []
    for ev in json.load(open(p)).get("events", []):
        segs = ev.get("segs")
        if segs:
            t = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
            if t:
                out.append((ev["tStartMs"] / 1000.0, t))
    return out


def window_text(caps, a, b):
    return " ".join(t for s, t in (caps or []) if a <= s <= b)


def heat_at(heat, t):
    for s in heat or []:
        if s["start_time"] <= t < s["end_time"]:
            return s["value"]
    return 0.0


def fmt(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def analyse(path, subs_dir):
    d = json.load(open(path))
    vid, dur = d["id"], d.get("duration") or 0
    comments = d.get("comments") or []
    caps = captions(subs_dir, vid)
    heat = d.get("heatmap") or []
    n = max(len(comments), 1)
    vid_laugh = sum(1 for c in comments if LAUGH.search(c.get("text") or "")) / n
    vid_happy = sum(1 for c in comments if HAPPY.search(c.get("text") or "")) / n

    hits = []
    for c in comments:
        text, likes = c.get("text") or "", c.get("like_count") or 0
        for m in TS.finditer(text):
            t = to_sec(*m.groups())
            if 20 < t < dur - 25:
                hits.append((t, likes, text.replace("\n", " ")[:150], bool(LAUGH.search(text)), bool(HAPPY.search(text))))
    hits.sort()
    clusters = []
    for t, likes, text, lf, hp in hits:
        if clusters and t - clusters[-1]["end"] <= 25:
            c = clusters[-1]; c["end"] = t; c["w"] += 1 + math.log1p(likes); c["n"] += 1
            c["likes"] += likes; c["laugh"] += lf; c["happy"] += hp; c["quotes"].append((likes, text))
        else:
            clusters.append(dict(start=t, end=t, w=1 + math.log1p(likes), n=1, likes=likes, laugh=int(lf), happy=int(hp), quotes=[(likes, text)]))
    # heat-only candidates (no comment cluster nearby)
    for s in heat:
        if s["value"] >= 0.75 and 20 < s["start_time"] < dur - 25 and not any(abs(c["start"] - s["start_time"]) < 30 or c["start"] - 30 < s["start_time"] < c["end"] + 30 for c in clusters):
            clusters.append(dict(start=int(s["start_time"]), end=int(s["end_time"]), w=0, n=0, likes=0, laugh=0, happy=0, quotes=[]))
    out = []
    guest, bonus = FAMOUS.get(vid, ("", 0.0))
    for c in clusters:
        a, b = c["start"] - 8, c["end"] + 30
        txt = window_text(caps, a, b)
        is_ad = bool(ADS.search(txt))
        h = max(heat_at(heat, x) for x in (c["start"], (c["start"] + c["end"]) // 2, c["end"]))
        laugh_share = (c["laugh"] + 0.5 * vid_laugh * 2) / (c["n"] + 1)  # smoothed toward the video-level rate
        fun = 3 * laugh_share + 1.5 * (c["happy"] / (c["n"] + 1)) + 4 * vid_laugh
        score = c["w"] + 4 * h + fun + bonus
        out.append(dict(id=vid, start=c["start"], end=c["end"], n=c["n"], likes=c["likes"], heat=round(h, 2),
                        laugh=c["laugh"], happy=c["happy"], ad=is_ad, score=round(score, 2),
                        quotes=sorted(c["quotes"], reverse=True)[:2], text=txt[:260]))
    out.sort(key=lambda x: -x["score"])
    return dict(id=vid, title=d["title"], dur=dur, views=d.get("view_count"), guest=guest, n_comments=len(comments),
                vid_laugh=round(vid_laugh, 2), vid_happy=round(vid_happy, 2), has_caps=caps is not None, moments=out)


if __name__ == "__main__":
    meta, subs, outp = sys.argv[1:4]
    rest = sys.argv[4:]
    while rest:
        flag, val = rest[0], rest[1] if len(rest) > 1 else ""
        if flag == "--bonus":
            vid, _, tail = val.partition("=")
            num, _, who = tail.partition(":")
            FAMOUS[vid] = (who, float(num))
        elif flag == "--ad":
            AD_WORDS.append(val)
            ADS = re.compile("(" + "|".join(re.escape(w) for w in AD_WORDS) + ")", re.I)
        else:
            sys.exit(f"unknown option {flag}")
        rest = rest[2:]
    vids = [analyse(p, subs) for p in sorted(glob.glob(os.path.join(meta, "*.info.json")))]
    json.dump(vids, open(outp, "w"), indent=1)
    print("VIDEO FUNNINESS (share of comments with laugh / happy markers)")
    for v in sorted(vids, key=lambda v: -v["vid_laugh"]):
        print(f"  laugh={v['vid_laugh']:.2f} happy={v['vid_happy']:.2f} comments={v['n_comments']:>3} caps={'y' if v['has_caps'] else 'N'} {v['id']} {v['guest'] or '-':<34} {v['title'][:60]}")
    flat = [dict(m, title=v["title"], guest=v["guest"]) for v in vids for m in v["moments"] if not m["ad"]]
    flat.sort(key=lambda m: -m["score"])
    print("\nTOP 24 NON-AD MOMENTS")
    for m in flat[:24]:
        print(f"[{m['score']:>5}] {m['id']} {fmt(m['start'])}-{fmt(m['end'])} heat={m['heat']:.2f} n={m['n']} lol={m['laugh']} | {m['guest'] or m['title'][:30]}")
        for lk, q in m["quotes"][:1]:
            print(f"        ({lk}) {q[:120]}")
        print(f"        TXT: {m['text'][:170]}")
    print("\nAD-FLAGGED (excluded):", ", ".join(f"{m['id']}@{fmt(m['start'])}" for v in vids for m in v["moments"] if m["ad"] and m["score"] > 8)[:400])
