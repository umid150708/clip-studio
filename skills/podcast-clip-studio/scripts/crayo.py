#!/usr/bin/env python3
"""Small Crayo API client (stdlib only) for podcast-clipping workflows.

The key is read from ~/.config/podcast-clip-studio/crayo.env (CRAYO_API_KEY=...) or the
CRAYO_API_KEY environment variable. It is never printed.

Anything that spends credits (autoclip, export, run) is a DRY RUN unless you pass --yes.

  python3 -I crayo.py account
  python3 -I crayo.py styles
  python3 -I crayo.py upload segments/01_example.mp4
  python3 -I crayo.py run segments/01_example.mp4 --length 60 --prompt "..." --yes
"""
import argparse, json, mimetypes, os, sys, time, urllib.error, urllib.request

BASE = "https://api.crayo.ai"
ENV_FILE = os.path.expanduser("~/.config/podcast-clip-studio/crayo.env")
UA = "podcast-clip-studio/1.0"


def api_key():
    k = os.environ.get("CRAYO_API_KEY", "")
    if not k and os.path.exists(ENV_FILE):
        for line in open(ENV_FILE):
            if line.startswith("CRAYO_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    if not k.startswith("crayo_sk_"):
        sys.exit("No Crayo key found. Run: bash save-crayo-key.sh")
    return k


def call(method, path, body=None, tries=8):
    for attempt in range(tries):
        req = urllib.request.Request(
            BASE + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                detail = json.load(e)
            except Exception:
                detail = {}
            code = (detail.get("error") or {}).get("code")
            # Crayo allows one in-flight request per account for some endpoints: wait and retry
            if e.code == 429 and code in ("CONCURRENT_REQUEST", "RATE_LIMITED") and attempt < tries - 1:
                time.sleep(float(e.headers.get("Retry-After") or 4) + attempt)
                continue
            sys.exit(f"HTTP {e.code} {method} {path}: {json.dumps(detail)}")


def upload(path):
    """Signed-URL upload (create -> PUT bytes -> complete). Returns the asset dict."""
    size = os.path.getsize(path)
    ctype = mimetypes.guess_type(path)[0] or "video/mp4"
    up = call("POST", "/v1/uploads", {"filename": os.path.basename(path)[:100], "content_type": ctype, "size_bytes": size})["upload"]
    with open(path, "rb") as f:
        put = urllib.request.Request(up["url"], data=f.read(), method=up["method"], headers=dict(up["headers"]))
        urllib.request.urlopen(put, timeout=900).read()
    return call("POST", f"/v1/uploads/{up['id']}/complete", {})["asset"]


def wait(fetch, done=("completed",), failed=("failed",), every=10, limit=1800):
    t0 = time.time()
    while time.time() - t0 < limit:
        data = fetch()
        obj = next(v for k, v in data.items() if isinstance(v, dict) and "status" in v)
        print(f"  status={obj['status']} progress={obj.get('progress', '?')}", flush=True)
        if obj["status"] in done:
            return data
        if obj["status"] in failed:
            sys.exit(f"Job failed: {json.dumps(obj)}")
        time.sleep(every)
    sys.exit("Timed out waiting for job.")


def autoclip_body(a, asset_id):
    body = {"asset_id": asset_id, "clip_count": a.count, "clip_length": a.length,
            "edit_level": a.edit_level, "formats": a.formats.split(","), "mode": "speech"}
    if a.prompt:
        if len(a.prompt) > 500:
            sys.exit(f"--prompt is {len(a.prompt)} chars, max 500.")
        body["prompt"] = a.prompt
    if a.language:
        body["language"] = a.language
    return body


def download(url, dest):
    """The file host rejects Python's default user-agent (403), so send ours."""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def fetch_export(export_id, name, out_dir):
    done = wait(lambda: call("GET", f"/v1/exports/{export_id}"))
    dest = os.path.join(out_dir, f"{name}.mp4")
    download(done["asset"]["url"], dest)
    a = done["asset"]
    print(f"saved {dest} ({a.get('length')}s, {a.get('width')}x{a.get('height')}, {a.get('size')} bytes)")
    return dest


def export_and_download(project_id, out_dir):
    ex = call("POST", f"/v1/projects/{project_id}/export")["export"]
    print(f"export {ex['id']} queued, credits_charged={ex.get('credits_charged')}")
    return fetch_export(ex["id"], project_id, out_dir)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("account")
    sub.add_parser("styles")
    u = sub.add_parser("upload"); u.add_argument("file")
    for name in ("autoclip", "run"):
        s = sub.add_parser(name)
        s.add_argument("target", help="asset id (autoclip) or local file (run)")
        s.add_argument("--count", type=int, default=2, help="2-20 (API minimum is 2)")
        s.add_argument("--length", type=int, default=60, choices=(30, 60, 90))
        s.add_argument("--edit-level", default="full", choices=("clips", "captions", "cropped", "full"))
        s.add_argument("--formats", default="title-subtitles", help="comma list: streamer,split,black-box,title-subtitles,full-video")
        s.add_argument("--prompt", default="")
        s.add_argument("--language", default="")
        s.add_argument("--out", default="shorts")
        s.add_argument("--yes", action="store_true", help="actually spend credits")
    e = sub.add_parser("export"); e.add_argument("project_id"); e.add_argument("--out", default="shorts"); e.add_argument("--yes", action="store_true")
    f = sub.add_parser("fetch", help="download an already-rendered export (free)")
    f.add_argument("export_id"); f.add_argument("--name", default=None); f.add_argument("--out", default="shorts")
    a = p.parse_args()

    if a.cmd == "account":
        d = call("GET", "/v1/account")
        print(json.dumps({k: d[k] for k in ("account", "credits", "storage") if k in d}, indent=1))
    elif a.cmd == "styles":
        for s in call("GET", "/v1/subtitle-styles")["styles"]:
            print(f"{s['style_id']:<28} {s['name']:<24} {s['font_family']:<18} bg={s['has_background']} anim={s['animation']}")
    elif a.cmd == "upload":
        asset = upload(a.file)
        print(json.dumps({k: asset[k] for k in ("id", "name", "type", "length", "width", "height", "size")}, indent=1))
    elif a.cmd == "fetch":
        fetch_export(a.export_id, a.name or a.export_id, a.out)
    elif a.cmd == "export":
        if not a.yes:
            sys.exit("DRY RUN: export costs 1 export credit per second of video. Re-run with --yes.")
        export_and_download(a.project_id, a.out)
    else:  # autoclip / run
        local = a.cmd == "run"
        if not a.yes:
            print("DRY RUN (no credits spent). AutoClip body would be:")
            print(json.dumps(autoclip_body(a, "<asset_id>"), indent=1))
            print(f"Cost: {a.count} video credits for the job + export credits per exported second. Add --yes to run.")
            return
        asset_id = upload(a.target)["id"] if local else a.target
        job = call("POST", "/v1/autoclip", autoclip_body(a, asset_id))["autoclip"]
        print(f"autoclip {job['id']} queued, credits_charged={job.get('credits_charged')}")
        done = wait(lambda: call("GET", f"/v1/autoclip/{job['id']}"))
        clips = done["autoclip"].get("clips", [])
        print(json.dumps(clips, indent=1))
        if local:
            for c in clips:
                export_and_download(c["project_id"], a.out)


if __name__ == "__main__":
    main()
