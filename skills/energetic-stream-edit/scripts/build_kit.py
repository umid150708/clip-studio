#!/usr/bin/env python3
"""Cut the downloaded recordings into kit clips (assets/sfx_kit/cuts.json), check each against what its kind should measure like, and write
assets/sfx_kit/files/*.wav + assets/sfx_kit/kit.json with licence and source for every clip. A clip that fails its check is left out and reported.

  python3 -I build_kit.py

Cuts are cuts: start/end, a short fade-in (against clicks) and a fade-out. No pitch, speed or gain change, no layering.
"""
import json, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_analyze as K
import mixer as X

SR = X.SR
KIT = os.path.normpath(os.path.join(HERE, "..", "assets", "sfx_kit"))
AUTHOR = "USC Cinema / Sunset Editorial sound-effects collection (tapes digitised by Craig Smith); uploaded to the Internet Archive by Jason Scott"


def gate(kind, m):
    """-> list of reasons the clip does not measure like its kind (empty = fine)."""
    why = []
    peak_s = m["onset_s"] + m["time_to_peak_s"]
    if m["peak_dbfs"] > -0.1:
        why.append("clipped")
    if kind == "impact":
        if not 0.5 <= m["seconds"] <= 2.0: why.append(f"length {m['seconds']}s outside 0.5-2.0")
        if m["time_to_peak_s"] > 0.3: why.append(f"slow attack ({m['time_to_peak_s']}s to peak)")
    elif kind in ("pop", "click"):
        if m["seconds"] > 0.6: why.append(f"length {m['seconds']}s over 0.6")
        if m["time_to_peak_s"] > 0.1: why.append(f"slow attack ({m['time_to_peak_s']}s to peak)")
    elif kind == "whoosh":
        if not 0.5 <= m["seconds"] <= 1.7: why.append(f"length {m['seconds']}s outside 0.5-1.7")
        if not 0.15 <= peak_s / m["seconds"] <= 0.85: why.append("peak at the edge of the clip, not a swell")
    elif kind == "riser":
        if not m["rises"]: why.append("does not get louder or brighter")
        if peak_s < 0.6 * m["seconds"]: why.append("peak is not near the end")
    return why


def main():
    spec = json.load(open(os.path.join(KIT, "cuts.json")))
    prov = {os.path.basename(p["file"]): p for p in json.load(open(os.path.join(KIT, "raw", "PROVENANCE.json")))}
    raw = {}
    os.makedirs(os.path.join(KIT, "files"), exist_ok=True)
    kit = {"kinds": {}}; rows, rejected = [], []
    for c in spec["cuts"]:
        key = next((k for k in prov if c["src"].lower() in k.lower()), None)
        if key is None:
            sys.exit(f"no raw file matches {c['src']!r}")
        if key not in raw:
            raw[key] = X.decode(os.path.join(KIT, prov[key]["file"]))
        x = raw[key]
        if "around_peak" in c:
            a, b = c["search"]; seg = np.abs(x[int(a * SR): int(b * SR)])
            pk = a + int(np.argmax(seg)) / SR
            start, end = pk - c["around_peak"][0], pk + c["around_peak"][1]
        else:
            start, end = c["start"], c["end"]
        y = x[max(0, int(start * SR)): int(end * SR)].copy()
        fi, fo = int(c.get("fade_in", 0) * SR), int(c.get("fade_out", 0) * SR)
        if fi: y[:fi] *= 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fi))
        if fo: y[-fo:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo))
        out = os.path.join(KIT, "files", c["out"] + ".wav")
        X.write_wav(out, y)
        m = K.analyze(out); why = gate(c["kind"], m)
        rows.append((c["out"], c["kind"], m, why))
        if why:
            rejected.append(dict(out=c["out"], why=why)); os.remove(out); continue
        kit["kinds"].setdefault(c["kind"], []).append(dict(
            file=f"files/{c['out']}.wav", title=prov[key]["title"], license="CC0 1.0 Universal", author=AUTHOR, url=prov[key]["url"], page=prov[key]["page"],
            source_file=prov[key]["name"], cut=[round(float(start), 3), round(float(end), 3)], fade_in=c.get("fade_in", 0), fade_out=c.get("fade_out", 0),
            anchor=c.get("anchor", "end" if c["kind"] == "riser" else "onset"),
            measured=dict(seconds=m["seconds"], peak_dbfs=m["peak_dbfs"], onset_s=m["onset_s"], time_to_peak_s=m["time_to_peak_s"], decay_to_minus30db_s=m["decay_to_minus30db_s"], rises=m["rises"])))
    kit["not_used"] = spec.get("not_used", []); kit["rejected_by_measurement"] = rejected
    json.dump(kit, open(os.path.join(KIT, "kit.json"), "w"), indent=1, ensure_ascii=False)
    for name, kind, m, why in rows:
        print(f"{'FAIL' if why else 'ok  '} {kind:6} {name:24} {m['seconds']:5.2f}s peak {m['peak_dbfs']:6.1f} to-peak {m['time_to_peak_s']:.2f}s decay30 {m['decay_to_minus30db_s']}  {'; '.join(why)}")
    n = sum(len(v) for v in kit["kinds"].values())
    print(f"\n{n} clips in the kit, {len(rejected)} rejected by measurement")


if __name__ == "__main__":
    main()
