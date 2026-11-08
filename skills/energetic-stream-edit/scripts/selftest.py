#!/usr/bin/env python3
"""End-to-end check of a fresh copy of this skill, with no footage of anyone: it makes a throwaway test video, renders a clip with every
feature switched on (script captions, title card, circle, arrow, emoji, labelled window, zoom jumps, flashes, real sound effects from the kit,
end line, loudness master), then measures the result.

  python3 -I selftest.py            # needs ffmpeg, numpy, opencv-python, Pillow, and macOS system fonts

It proves the pipeline runs and the numbers are in range. It cannot tell you the clip looks or sounds good: play it once.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    import render, measure
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "source.mp4")
        # 10 s of 16:9 test picture; the tone gets loud in bursts so there is something for the emphasis finder to hear
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=10",
                        "-f", "lavfi", "-i", "sine=f=220:duration=10", "-af", "volume='0.25+0.6*lt(mod(t,2.7),0.3)':eval=frame",
                        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", src], check=True)
        win = Image.new("RGB", (640, 360), (30, 60, 140)); d = ImageDraw.Draw(win); d.rectangle([40, 40, 600, 320], outline=(255, 255, 255), width=6)
        win_path = os.path.join(td, "window.png"); win.save(win_path)
        plan = {
            "source": src, "start": 0.0, "end": 9.0,
            "captions": {"mode": "script"},
            "script": [{"t0": 1.0, "t1": 2.4, "text": "the test {red|clip} starts"}, {"t0": 2.6, "t1": 4.0, "text": "*something happens*"},
                       {"t0": 4.2, "t1": 6.0, "text": "then {cyan|everything} moves"}],
            "title": {"lines": ["SELF", "TEST"], "colors": ["white", "cyan"], "t0": 0, "t1": 1.5},
            "end_card": {"text": "IT WORKS", "dur": 1.2, "color": "green"},
            "motion": {"cuts": [5.5], "flashes": [{"t": 6.5, "color": "green", "dur": 0.4, "peak": 0.4}], "white_flash": [5.5]},
            "annotations": [
                {"type": "circle", "t0": 2.0, "dur": 1.5, "x": 0.5, "y": 0.5, "r": 0.05},
                {"type": "arrow", "t0": 3.2, "dur": 1.5, "x0": 0.62, "y0": 0.62, "x1": 0.52, "y1": 0.52},
                {"type": "emoji", "t0": 4.0, "dur": 1.2, "char": "🔥", "x": 0.2, "y": 0.25, "space": "screen"},
                {"type": "inset", "t0": 6.8, "dur": 1.5, "src": win_path, "label": "TEST WINDOW", "x": 0.5, "y": 0.2}],
            "sound": {"auto": {"title": True, "annotations": True, "flashes": True, "end_card": True, "annotation_kinds": ["pop", "click"]},
                      "cues": [{"t": 5.0, "kind": "fakeout"}]},
        }
        pp = os.path.join(td, "plan.json"); json.dump(plan, open(pp, "w"))
        # a quiet source needs about 20 dB of gain: this is the case that once measured +4.4 dBTP
        quiet = os.path.join(td, "quiet.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", "volume=0.05", "-c:v", "copy", "-c:a", "aac", quiet], check=True)
        qplan = dict(plan, source=quiet); qp = os.path.join(td, "quiet_plan.json"); json.dump(qplan, open(qp, "w"))
        qout = os.path.join(td, "quiet_out.mp4")
        out = os.path.join(td, "out.mp4")
        B = render.render(pp, out, lufs=-12)
        m = measure.measure(out)
        render.render(qp, qout, lufs=-12)
        mq = measure.loudness(qout)
        rep = B["sound_report"]
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,channels", "-of", "json", out]))
        v = next(s for s in probe["streams"] if s["codec_type"] == "video"); a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        checks = [
            (f"video {v['width']}x{v['height']} @ {v['r_frame_rate']}", (v["width"], v["height"], v["r_frame_rate"]) == (1080, 1920, "30/1")),
            (f"duration {m['dur']} s", abs(m["dur"] - 9.0) < 0.2),
            (f"audio stereo ({a['channels']} ch)", a["channels"] == 2),
            (f"{len(rep['placements'])} sound placements (title, 3 annotations, flash, end line, fake-out riser + hit)", len(rep["placements"]) >= 9),
            (f"fake-out dip {rep['dips']}", rep["dips"] == [(4.7, 5.0)]),
            (f"loudness {m['LUFS']} LUFS (target -12)", abs(m["LUFS"] + 12) < 1.6),
            (f"quiet source: true peak {mq['true_peak_dB']} dBTP (<= -1.0)", mq["true_peak_dB"] <= -1.0),
            (f"true peak {m['true_peak_dB']} dBTP (<= -1.0)", m["true_peak_dB"] <= -1.0),
            (f"{m['jumps']} zoom jumps found", m["jumps"] >= 2),
            (f"yellow caption height {m['yellow_caption_centre_y']} (expect ~0.47)", m["yellow_caption_centre_y"] is None or abs(m["yellow_caption_centre_y"] - 0.47) < 0.06),
        ]
    bad = 0
    for name, ok in checks:
        print(("ok   " if ok else "FAIL ") + name); bad += (not ok)
    print("\nselftest passed" if not bad else f"\nselftest: {bad} check(s) failed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
