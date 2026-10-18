# -*- coding: utf-8 -*-
"""Write STORYBOARD.md for the single continuous frame.

    python gen_storyboard.py <project>
"""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    args = ap.parse_args()
    p = args.project

    with open(os.path.join(p, "project.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(p, "lyrics_final.json"), encoding="utf-8") as f:
        lyr = json.load(f)
    am = {}
    if os.path.isfile(os.path.join(p, "audiomap.json")):
        with open(os.path.join(p, "audiomap.json"), encoding="utf-8") as f:
            am = json.load(f)

    dur = float(meta["duration"])
    bpm = (am.get("tempo") or {}).get("bpm")
    tempo_txt = ("%.1f BPM groove" % bpm) if bpm else "free-tempo track"
    anchors = ", ".join("%.2f" % l["start"] for l in lyr)
    copy_block = "\n".join('      "%s",' % l["en"] for l in lyr)
    cid = meta["title"].lower().replace(" ", "-")

    md = """---
compositionId: %s-lyric
duration_s: %s
canvas: { "w": 1080, "h": 1920, "fps": 30 }
style:
  font: "Inter / EB Garamond / JetBrains Mono / Noto Serif SC"
  palette: ["#04050D", "#0C1134", "#CC785C", "#DCA87C", "#F4F1EA"]
assets: true
build_notes:
  - "one continuous timeline for the whole track — the glass body never resets between lyric lines"
  - "lyrics driven by Whisper word timestamps"
  - "deterministic glass body: seeded path, elastic edge compression, morph to a new rounded geometry on every wall hit"
  - "original line + Chinese translation shown as one subtitle group"
  - "credit reads %s; no verse/chorus/section labels anywhere on screen"
  - "animal band sprite layer at the bottom, seamless 4.54 s loop, composited with screen blend"
avoid:
  - "section labels (VERSE / CHORUS / BRIDGE)"
  - "liquid, gooey or shattered shapes — the body always keeps a clean geometric outline"
  - "neon glow, dense particles, strobe or camera shake"
  - "lyrics that move independently of the sung line"
  - "a second bubble — the band asset's own bubble is cropped out"
---

## Frame 1 — f1

- src: compositions/frames/01-f1.html
- duration: %ss
- span_sec: [0.0, %s]
- pacing: beat_cut
- mood: [dark, dreamy, hopeful]
- feel: %s, %d lyric lines; one continuous dreamscape with a floating glass body and per-line bilingual reveals

### Groups

- **g1** — free_design
  - span_sec: [0.0, %s]
  - free_design: { dominant_system: "floating glass body over a deep blue-violet field, per-line bilingual lyric reveal", primitives: ["soft-fade-pull", "line-fade", "shape-morph"], density_topology: "sequential-hold" }
  - anchors: [%s]
  - copy: [
%s
    ]
""" % (cid, dur, meta.get("artist", ""), dur, dur, tempo_txt, len(lyr), dur, anchors, copy_block)

    with open(os.path.join(p, "STORYBOARD.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("wrote STORYBOARD.md (%d chars, %d lines)" % (len(md), len(lyr)))


if __name__ == "__main__":
    main()
