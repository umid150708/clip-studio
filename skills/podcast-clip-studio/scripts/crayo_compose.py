#!/usr/bin/env python3
"""Assemble ONE short inside Crayo from what `reel.py --plain` produced:
     head-tracked picture (OUT.mp4) + processed narration (OUT.mp4.narration.mp3) + cutaway clips (cutaways/*.mp4)
   -> one Crayo project (scenes = picture / cutaway / picture ..., narration underneath, Crayo captions, Crayo title card)
   -> ONE export, downloaded to OUT_DIR.

   python3 -I crayo_compose.py finals/clip01.mp4 --name "01 Example" --title "One line that frames the moment" [--style 122] [--yes]

Dry run by default. With --yes: uploads (free), creates one project (free, but captions cost 1 voiceover credit per second)
and exports it once (1 export credit per second). Never run twice for the same clip without asking the user.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crayo

ap = argparse.ArgumentParser()
ap.add_argument("main")
ap.add_argument("--name", required=True, help="project name in Crayo")
ap.add_argument("--title", required=True, help="one-line title card shown at the top for the first seconds")
ap.add_argument("--style", default="122", help="subtitle style_id (122 = Black Caps, word-by-word)")
ap.add_argument("--title-secs", type=float, default=3.2)
ap.add_argument("--out", default="finals/crayo")
ap.add_argument("--yes", action="store_true")
ap.add_argument("--patch", default=None, help="update this existing project in place instead of creating a new one")
ap.add_argument("--no-export", action="store_true", help="create the project only; inspect it in the editor, then export it once")
a = ap.parse_args()

info = json.load(open(a.main + ".json"))
D = info["duration"]
import subprocess as _sp
D = min(D, float(_sp.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.main])) - 0.06)
windows = sorted(zip([c[0] for c in info["cutaways"]], [c[1] for c in info["cutaways"]], info["cutaway_files"]))
ms = lambda s: int(round(s * 1000))

plan = []   # (kind, start_s, end_s, file)
cur = 0.0
for t0, t1, f in windows:
    if t0 - cur > 0.05:
        plan.append(("main", cur, t0, a.main))
    plan.append(("cutaway", t0, t1, f))
    cur = t1
if D - cur > 0.5:                     # a sliver of speaker after the last cutaway is dropped instead of flashing on screen
    plan.append(("main", cur, D, a.main))
elif plan:
    D = plan[-1][2]

print(f"{a.name}: {D:.1f}s, {sum(1 for p in plan if p[0] == 'cutaway')} cutaways, {len(plan)} scenes")
for kind, s, e, f in plan:
    print(f"  {kind:8} {s:6.2f}-{e:6.2f}  {os.path.basename(f)}")
if not a.yes:
    print("DRY RUN. Add --yes to upload, create the project and export once.")
    sys.exit(0)

# ---- every cutaway file must be at least as long as its slot, or the timeline would desync from the narration
import subprocess
for kind, s, e, f in plan:
    if kind == "cutaway":
        have = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))
        if have < (e - s) - 0.05:
            sys.exit(f"{f} is {have:.2f}s but its slot is {e - s:.2f}s. Re-render it longer.")

# ---- upload (free)
CACHE = "uploads.json"   # path -> {size, asset_id}: never upload the same file twice
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
ids = {}
for f in {p[3] for p in plan} | {a.main + ".narration.mp3"}:
    key = f"{f}:{os.path.getsize(f)}:{int(os.path.getmtime(f))}"
    if key not in cache:
        cache[key] = crayo.upload(f)["id"]
        json.dump(cache, open(CACHE, "w"), indent=1)
        print("uploaded", os.path.basename(f), cache[key])
    ids[f] = cache[key]

scenes = []
for kind, s, e, f in plan:
    scenes.append({"asset_id": ids[f], "start_ms": ms(s), "end_ms": ms(e), "volume": 0, "fit": "cover",
                   **({"trim_start_ms": ms(s)} if kind == "main" else {})})
for prev, nxt in zip(scenes, scenes[1:]):  # make the timeline gapless and non-overlapping after rounding
    nxt["start_ms"] = prev["end_ms"]
scenes[-1]["end_ms"] = max(scenes[-1]["end_ms"], scenes[-1]["start_ms"] + 100)

body = {"title": a.name, "scenes": scenes,
        "narration": {"asset_id": ids[a.main + ".narration.mp3"], "volume": 100},
        "subtitles": {"style_id": a.style, "position": "bottom"},
        "texts": [{"text": a.title, "start_ms": 0, "end_ms": ms(min(a.title_secs, D)), "position": "top",
                   "font_size": 62, "color": "#000000", "background_color": "#ffffff"}]}
if a.patch:   # edit the project we already made, so no duplicates pile up in the account
    proj = crayo.call("PATCH", f"/v1/projects/{a.patch}", {"scenes": scenes})["project"]
else:
    proj = crayo.call("POST", "/v1/projects", body)["project"]
print("project", proj["id"], f"{proj['duration_ms'] / 1000:.1f}s", proj.get("edit_url", ""))
json.dump({"project_id": proj["id"], "name": a.name}, open(a.main + ".project.json", "w"))

if a.no_export:
    print("created without exporting. Check it in the editor, then: python3 -I crayo.py export", proj["id"], "--out", a.out, "--yes")
else:
    crayo.export_and_download(proj["id"], a.out)
