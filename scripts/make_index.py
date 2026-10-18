# -*- coding: utf-8 -*-
"""Write index.html: one root composition mounting the frame + the track.

    python make_index.py <project>

Mirrors what the music-to-video skill's assemble-index.mjs produces for a
single-frame storyboard, without needing the storyboard parser.
"""
import argparse
import json
import os

TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="assets/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #000; }
      #root { position: relative; width: 1080px; height: 1920px; overflow: hidden; }
      .frame { position: absolute; inset: 0; width: 100%; height: 100%; }
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="__DUR__"
      data-width="1080"
      data-height="1920"
    >
      <div
        id="el-01-f1"
        class="frame"
        data-composition-id="01-f1"
        data-composition-src="compositions/frames/01-f1.html"
        data-start="0"
        data-duration="__DUR__"
        data-track-index="1"
      ></div>

      <!-- BGM -->
      <audio id="el-bgm" src="assets/bgm.mp3" data-start="0" data-duration="__DUR__"
        data-track-index="11" data-volume="0.9"></audio>
    </div>

    <script>
      window.__timelines = window.__timelines || {};
      window.__timelines["main"] = gsap.timeline({ paused: true });
    </script>
  </body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    args = ap.parse_args()
    with open(os.path.join(args.project, "project.json"), encoding="utf-8") as f:
        meta = json.load(f)
    html = TEMPLATE.replace("__DUR__", "%.3f" % float(meta["duration"]))
    path = os.path.join(args.project, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", path)


if __name__ == "__main__":
    main()
