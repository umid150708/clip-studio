#!/usr/bin/env python3
"""Download the sound-kit source files listed in assets/sfx_kit/download_plan.json. DRY RUN unless --yes (nothing is fetched without it).
Files go to assets/sfx_kit/raw/, each md5-checked against the Internet Archive metadata; assets/sfx_kit/raw/PROVENANCE.json records url, size, md5 and date.

  python3 -I fetch_kit.py            # list what would be fetched
  python3 -I fetch_kit.py --yes      # fetch (about 11.5 MB over HTTPS from archive.org, no login)
"""
import argparse, datetime, hashlib, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.normpath(os.path.join(HERE, "..", "assets", "sfx_kit"))


def url_of(f):
    return f"https://archive.org/download/{f['id']}/{urllib.parse.quote(f['name'], safe='/')}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--yes", action="store_true"); a = ap.parse_args()
    plan = json.load(open(os.path.join(KIT, "download_plan.json")))
    total = sum(f["size"] for f in plan["files"])
    print(f"{plan['source']}\nlicence: {plan['license']}\n")
    for f in plan["files"]:
        print(f"  {f['kind']:7} {f['size'] / 1024:8.1f} KB  {f['title']}\n          {url_of(f)}")
    print(f"\n{len(plan['files'])} files, {total / 1e6:.1f} MB")
    if not a.yes:
        print("dry run: nothing downloaded (pass --yes after approval)"); return
    raw = os.path.join(KIT, "raw"); os.makedirs(raw, exist_ok=True); prov = []
    for f in plan["files"]:
        dest = os.path.join(raw, f["id"] + "__" + os.path.basename(f["name"]))
        data = None
        if os.path.exists(dest):                                   # resume: keep a file that is already there and verifies
            d0 = open(dest, "rb").read()
            if len(d0) == f["size"] and hashlib.md5(d0).hexdigest() == f["md5"]:
                data = d0; print("have", f["title"])
        for attempt in range(4):
            if data is not None:
                break
            try:
                req = urllib.request.Request(url_of(f), headers={"User-Agent": "clip-studio-sfx-kit/1.0"})
                data = urllib.request.urlopen(req, timeout=120).read()
            except Exception as e:                                 # archive.org answers 5xx now and then: wait and try again
                print(f"  retry {attempt + 1} for {f['title']}: {e}"); time.sleep(4 * (attempt + 1))
        if data is None:
            sys.exit(f"could not fetch {f['title']} after retries; run again to resume")
        if len(data) != f["size"] or hashlib.md5(data).hexdigest() != f["md5"]:
            sys.exit(f"CHECKSUM MISMATCH for {f['title']}: refusing to keep it")
        open(dest, "wb").write(data)
        prov.append(dict(f, url=url_of(f), page=f"https://archive.org/details/{f['id']}", file=os.path.relpath(dest, KIT), fetched=datetime.date.today().isoformat()))
        print("ok", f["title"])
    json.dump(prov, open(os.path.join(raw, "PROVENANCE.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
