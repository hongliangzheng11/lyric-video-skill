# -*- coding: utf-8 -*-
"""Assemble compositions/frames/01-f1.html from the skill template + project data.

    python build_frame.py <project>
"""
import argparse
import json
import os
import unicodedata

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(SKILL, "assets", "frame_template.html")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def visual_width(text):
    """Display width in em — CJK / kana are full width, latin about half."""
    return sum(1.0 if unicodedata.east_asian_width(c) in ("W", "F") else 0.52
               for c in text)


def font_size(text):
    if any(unicodedata.east_asian_width(c) in ("W", "F") for c in text):
        # the 56/50/45/40 ladder assumes latin metrics; a full-width line needs
        # to be measured, otherwise kana push the block past the 60 px margins
        w = visual_width(text)
        for size in (56, 50, 45, 40, 36, 32):
            if w * size <= 940:
                return size
        return 30
    n = len(text)
    if n <= 26:
        return 56
    if n <= 34:
        return 50
    if n <= 42:
        return 45
    return 40


def title_size(text, base, width):
    """Shrink the display face so long titles still fit the safe width."""
    return int(min(base, width / max(4.0, 0.5 * len(text))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    args = ap.parse_args()
    p = args.project

    meta = load(os.path.join(p, "project.json"))
    motion = load(os.path.join(p, "motion.json"))
    lyrics = load(os.path.join(p, "lyrics_final.json"))
    am = load(os.path.join(p, "audiomap.json"))

    dur = float(meta["duration"])
    energy = [[round(e["start"], 3), round(e["end"], 3), round(float(e["energy"]), 3)]
              for e in am["energy_phases"]]

    lines = []
    for i, l in enumerate(lyrics):
        nxt = lyrics[i + 1]["start"] if i + 1 < len(lyrics) else l["end"] + 3.0
        lines.append({"start": l["start"], "end": l["end"], "ns": nxt,
                      "en": l["en"], "zh": l.get("zh", ""), "size": font_size(l["en"])})

    with open(TPL, encoding="utf-8") as f:
        html = f.read()

    title = meta["title"]
    html = html.replace("__DUR__", "%.3f" % dur)
    html = html.replace("__ARTIST_UPPER__", meta.get("artist_upper") or meta["artist"].upper())
    html = html.replace("__TITLE_SIZE__", str(title_size(title, 132, 900)))
    html = html.replace("__OUTRO_SIZE__", str(title_size(title, 104, 780)))
    html = html.replace("__TITLE__", title)
    tagline = (meta.get("tagline") or "").strip()
    if tagline:
        html = html.replace("__TAGLINE__", tagline)
    else:
        html = html.replace('          <div class="sub">__TAGLINE__</div>\n', "")

    html = html.replace('/*__MOTION__*/{ "legs": [], "bounces": [] }',
                        json.dumps(motion, separators=(",", ":")))
    html = html.replace("/*__ENERGY__*/[[0, 1, 0.02]]", json.dumps(energy, separators=(",", ":")))
    html = html.replace("/*__LYRICS__*/[]",
                        json.dumps(lines, ensure_ascii=False, separators=(",", ":")))

    # outro card / credit / fade must follow the actual tail of the song, not a
    # fixed second count — a 4:31 track would otherwise show the closing card
    # in the middle of verse three.
    last_end = max(l["end"] for l in lines) if lines else 0.0
    tail = dur - last_end
    if tail >= 6.0:
        credit_out = (last_end - 0.2, last_end + 1.4)
        outro_in = (last_end + 0.9, last_end + 2.9)
    else:
        credit_out = (dur - 2.0, dur - 0.4)
        outro_in = (dur + 2.0, dur + 4.0)   # no room for a closing card
    fade = (dur - 2.5, dur - 0.1)

    # the title card sits on the same optical centre as the lyrics, so it has to
    # be gone before the first sung line — a track that opens early would
    # otherwise stack the title on top of verse one.
    first_start = min((l["start"] for l in lines), default=99.0)
    title_in, title_out = (2.2, 3.6), (11.4, 12.8)
    if first_start - 0.9 < title_out[1]:
        title_out = (max(3.9, first_start - 2.4), max(4.7, first_start - 1.0))
    if title_out[0] - title_in[1] < 1.4:      # no room to hold after the fade-in
        title_in = (max(0.6, title_out[0] - 2.9), max(1.6, title_out[0] - 1.5))

    for token, pair in (("__CREDIT_OUT0__", credit_out[0]), ("__CREDIT_OUT1__", credit_out[1]),
                        ("__OUTRO_IN0__", outro_in[0]), ("__OUTRO_IN1__", outro_in[1]),
                        ("__TITLE_IN0__", title_in[0]), ("__TITLE_IN1__", title_in[1]),
                        ("__TITLE_IN1P__", title_in[1] + 0.2),
                        ("__TITLE_OUT0__", title_out[0]), ("__TITLE_OUT1__", title_out[1]),
                        ("__FADE0__", fade[0]), ("__FADE1__", fade[1])):
        html = html.replace(token, "%.3f" % pair)

    for token in ("__DUR__", "__TITLE__", "__TAGLINE__", "__ARTIST_UPPER__",
                  "__TITLE_SIZE__", "__OUTRO_SIZE__", "/*__MOTION__*/", "/*__LYRICS__*/",
                  "__CREDIT_OUT0__", "__OUTRO_IN0__", "__TITLE_IN0__",
                  "__TITLE_IN1P__", "__TITLE_OUT0__", "__FADE0__"):
        if token in html:
            raise SystemExit("template placeholder left unfilled: %s" % token)

    out = os.path.join(p, "compositions", "frames", "01-f1.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d bytes, %d lines, %d legs, %d bounces)"
          % (out, len(html), len(lines), len(motion["legs"]), len(motion["bounces"])))


if __name__ == "__main__":
    main()
