# -*- coding: utf-8 -*-
"""Check the rendered file against the spec and build a contact sheet.

    python verify.py <project> [--video renders/video.mp4] [--shots 18]

Exits non-zero when a hard spec is violated (wrong canvas, fps, or a duration
that drifts from the source audio by more than one frame).
"""
import argparse
import json
import os
import subprocess
import sys


def ffprobe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,"
         "r_frame_rate,nb_frames,sample_rate,channels",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--video", default=os.path.join("renders", "video.mp4"))
    ap.add_argument("--shots", type=int, default=18)
    args = ap.parse_args()

    p = args.project
    with open(os.path.join(p, "project.json"), encoding="utf-8") as f:
        meta = json.load(f)
    video = os.path.join(p, args.video)
    info = ffprobe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = v["r_frame_rate"].split("/")
    fps = int(num) / int(den)
    dur = float(info["format"]["duration"])
    src = float(meta["duration"])

    print("video   %sx%s  %.3f fps  %s frames  %.2fs  %.1f MB  %.1f Mbps"
          % (v["width"], v["height"], fps, v.get("nb_frames", "?"), dur,
             int(info["format"]["size"]) / 1e6, int(info["format"]["bit_rate"]) / 1e6))
    print("audio   %s" % ("%s %s Hz %s ch" % (a["codec_name"], a["sample_rate"], a["channels"])
                          if a else "MISSING"))
    print("source  %.3fs   delta %+.0f ms (%.1f frames)"
          % (src, (dur - src) * 1000, (dur - src) * fps))

    bad = []
    if (v["width"], v["height"]) != (1080, 1920):
        bad.append("canvas is not 1080x1920")
    if abs(fps - 30) > 0.01:
        bad.append("frame rate is not 30")
    if abs(dur - src) > 1.0 / fps + 0.02:
        bad.append("duration drifts from the source audio by more than a frame")
    if not a:
        bad.append("no audio stream")

    shots = os.path.join(p, "build", "verify")
    os.makedirs(shots, exist_ok=True)
    step = src / (args.shots + 1)
    times = [round(step * (i + 1), 2) for i in range(args.shots)]
    for t in times:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video,
                        "-frames:v", "1", "-q:v", "2",
                        os.path.join(shots, "v%06.1f.jpg" % t)], check=True)

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("pillow missing — frames saved to", shots)
        sys.exit(1 if bad else 0)

    cols, rows, w, h = 6, (len(times) + 5) // 6, 300, 533
    sheet = Image.new("RGB", (cols * w, rows * h), (8, 8, 10))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        im = Image.open(os.path.join(shots, "v%06.1f.jpg" % t)).resize((w, h), Image.LANCZOS)
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 56, y + 22], fill=(0, 0, 0))
        d.text((x + 6, y + 6), "%.1fs" % t, fill=(255, 225, 190))
    out = os.path.join(p, "renders", "contact-sheet.jpg")
    sheet.save(out, quality=92)
    print("contact sheet ->", out)

    if bad:
        print("\nSPEC VIOLATIONS:")
        for b in bad:
            print("  -", b)
        sys.exit(1)
    print("\nOK: canvas / fps / duration / audio all match the spec")


if __name__ == "__main__":
    main()
