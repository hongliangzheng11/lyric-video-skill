# -*- coding: utf-8 -*-
"""Scaffold a lyric-video project from an audio file.

Creates a fresh, uniquely named project directory, copies the audio, makes the
16 kHz mono WAV used by Whisper, runs the official beat/energy analysis, and
copies the fixed look assets (band sprite sheets, GSAP).

    python new_project.py "D:/music/song.mp3" "Artist Name" [--title "Song Title"]
                          [--root G:/hyperframes/videos] [--tagline "一句中文主题"]
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(SKILL, "assets")
DEFAULT_ROOT = "G:/hyperframes/videos"
DEFAULT_HF = "G:/hyperframes"


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "track"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit("command failed: %s\n%s" % (" ".join(cmd), r.stderr[-800:]))
    return r


def probe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path]).stdout.strip()
    return float(out)


def unique_dir(root, base):
    stamp = dt.datetime.now().strftime("%Y%m%d")
    n = 1
    while True:
        d = os.path.join(root, "%s-lyric-%s-%03d" % (base, stamp, n))
        if not os.path.exists(d):
            return d
        n += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("artist")
    ap.add_argument("--title", default=None)
    ap.add_argument("--tagline", default="")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--hyperframes", default=DEFAULT_HF)
    ap.add_argument("--style", default="auto",
                    help="classic | emotional_listening | energetic_performance | "
                         "funny_interaction | cozy_ensemble | auto | mixed "
                         "(default auto; plan_styles.py can still override)")
    args = ap.parse_args()

    audio = os.path.abspath(args.audio)
    if not os.path.isfile(audio):
        sys.exit("audio not found: %s" % audio)
    title = args.title or os.path.splitext(os.path.basename(audio))[0]
    # "Artist - Title.mp3" is a common naming; drop the artist prefix
    for sep in (" - ", " – ", " — "):
        if sep in title and title.lower().startswith(args.artist.lower()):
            title = title.split(sep, 1)[1].strip()
    dur = probe_duration(audio)

    project = unique_dir(args.root, slug(title))
    os.makedirs(os.path.join(project, "assets"), exist_ok=True)
    os.makedirs(os.path.join(project, "build"), exist_ok=True)
    os.makedirs(os.path.join(project, "compositions", "frames"), exist_ok=True)
    os.makedirs(os.path.join(project, "renders"), exist_ok=True)

    shutil.copy2(audio, os.path.join(project, "assets", "bgm.mp3"))
    run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(project, "assets", "bgm.mp3"),
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
         os.path.join(project, "assets", "vocals16k.wav")])
    for name in ("band_sheet1.webp", "band_sheet2.webp", "gsap.min.js"):
        shutil.copy2(os.path.join(ASSETS, name), os.path.join(project, "assets", name))

    analyze = os.path.join(args.hyperframes, "skills", "music-to-video",
                           "scripts", "analyze-beatgrid.py")
    if not os.path.isfile(analyze):
        sys.exit("missing official analyzer: %s (pass --hyperframes)" % analyze)
    run([sys.executable, analyze, os.path.join(project, "assets", "bgm.mp3"),
         "-o", os.path.join(project, "audiomap.json")], cwd=project)

    meta = {
        "artist": args.artist,
        "artist_upper": args.artist.upper(),
        "title": title,
        "tagline": args.tagline,
        "audio": os.path.basename(audio),
        "duration": round(dur, 3),
        "canvas": [1080, 1920],
        "fps": 30,
        "hyperframes": args.hyperframes,
        "style": args.style,
    }
    with open(os.path.join(project, "project.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(project)
    print("duration %.3fs  title=%r  artist=%r" % (dur, title, args.artist))


if __name__ == "__main__":
    main()
