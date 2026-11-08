"""Word-level timings for a finished Crayo export (costs 1 voiceover credit per second of video).
   python3 -I words.py EXPORT_ID OUT.json     (EXPORT_ID is printed as 'export <id> queued' by crayo.py)
"""
import json, sys
sys.path.insert(0, ".")
import crayo

export_id, out = sys.argv[1], sys.argv[2]
asset = crayo.call("GET", f"/v1/exports/{export_id}")["asset"]
tr = crayo.call("POST", "/v1/transcripts", {"asset_id": asset["id"]})["transcript"]
words = [{"w": w["word"], "s": w["start_ms"] / 1000, "e": w["end_ms"] / 1000} for w in tr["words"]]
json.dump({"asset_id": asset["id"], "language": tr["language"], "text": tr["text"], "words": words}, open(out, "w"), indent=1)
print(f"{len(words)} words, asset {asset['id']} -> {out}")
print(tr["text"][:300])
